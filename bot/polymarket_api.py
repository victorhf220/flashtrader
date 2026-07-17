"""
Integração com Polymarket API para obter dados reais de mercados
Permite calcular spreads reais ao invés de estimados

IMPORTANTE: URLs e estruturas podem variar - sempre testar contra live API
Referência: https://docs.polymarket.com/api
"""

import logging
import json
import requests
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
import time

logger = logging.getLogger(__name__)

# URLs da API Polymarket (July 2026)
# NOTA: Verificar se URLs estão atualizadas se comportamento mudar
POLYMARKET_API_BASE = "https://clob.polymarket.com"
POLYMARKET_REST_API = "https://polymarket.com/api"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"  # Alternativa

# Cache TTLs
SPREAD_CACHE_TTL = 300  # 5 minutos
MARKET_CACHE_TTL = 3600  # 1 hora
MAX_CACHE_SIZE = 1000  # Evita crescimento infinito

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 60
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # segundos

@dataclass
class MarketData:
    """Dados de um mercado Polymarket com validação"""
    market_id: str
    question: str
    category: str
    outcomes: Dict[str, float] = field(default_factory=dict)  # {outcome_name: probability}
    spread: float = 0.0  # diferença entre melhor bid e ask
    volume_24h: float = 0.0
    liquidity: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validações após inicialização"""
        if not self.market_id or not isinstance(self.market_id, str):
            raise ValueError(f"market_id inválido: {self.market_id}")
        if not self.question or not isinstance(self.question, str):
            raise ValueError(f"question inválida: {self.question}")
        if not -0.01 < self.spread < 1.01:
            logger.warning(f"Spread fora do range esperado: {self.spread}")
        if self.volume_24h < 0 or self.liquidity < 0:
            logger.warning(f"Volume/Liquidity negativo: vol={self.volume_24h}, liq={self.liquidity}")
    
    def __repr__(self):
        return (f"Market({self.question[:40]}... | "
                f"Spread: {self.spread:.2%} | Vol: ${self.volume_24h:.0f})")
    
    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Verifica se dados são antigos"""
        age = (datetime.now() - self.last_updated).total_seconds()
        return age > max_age_seconds


def rate_limit(max_per_minute: int = 60):
    """Decorador para rate limiting"""
    min_interval = 60.0 / max_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(f"Rate limit: aguardando {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_on_failure(max_attempts: int = 3, delay: int = 2):
    """Decorador para retry com backoff exponencial"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, TimeoutError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} falhou (tentativa {attempt + 1}/{max_attempts}). "
                            f"Aguardando {wait_time}s antes de retry..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} falhou após {max_attempts} tentativas")
            
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


class PolymarketAPI:
    """
    Cliente para API da Polymarket com retry, rate limiting e fallbacks
    
    ⚠️ IMPORTANTE:
    - Respeita rate limits (60 req/min)
    - Retry automático com backoff exponencial
    - Fallback para GAMMA_API se principal falha
    - Validação de dados e tratamento de erros robusto
    - Cache com limpeza automática
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Sentinel-Arbitrage-Bot/1.0.1',
            'Connection': 'keep-alive'
        })
        self.session.timeout = 10
        
        # Cache com limite de tamanho
        self.market_cache: Dict[str, MarketData] = {}
        self.cache_timestamp: Dict[str, datetime] = {}
        self.request_count = 0
        self.last_request_time = 0.0
        
        logger.info("PolymarketAPI inicializado")
    
    def _clean_cache(self):
        """Limpa cache se exceder limite de tamanho"""
        if len(self.market_cache) > MAX_CACHE_SIZE:
            # Garante que toda chave no cache tenha timestamp - protege contra
            # entradas órfãs que impediriam a limpeza de funcionar corretamente
            for key in self.market_cache:
                if key not in self.cache_timestamp:
                    self.cache_timestamp[key] = datetime.min
            
            # Remove as 10% entradas mais antigas
            oldest_keys = sorted(
                self.cache_timestamp.items(),
                key=lambda x: x[1]
            )[:int(MAX_CACHE_SIZE * 0.1)]
            
            for key, _ in oldest_keys:
                self.market_cache.pop(key, None)
                self.cache_timestamp.pop(key, None)
            
            logger.info(f"Cache limpado: removidas {len(oldest_keys)} entradas antigas")
    
    def _make_request(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = "GET",
        fallback_url: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Faz requisição HTTP com retry e fallback
        
        Args:
            url: URL principal
            params: Parâmetros de query
            method: GET, POST, etc
            fallback_url: URL alternativa se principal falha
        
        Returns:
            JSON response ou None se falha
        """
        for attempt in range(RETRY_ATTEMPTS):
            try:
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=10)
                else:
                    response = self.session.post(url, json=params, timeout=10)
                
                # Verifica status
                if response.status_code == 429:  # Rate limited
                    wait_time = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Aguardando {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                return response.json()
            
            except requests.Timeout:
                logger.warning(f"Timeout na tentativa {attempt + 1}/{RETRY_ATTEMPTS}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))
            
            except requests.ConnectionError as e:
                logger.warning(f"Connection error: {e}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))
            
            except requests.HTTPError as e:
                logger.error(f"HTTP error {response.status_code}: {e}")
                if response.status_code >= 500:  # Server error, retry
                    if attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(RETRY_DELAY * (2 ** attempt))
                else:  # Client error, não retry
                    break
            
            except ValueError:
                logger.error(f"Resposta inválida: {response.text[:200]}")
                break
        
        # Fallback para URL alternativa
        if fallback_url and fallback_url != url:
            logger.info(f"Tentando fallback URL: {fallback_url}")
            return self._make_request(fallback_url, params, method, fallback_url=None)
        
        return None
    
    def search_markets(self, query: str, limit: int = 10) -> List[MarketData]:
        """
        Busca mercados por termo na Polymarket com retry e fallback
        
        Args:
            query: Termo de busca (ex: "Bitcoin", "Trump")
            limit: Número máximo de resultados (1-100)
        
        Returns:
            Lista de MarketData relevantes (pode estar vazia)
        """
        # Validações
        if not query or not isinstance(query, str):
            logger.error(f"Query inválida: {query}")
            return []
        
        if not 1 <= limit <= 100:
            logger.warning(f"Limit fora do range (1-100): {limit}. Ajustando...")
            limit = max(1, min(100, limit))
        
        query = query.strip()
        
        try:
            url = f"{POLYMARKET_REST_API}/markets"
            params = {
                "q": query,
                "limit": limit,
                "order": "volume"
            }
            
            # Faz requisição com retry e fallback
            data = self._make_request(
                url,
                params=params,
                fallback_url=f"{POLYMARKET_GAMMA_API}/markets"
            )
            
            if not data:
                logger.warning(f"Nenhuma resposta ao buscar '{query}'")
                return []
            
            markets = []
            
            # A API real da Polymarket (Gamma) retorna uma lista JSON diretamente,
            # mas outras variantes/versões podem envelopar em {"data": [...]} ou {"markets": [...]}
            # Tratamos os dois formatos por segurança.
            if isinstance(data, list):
                market_list = data
            elif isinstance(data, dict):
                market_list = data.get("data", []) or data.get("markets", [])
            else:
                logger.error(f"Formato de resposta inesperado: {type(data)}")
                return []
            
            if not isinstance(market_list, list):
                logger.error(f"Resposta não é uma lista: {type(market_list)}")
                return []
            
            for market_raw in market_list:
                try:
                    market = self._parse_market(market_raw)
                    if market:
                        markets.append(market)
                except Exception as e:
                    logger.debug(f"Falha ao parsear mercado: {e}")
                    continue
            
            logger.info(f"Encontrados {len(markets)} mercados para '{query}'")
            self._clean_cache()  # Limpa cache se necessário
            return markets
        
        except Exception as e:
            logger.error(f"Erro ao buscar mercados '{query}': {e}")
            return []
    
    def get_market_by_id(self, market_id: str) -> Optional[MarketData]:
        """
        Obtém dados de um mercado específico com cache inteligente
        
        Args:
            market_id: ID do mercado (endereço do contrato)
        
        Returns:
            MarketData ou None se não encontrado
        """
        # Validação
        if not market_id or not isinstance(market_id, str):
            logger.error(f"market_id inválido: {market_id}")
            return None
        
        market_id = market_id.strip()
        
        try:
            # Verifica cache
            if market_id in self.market_cache:
                cached_market = self.market_cache[market_id]
                if not cached_market.is_stale(MARKET_CACHE_TTL):
                    logger.debug(f"Retornando mercado {market_id} do cache")
                    return cached_market
                else:
                    logger.debug(f"Cache expirado para {market_id}")
            
            # Faz requisição com retry
            url = f"{POLYMARKET_REST_API}/markets/{market_id}"
            data = self._make_request(
                url,
                fallback_url=f"{POLYMARKET_GAMMA_API}/markets/{market_id}"
            )
            
            if not data:
                logger.warning(f"Mercado não encontrado: {market_id}")
                return None
            
            # Parse e cache
            market = self._parse_market(data)
            
            if market:
                self.market_cache[market_id] = market
                self.cache_timestamp[market_id] = datetime.now()
                self._clean_cache()
            
            return market
        
        except Exception as e:
            logger.error(f"Erro ao obter mercado {market_id}: {e}")
            # Tenta retornar do cache mesmo expirado em caso de erro
            return self.market_cache.get(market_id)
    
    def get_spread(self, market_id: str, default: float = 0.03) -> float:
        """
        Obtém o spread (bid-ask) de um mercado com fallback
        
        Args:
            market_id: ID do mercado
            default: Spread padrão se não conseguir obter (ex: 0.03 = 3%)
        
        Returns:
            Spread em percentual (ex: 0.02 = 2%), ou default se falha
        """
        if not market_id:
            return default
        
        try:
            market = self.get_market_by_id(market_id)
            if market and 0.0 <= market.spread <= 1.0:
                return market.spread
            
            logger.warning(f"Spread inválido para {market_id}, usando default {default}")
            return default
        
        except Exception as e:
            logger.error(f"Erro ao obter spread para {market_id}: {e}")
            return default
    
    def get_order_book(self, market_id: str, outcome: int) -> Dict:
        """
        Obtém o order book (bid/ask) para um resultado específico
        
        Args:
            market_id: ID do mercado
            outcome: 0 (NO) ou 1 (YES)
        
        Returns:
            {
                'bids': [(price, amount), ...],  # Ordenado por preço DESC
                'asks': [(price, amount), ...],  # Ordenado por preço ASC
                'best_bid': float,
                'best_ask': float,
                'spread': float (0-1),
                'spread_percent': float,
                'is_valid': bool
            }
        """
        default_response = {
            'bids': [],
            'asks': [],
            'best_bid': 0.0,
            'best_ask': 1.0,
            'spread': 1.0,
            'spread_percent': 100.0,
            'is_valid': False
        }
        
        # Validações
        if not market_id or not isinstance(market_id, str):
            logger.error(f"market_id inválido: {market_id}")
            return default_response
        
        if outcome not in (0, 1):
            logger.error(f"outcome inválido: {outcome}. Deve ser 0 ou 1")
            return default_response
        
        try:
            url = f"{POLYMARKET_API_BASE}/order-books"
            params = {
                "market": market_id,
                "outcome": outcome
            }
            
            data = self._make_request(
                url,
                params=params,
                fallback_url=f"{POLYMARKET_GAMMA_API}/order-books"
            )
            
            if not data:
                logger.warning(f"Nenhum order book encontrado para {market_id}:{outcome}")
                return default_response
            
            # Parse com validações
            bids = []
            asks = []
            
            for b in data.get("bids", []):
                try:
                    if isinstance(b, (list, tuple)) and len(b) >= 2:
                        price, amount = float(b[0]), float(b[1])
                        if 0 <= price <= 1 and amount > 0:
                            bids.append((price, amount))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Bid inválido: {b} ({e})")
                    continue
            
            for a in data.get("asks", []):
                try:
                    if isinstance(a, (list, tuple)) and len(a) >= 2:
                        price, amount = float(a[0]), float(a[1])
                        if 0 <= price <= 1 and amount > 0:
                            asks.append((price, amount))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Ask inválido: {a} ({e})")
                    continue
            
            # Calcula best bid/ask com segurança
            best_bid = bids[0][0] if bids else 0.0
            best_ask = asks[0][0] if asks else 1.0
            
            # Validações finais
            if best_bid < 0 or best_bid > 1:
                logger.warning(f"best_bid fora do range: {best_bid}")
                best_bid = 0.0
            
            if best_ask < 0 or best_ask > 1:
                logger.warning(f"best_ask fora do range: {best_ask}")
                best_ask = 1.0
            
            if best_bid > best_ask:
                logger.warning(f"best_bid > best_ask ({best_bid} > {best_ask}), invertendo")
                best_bid, best_ask = best_ask, best_bid
            
            spread = best_ask - best_bid
            spread_percent = (spread / best_bid * 100) if best_bid > 0 else 100.0
            
            return {
                'bids': bids,
                'asks': asks,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_percent': spread_percent,
                'is_valid': True
            }
        
        except Exception as e:
            logger.error(f"Erro ao obter order book para {market_id}:{outcome}: {e}")
            return default_response
    
    def get_arbitrage_opportunity(
        self,
        market_id: str,
        estimated_fee: float = 0.02
    ) -> Optional[Dict]:
        """
        Analisa oportunidade de arbitrage em um mercado com validações
        
        Args:
            market_id: ID do mercado
            estimated_fee: Taxa esperada (ex: 0.02 = 2%)
        
        Returns:
            {
                'market_id': str,
                'question': str,
                'outcome': int,
                'spread': float,
                'net_profit_percent': float,  # spread - fee
                'is_profitable': bool,
                'confidence': float,  # 0-1, baseado em volume/liquidity
                'details': str,
                'volume_24h': float,
                'liquidity': float
            } ou None
        """
        if not market_id:
            return None
        
        if not 0 <= estimated_fee <= 1:
            logger.warning(f"Fee inválida: {estimated_fee}, usando 0.02")
            estimated_fee = 0.02
        
        try:
            market = self.get_market_by_id(market_id)
            if not market:
                return None
            
            # Analisa ambos os lados com retry
            book_yes = self.get_order_book(market_id, 1)
            book_no = self.get_order_book(market_id, 0)
            
            if not (book_yes.get('is_valid') and book_no.get('is_valid')):
                logger.warning(f"Order books inválidos para {market_id}")
                return None
            
            spread_yes = (book_yes.get('spread_percent', 0.0) or 0) / 100.0
            spread_no = (book_no.get('spread_percent', 0.0) or 0) / 100.0
            
            # Calcula lucro esperado após taxa
            net_profit_yes = spread_yes - estimated_fee
            net_profit_no = spread_no - estimated_fee
            
            # Determina melhor oportunidade
            if net_profit_yes > net_profit_no:
                best_outcome = 1
                net_profit = net_profit_yes
                spread = spread_yes
            else:
                best_outcome = 0
                net_profit = net_profit_no
                spread = spread_no
            
            is_profitable = net_profit > 0.001  # Threshold mínimo
            
            # Calcula confiança baseada em volume/liquidity
            min_liquidity = 1000  # $1000
            confidence = min(1.0, market.liquidity / min_liquidity) if market.liquidity > 0 else 0.5
            
            return {
                'market_id': market_id,
                'question': market.question,
                'category': market.category,
                'outcome': best_outcome,  # 0=NO, 1=YES
                'spread': max(0, spread),
                'fee': estimated_fee,
                'net_profit_percent': max(0, net_profit),
                'is_profitable': is_profitable,
                'confidence': confidence,  # 0-1
                'details': f"Spread: {max(0, spread):.2%}, Fee: {estimated_fee:.2%}, Net: {max(0, net_profit):.2%}",
                'volume_24h': market.volume_24h,
                'liquidity': market.liquidity,
                'last_updated': market.last_updated.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Erro ao analisar arbitrage para {market_id}: {e}")
            return None
    
    def _parse_market(self, market_data: dict) -> Optional[MarketData]:
        """
        Converte resposta da API em MarketData com validações robustas
        
        Args:
            market_data: Raw market data from API
        
        Returns:
            MarketData validado ou None se inválido
        """
        try:
            # Validação inicial
            if not isinstance(market_data, dict):
                logger.debug(f"market_data não é dict: {type(market_data)}")
                return None
            
            # Extrai e valida ID
            market_id = market_data.get("id") or market_data.get("address")
            if not market_id:
                logger.debug("market_id não encontrado no mercado")
                return None
            
            market_id = str(market_id).strip()
            
            # Extrai question
            question = str(market_data.get("question", "Unknown")).strip()
            if not question or len(question) < 3:
                logger.debug(f"Question inválida: {question}")
                return None
            
            # Extrai category
            category = str(market_data.get("category", "default")).lower().strip()
            
            # Parse outcomes com validação
            # A API real da Polymarket retorna "outcomes" e "outcomePrices" como
            # strings JSON separadas (ex: '["Yes","No"]' e '["0.53","0.47"]'),
            # não como lista de objetos {name, probability}. Tratamos os dois formatos.
            outcomes = {}
            outcomes_raw = market_data.get("outcomes", [])
            prices_raw = market_data.get("outcomePrices", [])
            
            try:
                if isinstance(outcomes_raw, str):
                    outcomes_raw = json.loads(outcomes_raw)
                if isinstance(prices_raw, str):
                    prices_raw = json.loads(prices_raw)
            except (json.JSONDecodeError, TypeError):
                outcomes_raw, prices_raw = [], []
            
            if isinstance(outcomes_raw, list) and isinstance(prices_raw, list) and len(outcomes_raw) == len(prices_raw):
                # Formato real da API: nomes e preços em arrays paralelos
                for name, price in zip(outcomes_raw, prices_raw):
                    try:
                        name = str(name).strip()
                        prob = float(price)
                        if name and 0 <= prob <= 1:
                            outcomes[name] = prob
                    except (ValueError, TypeError):
                        continue
            elif isinstance(outcomes_raw, list):
                # Formato alternativo: lista de objetos {name, probability}
                for outcome in outcomes_raw:
                    try:
                        if isinstance(outcome, dict):
                            name = str(outcome.get("name", "")).strip()
                            prob = float(outcome.get("probability", 0.5))
                            if name and 0 <= prob <= 1:
                                outcomes[name] = prob
                    except (ValueError, TypeError):
                        continue
            
            # Extrai spread: usa o campo direto da API quando disponível (mais preciso),
            # senão estima pela diferença entre probabilidades dos outcomes
            try:
                if "spread" in market_data:
                    spread = float(market_data.get("spread", 0.02))
                elif outcomes and len(outcomes) >= 2:
                    probs = list(outcomes.values())
                    spread = max(0, abs(max(probs) - min(probs)))
                else:
                    spread = 0.02  # Default
            except (ValueError, TypeError):
                spread = 0.02
            
            # Extrai volume e liquidity com validação
            # NOTA: campo real da API é "volume24hr" (não "volume24h")
            try:
                volume_24h = float(market_data.get("volume24hr", market_data.get("volume24h", 0)))
                liquidity = float(market_data.get("liquidity", 0))
            except (ValueError, TypeError):
                volume_24h = 0.0
                liquidity = 0.0
            
            # Tenta criar MarketData (falha se validações falharem)
            market = MarketData(
                market_id=market_id,
                question=question,
                category=category,
                outcomes=outcomes,
                spread=min(1.0, spread),  # Clamp to [0, 1]
                volume_24h=max(0, volume_24h),
                liquidity=max(0, liquidity),
                last_updated=datetime.now()
            )
            
            return market
        
        except ValueError as e:
            logger.debug(f"Validação falhou ao parsear mercado: {e}")
            return None
        except Exception as e:
            logger.debug(f"Erro ao parsear mercado: {e}")
            return None


    def health_check(self) -> bool:
        """
        Verifica saúde da conexão com Polymarket API
        
        Returns:
            True se API respondeu, False caso contrário
        """
        try:
            url = f"{POLYMARKET_REST_API}/health"
            data = self._make_request(url, fallback_url=f"{POLYMARKET_GAMMA_API}/health")
            return data is not None
        except Exception as e:
            logger.warning(f"Health check falhou: {e}")
            return False


# Instância global com lazy initialization
_polymarket_api = None

def get_polymarket_api() -> PolymarketAPI:
    """Retorna instância singleton do PolymarketAPI"""
    global _polymarket_api
    if _polymarket_api is None:
        _polymarket_api = PolymarketAPI()
    return _polymarket_api

# Alias para compatibilidade
polymarket_api = get_polymarket_api()

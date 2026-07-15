"""
Testes para o módulo polymarket_api.py

Execute com:
    python -m pytest tests/test_polymarket_api.py -v
"""

import pytest
from datetime import datetime
from bot.polymarket_api import (
    MarketData,
    PolymarketAPI,
    get_polymarket_api
)


class TestMarketData:
    """Testes da dataclass MarketData"""
    
    def test_valid_market_data(self):
        """Testa criação de MarketData válido"""
        market = MarketData(
            market_id="0xabc123",
            question="Will Bitcoin reach $100k?",
            category="crypto",
            spread=0.05,
            volume_24h=50000,
            liquidity=10000
        )
        assert market.market_id == "0xabc123"
        assert market.spread == 0.05
        assert not market.is_stale()
    
    def test_invalid_market_id(self):
        """Testa rejeição de market_id inválido"""
        with pytest.raises(ValueError):
            MarketData(
                market_id="",  # Inválido
                question="Test",
                category="test"
            )
    
    def test_invalid_question(self):
        """Testa rejeição de question inválida"""
        with pytest.raises(ValueError):
            MarketData(
                market_id="0xabc123",
                question="",  # Inválido
                category="test"
            )
    
    def test_spread_validation(self):
        """Testa validação de spread"""
        # Spread > 1 deve gerar warning
        market = MarketData(
            market_id="0xabc123",
            question="Test?",
            category="test",
            spread=1.5  # Fora do range esperado
        )
        # Não deve falhar, apenas warn
        assert market.spread == 1.5
    
    def test_is_stale(self):
        """Testa verificação de staleness"""
        market = MarketData(
            market_id="0xabc123",
            question="Test?",
            category="test"
        )
        # Acaba de ser criado
        assert not market.is_stale(max_age_seconds=60)
        
        # Mais de 1s atrás
        assert market.is_stale(max_age_seconds=0)


class TestPolymarketAPI:
    """Testes da classe PolymarketAPI"""
    
    @pytest.fixture
    def api(self):
        """Fixture que retorna instância da API"""
        return PolymarketAPI()
    
    def test_initialization(self, api):
        """Testa inicialização da API"""
        assert api.market_cache == {}
        assert api.cache_timestamp == {}
    
    def test_singleton(self):
        """Testa que get_polymarket_api retorna singleton"""
        api1 = get_polymarket_api()
        api2 = get_polymarket_api()
        assert api1 is api2
    
    def test_clean_cache_removes_old_entries(self, api):
        """Testa que _clean_cache remove entradas antigas"""
        # Popula cache além do limite
        from bot.polymarket_api import MAX_CACHE_SIZE
        
        for i in range(MAX_CACHE_SIZE + 10):
            market = MarketData(
                market_id=f"0x{i:04d}",
                question=f"Test {i}?",
                category="test"
            )
            api.market_cache[f"key_{i}"] = market
        
        original_size = len(api.market_cache)
        api._clean_cache()
        
        # Deve ter removido ~10% das antigas
        assert len(api.market_cache) < original_size
        assert len(api.market_cache) <= MAX_CACHE_SIZE
    
    def test_parse_market_valid(self, api):
        """Testa parsing de market data válido"""
        raw_data = {
            "id": "0xabc123",
            "question": "Will Bitcoin reach $100k?",
            "category": "crypto",
            "outcomes": [
                {"name": "YES", "probability": 0.65},
                {"name": "NO", "probability": 0.35}
            ],
            "volume24h": 50000,
            "liquidity": 10000
        }
        
        market = api._parse_market(raw_data)
        
        assert market is not None
        assert market.market_id == "0xabc123"
        assert market.category == "crypto"
        assert len(market.outcomes) == 2
        assert market.volume_24h == 50000
    
    def test_parse_market_invalid_id(self, api):
        """Testa parsing com ID inválido"""
        raw_data = {
            "id": "",  # Inválido
            "question": "Test?",
            "category": "test"
        }
        
        market = api._parse_market(raw_data)
        assert market is None
    
    def test_parse_market_invalid_question(self, api):
        """Testa parsing com question inválida"""
        raw_data = {
            "id": "0xabc123",
            "question": "",  # Inválido
            "category": "test"
        }
        
        market = api._parse_market(raw_data)
        assert market is None
    
    def test_parse_market_missing_fields(self, api):
        """Testa parsing com campos faltantes"""
        raw_data = {
            "id": "0xabc123",
            "question": "Test?"
            # Faltam category, outcomes, etc
        }
        
        market = api._parse_market(raw_data)
        
        assert market is not None
        assert market.category == "default"  # Default
        assert len(market.outcomes) == 0  # Nenhum outcome
    
    def test_get_spread_with_valid_data(self, api):
        """Testa get_spread com dados válidos"""
        # Mock de market data
        market = MarketData(
            market_id="0xabc123",
            question="Test?",
            category="test",
            spread=0.03
        )
        api.market_cache["0xabc123"] = market
        
        spread = api.get_spread("0xabc123")
        assert spread == 0.03
    
    def test_get_spread_with_invalid_data(self, api):
        """Testa get_spread com dados inválidos"""
        # Market inexistente
        spread = api.get_spread("0xinvalid", default=0.05)
        assert spread == 0.05
    
    def test_order_book_validation(self, api):
        """Testa validações de order book"""
        # Teste com market_id inválido
        book = api.get_order_book("", 1)
        assert book['is_valid'] is False
        
        # Teste com outcome inválido
        book = api.get_order_book("0xabc123", 99)
        assert book['is_valid'] is False


class TestIntegration:
    """Testes de integração (requerem conexão com API)"""
    
    @pytest.mark.integration
    def test_health_check(self):
        """Testa health check da API (requer internet)"""
        api = PolymarketAPI()
        # Pode falhar se API está fora ou sem conexão
        # Apenas loga warning, não falha
        health = api.health_check()
        assert isinstance(health, bool)
    
    @pytest.mark.integration
    def test_search_markets_real(self):
        """Testa busca real de mercados (requer internet)"""
        api = PolymarketAPI()
        markets = api.search_markets("Bitcoin", limit=5)
        
        # Pode retornar vazio se conexão falhar
        assert isinstance(markets, list)
        
        if markets:
            market = markets[0]
            assert isinstance(market, MarketData)
            assert market.market_id
            assert market.question


# Executar testes unitários (sem integração) com:
# pytest tests/test_polymarket_api.py -v -m "not integration"

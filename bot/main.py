import logging
import time
import sys
import os
from datetime import datetime

# Adiciona parent dir ao path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    INTERVALO,
    SCORE_LIMIAR,
    MERCADOS,
    MAX_ERROS_CONSECUTIVOS,
    PAUSA_APOS_ERROS,
    MAX_ERROS_TOTAL,
    PAUSA_APOS_MUITOS_ERROS,
    LOG_DIR,
    LOG_FILE,
)
from sentiment import SentimentAnalyzer
from executor import ContractExecutor
from database.db import db, calculate_metrics, get_latest_metrics

# ===== LOGGING =====
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class SentinelBot:
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.executor = ContractExecutor()
        self.erros_consecutivos = 0
        self.total_erros = 0
        self.ultima_execucao = None
        self.paused = False
        self.pause_until = None
        
        logger.info("=" * 80)
        logger.info("SENTINEL ARBITRAGE BOT INICIALIZADO")
        logger.info(f"Mercados: {MERCADOS}")
        logger.info(f"Intervalo: {INTERVALO}s")
        logger.info(f"Score Limiar: {SCORE_LIMIAR}")
        logger.info("=" * 80)
    
    def healthcheck(self) -> bool:
        """Verifica saúde do bot"""
        try:
            # Verifica conexão blockchain
            if not self.executor.is_connected():
                logger.error("Bot desconectado do blockchain")
                return False
            
            logger.debug("Healthcheck: OK")
            return True
        except Exception as e:
            logger.error(f"Healthcheck falhou: {e}")
            return False
    
    def handle_error(self, error_message: str):
        """Trata erros com circuit breaker"""
        self.erros_consecutivos += 1
        self.total_erros += 1
        
        logger.error(f"[Erro #{self.total_erros}] {error_message}")
        logger.warning(f"Erros consecutivos: {self.erros_consecutivos}/{MAX_ERROS_CONSECUTIVOS}")
        
        # Circuit breaker após muitos erros consecutivos
        if self.erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
            self.paused = True
            self.pause_until = time.time() + PAUSA_APOS_ERROS
            logger.warning(f"⚠️ BOT PAUSADO por {PAUSA_APOS_ERROS}s (muitos erros consecutivos)")
        
        # Pausa longa após muitos erros totais
        if self.total_erros >= MAX_ERROS_TOTAL:
            self.paused = True
            self.pause_until = time.time() + PAUSA_APOS_MUITOS_ERROS
            logger.critical(f"🛑 BOT PAUSADO por {PAUSA_APOS_MUITOS_ERROS}s (limite de erros atingido)")
    
    def reset_errors(self):
        """Reseta contador de erros após execução bem-sucedida"""
        if self.erros_consecutivos > 0:
            logger.info(f"✓ Erros consecutivos resetados ({self.erros_consecutivos} → 0)")
        self.erros_consecutivos = 0
    
    def check_pause(self):
        """Verifica se bot deve estar pausado"""
        if self.paused:
            time_left = max(0, self.pause_until - time.time())
            if time_left > 0:
                logger.warning(f"Bot está pausado. Retoma em {time_left:.0f}s")
                time.sleep(min(10, time_left))  # Dorme 10s ou menos
                return True
            else:
                self.paused = False
                logger.info("✓ Bot retomado após pausa")
                self.erros_consecutivos = 0
        return False
    
    def analyze_markets(self) -> dict:
        """Analisa sentimento de todos os mercados"""
        try:
            logger.info(f"Analisando {len(MERCADOS)} mercados...")
            sentiments = self.sentiment_analyzer.analyze_all_markets()
            
            logger.info(f"Análise completa:")
            for term, score in sentiments.items():
                signal = "📈 BUY" if score > SCORE_LIMIAR else ("📉 SELL" if score < -SCORE_LIMIAR else "➡️ HOLD")
                logger.info(f"  {term}: {score:+.3f} [{signal}]")
            
            self.reset_errors()
            return sentiments
        except Exception as e:
            self.handle_error(f"Erro ao analisar mercados: {e}")
            return {}
    
    def execute_trades(self, sentiments: dict):
        """Executa trades baseado em sentimentos com consideração de taxas dinâmicas"""
        executed = 0
        
        for term, score in sentiments.items():
            try:
                # Detecta categoria e calcula taxas
                fee_taker, _ = self.executor.get_category_fee(term)
                
                # BUY (YES) - sentimento positivo
                if score > SCORE_LIMIAR:
                    logger.info(f"🟢 Sinal de COMPRA para {term} (score: {score:+.3f}, taxa: {fee_taker}%)")
                    # Aqui você integraria com o Polymarket para obter endereço do mercado
                    # Por enquanto, apenas simula
                    success, tx_hash = self.executor.execute_arbitrage(
                        market="0x" + "0" * 40,  # Placeholder - usar endereço real
                        outcome=1,  # YES
                        sentiment_score=score,
                        estimated_spread=0.05,
                        market_name=term  # Passa nome para detectar categoria e taxas
                    )
                    
                    if success:
                        executed += 1
                        logger.info(f"✓ Trade BUY executado: {tx_hash}")
                    else:
                        logger.warning(f"✗ Trade BUY falhou: {tx_hash}")
                
                # SELL (NO) - sentimento negativo
                elif score < -SCORE_LIMIAR:
                    logger.info(f"🔴 Sinal de VENDA para {term} (score: {score:+.3f}, taxa: {fee_taker}%)")
                    success, tx_hash = self.executor.execute_arbitrage(
                        market="0x" + "0" * 40,  # Placeholder - usar endereço real
                        outcome=0,  # NO
                        sentiment_score=score,
                        estimated_spread=0.05,
                        market_name=term  # Passa nome para detectar categoria e taxas
                    )
                    
                    if success:
                        executed += 1
                        logger.info(f"✓ Trade SELL executado: {tx_hash}")
                    else:
                        logger.warning(f"✗ Trade SELL falhou: {tx_hash}")
            
            except Exception as e:
                self.handle_error(f"Erro ao executar trade para {term}: {e}")
        
        if executed > 0:
            self.reset_errors()
            return True
        
        return False
    
    def print_status(self):
        """Imprime status do bot"""
        metrics = calculate_metrics()
        
        logger.info("=" * 80)
        logger.info("STATUS DO BOT")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Última execução: {self.ultima_execucao or 'Nunca'}")
        logger.info(f"Erros consecutivos: {self.erros_consecutivos}/{MAX_ERROS_CONSECUTIVOS}")
        logger.info(f"Total erros: {self.total_erros}/{MAX_ERROS_TOTAL}")
        logger.info("")
        logger.info("MÉTRICAS")
        logger.info(f"  Lucro hoje: ${metrics.get('lucro_dia', 0):.2f}")
        logger.info(f"  Operações hoje: {metrics.get('ops_dia', 0)}")
        logger.info(f"  Lucro total: ${metrics.get('lucro_total', 0):.2f}")
        logger.info(f"  Total operações: {metrics.get('ops_total', 0)}")
        logger.info("=" * 80)
    
    def run(self):
        """Loop principal do bot"""
        logger.info("Iniciando loop principal...")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                
                # Verifica pausa
                if self.check_pause():
                    continue
                
                # Healthcheck
                if not self.healthcheck():
                    self.handle_error("Healthcheck falhou")
                    time.sleep(INTERVALO)
                    continue
                
                logger.info(f"\n{'='*80}")
                logger.info(f"ITERAÇÃO #{iteration} - {datetime.now().isoformat()}")
                logger.info(f"{'='*80}")
                
                # Analisa mercados
                sentiments = self.analyze_markets()
                
                if not sentiments:
                    self.handle_error("Análise de mercados retornou vazio")
                    time.sleep(INTERVALO)
                    continue
                
                # Executa trades
                self.execute_trades(sentiments)
                
                self.ultima_execucao = datetime.now()
                
                # Imprime status a cada 10 iterações
                if iteration % 10 == 0:
                    self.print_status()
                
                # Aguarda próximo intervalo
                logger.info(f"Aguardando {INTERVALO}s até próxima iteração...")
                time.sleep(INTERVALO)
        
        except KeyboardInterrupt:
            logger.info("\n\n🛑 BOT INTERROMPIDO PELO USUÁRIO")
            self.print_status()
        except Exception as e:
            logger.critical(f"❌ ERRO CRÍTICO: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    bot = SentinelBot()
    bot.run()

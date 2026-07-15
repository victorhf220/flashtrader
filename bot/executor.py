import logging
import json
from typing import Tuple
from web3 import Web3
from eth_account import Account

from config import (
    POLYGON_RPC,
    POLYGON_RPC_BACKUP,
    PRIVATE_KEY,
    CONTRACT_ADDRESS,
    CAPITAL_POR_OP,
    SPREAD_MINIMO,
    DRY_RUN,
)
from database.db import save_operation

logger = logging.getLogger(__name__)

# ABI do contrato FlashTrader (simplificado)
FLASH_TRADER_ABI = json.loads('''[
    {
        "type": "function",
        "name": "executeArbitrage",
        "inputs": [
            {"name": "market", "type": "address"},
            {"name": "outcome", "type": "uint256"},
            {"name": "flashAmount", "type": "uint256"},
            {"name": "minProfit", "type": "uint256"}
        ],
        "outputs": [],
        "stateMutability": "nonpayable"
    },
    {
        "type": "function",
        "name": "getStats",
        "inputs": [],
        "outputs": [
            {"name": "operations", "type": "uint256"},
            {"name": "totalProfitAccumulated", "type": "uint256"},
            {"name": "lastProfitAmount", "type": "uint256"}
        ],
        "stateMutability": "view"
    }
]''')

class ContractExecutor:
    def __init__(self):
        self.w3 = self._init_web3()
        self.account = Account.from_key(PRIVATE_KEY) if PRIVATE_KEY else None
        self.contract = self._load_contract()
        self.nonce_cache = None
        
    def _init_web3(self) -> Web3:
        """Inicializa conexão Web3 com fallback"""
        try:
            w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
            if w3.is_connected():
                logger.info(f"Conectado ao Polygon RPC: {POLYGON_RPC}")
                return w3
        except Exception as e:
            logger.warning(f"Erro ao conectar ao RPC primário: {e}")
        
        try:
            w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_BACKUP))
            if w3.is_connected():
                logger.info(f"Conectado ao Polygon RPC backup: {POLYGON_RPC_BACKUP}")
                return w3
        except Exception as e:
            logger.error(f"Erro ao conectar ao RPC backup: {e}")
        
        raise RuntimeError("Não foi possível conectar a nenhum RPC")
    
    def _load_contract(self):
        """Carrega instância do contrato"""
        if not CONTRACT_ADDRESS or not self.account:
            logger.warning("Contrato ou conta não configurados")
            return None
        
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(CONTRACT_ADDRESS),
                abi=FLASH_TRADER_ABI
            )
            logger.info(f"Contrato carregado: {CONTRACT_ADDRESS}")
            return contract
        except Exception as e:
            logger.error(f"Erro ao carregar contrato: {e}")
            return None
    
    def _estimate_gas(self, tx: dict) -> int:
        """Estima gas com margem de segurança"""
        try:
            estimate = self.w3.eth.estimate_gas(tx)
            # Adiciona 20% de margem
            return int(estimate * 1.2)
        except Exception as e:
            logger.warning(f"Erro ao estimar gas: {e}, usando 500000 como fallback")
            return 500000
    
    def _get_gas_price(self) -> Tuple[int, int]:
        """Obtém base fee e maxPriorityFeePerGas (EIP-1559)"""
        try:
            gas_price = self.w3.eth.gas_price
            block = self.w3.eth.get_block('latest')
            base_fee = block.get('baseFeePerGas', gas_price)
            max_priority_fee = self.w3.to_wei(1, 'gwei')  # 1 GWEI de prioridade
            max_fee = (base_fee * 2) + max_priority_fee
            return max_fee, max_priority_fee
        except Exception as e:
            logger.warning(f"Erro ao obter gas price: {e}")
            return self.w3.to_wei(50, 'gwei'), self.w3.to_wei(2, 'gwei')
    
    def execute_arbitrage(
        self,
        market: str,
        outcome: int,
        sentiment_score: float,
        estimated_spread: float = 0.05,
    ) -> Tuple[bool, str]:
        """
        Executa arbitrage via flash loan
        
        Args:
            market: Endereço do mercado Polymarket
            outcome: 0 = NO, 1 = YES
            sentiment_score: Score agregado de sentimento
            estimated_spread: Spread estimado entre compra e venda
        
        Returns:
            (success, tx_hash ou erro_message)
        """
        
        if DRY_RUN:
            logger.info(f"[DRY RUN] Arbitrage seria executado:")
            logger.info(f"  Market: {market}")
            logger.info(f"  Outcome: {outcome}")
            logger.info(f"  Sentiment: {sentiment_score:.3f}")
            logger.info(f"  Capital: ${CAPITAL_POR_OP}")
            
            # Simula sucesso
            estimated_profit = CAPITAL_POR_OP * estimated_spread * 0.8  # 80% do spread
            
            save_operation(
                termo=market,
                direction="YES" if outcome == 1 else "NO",
                score=sentiment_score,
                lucro=estimated_profit,
                status="DRY_RUN",
                detalhes=f"Spread estimado: {estimated_spread:.2%}, Lucro estimado: ${estimated_profit:.2f}"
            )
            
            return True, "DRY_RUN_SUCCESS"
        
        # Validações
        if not self.contract or not self.account:
            error = "Contrato ou conta não configurados"
            logger.error(error)
            save_operation(market, "YES" if outcome == 1 else "NO", sentiment_score, 0, "ERROR", error)
            return False, error
        
        if estimated_spread < SPREAD_MINIMO:
            error = f"Spread insuficiente: {estimated_spread:.2%} < {SPREAD_MINIMO:.2%}"
            logger.warning(error)
            return False, error
        
        try:
            # Calcula profit mínimo esperado
            estimated_profit = CAPITAL_POR_OP * estimated_spread * 0.7  # 70% do spread (após fees)
            min_profit = int(estimated_profit * 0.9)  # 90% do estimado como mínimo
            
            # Prepara transação
            market_checksum = Web3.to_checksum_address(market)
            
            tx_data = self.contract.functions.executeArbitrage(
                market_checksum,
                outcome,
                self.w3.to_wei(CAPITAL_POR_OP, 'mwei'),  # USDC usa 6 decimals (mwei)
                min_profit
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'chainId': 137,  # Polygon mainnet
            })
            
            # Adiciona gas otimizado (EIP-1559)
            max_fee, max_priority_fee = self._get_gas_price()
            tx_data['maxFeePerGas'] = max_fee
            tx_data['maxPriorityFeePerGas'] = max_priority_fee
            tx_data['gas'] = self._estimate_gas(tx_data)
            
            logger.info(f"Transação preparada: {json.dumps({
                'market': market,
                'outcome': outcome,
                'capital': CAPITAL_POR_OP,
                'minProfit': min_profit,
                'gas': tx_data['gas'],
                'maxFeePerGas': self.w3.from_wei(max_fee, 'gwei')
            }, indent=2)}")
            
            # Assina transação
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, PRIVATE_KEY)
            
            # Envia transação
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Transação enviada: {tx_hash_hex}")
            
            # Aguarda confirmação (máximo 60 segundos)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                
                if receipt.get('status') == 1:  # 1 = sucesso
                    logger.info(f"Transação confirmada com sucesso!")
                    
                    save_operation(
                        termo=market,
                        direction="YES" if outcome == 1 else "NO",
                        score=sentiment_score,
                        lucro=estimated_profit,
                        status="SUCCESS",
                        detalhes=f"TxHash: {tx_hash_hex}, GasUsed: {receipt['gasUsed']}"
                    )
                    
                    return True, tx_hash_hex
                else:
                    error = f"Transação falhou (status 0): {tx_hash_hex}"
                    logger.error(error)
                    
                    save_operation(
                        termo=market,
                        direction="YES" if outcome == 1 else "NO",
                        score=sentiment_score,
                        lucro=0,
                        status="FAILED",
                        detalhes=error
                    )
                    
                    return False, error
            except Exception as e:
                # Timeout ou erro ao aguardar confirmação
                logger.warning(f"Erro ao aguardar confirmação: {e}")
                save_operation(
                    termo=market,
                    direction="YES" if outcome == 1 else "NO",
                    score=sentiment_score,
                    lucro=0,
                    status="PENDING",
                    detalhes=f"TxHash: {tx_hash_hex}, Aguardando confirmação..."
                )
                return True, tx_hash_hex  # Consideramos enviado
        
        except Exception as e:
            error = f"Erro ao executar arbitrage: {str(e)}"
            logger.error(error)
            
            save_operation(
                termo=market,
                direction="YES" if outcome == 1 else "NO",
                score=sentiment_score,
                lucro=0,
                status="ERROR",
                detalhes=error
            )
            
            return False, error
    
    def get_contract_stats(self) -> dict:
        """Obtém estatísticas do contrato"""
        try:
            if not self.contract:
                return {}
            
            operations, total_profit, last_profit = self.contract.functions.getStats().call()
            
            return {
                "total_operations": operations,
                "total_profit": self.w3.from_wei(total_profit, 'mwei'),
                "last_profit": self.w3.from_wei(last_profit, 'mwei'),
            }
        except Exception as e:
            logger.error(f"Erro ao obter stats do contrato: {e}")
            return {}
    
    def is_connected(self) -> bool:
        """Verifica se está conectado ao blockchain"""
        try:
            return self.w3.is_connected()
        except:
            return False

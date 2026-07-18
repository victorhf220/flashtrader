#!/usr/bin/env python3
"""
Executor Polymarket via py-clob-client (SDK oficial)

FLUXO:
1. Contrato faz flash loan de USDC da Aave
2. Contrato transfere USDC pra essa classe
3. Essa classe arbitra na Polymarket com py-clob-client
4. Espera settlement
5. Repaga o contrato
"""

import os
import time
import logging
from typing import Optional, Dict, Tuple
from web3 import Web3
from eth_account import Account
from pyclobjson import PolymarketClient

logger = logging.getLogger(__name__)

class PolymarketExecutorHybrid:
    """
    Executa arbitrage na Polymarket usando flash loans da Aave
    """
    
    def __init__(self, private_key: str, contract_address: str, py_bot_wallet: str):
        """
        Args:
            private_key: Sua chave privada (quem assina as ordens)
            contract_address: Endereço do PolymarketFlashLoan.sol
            py_bot_wallet: Carteira Python que recebe o USDC emprestado
        """
        self.private_key = private_key
        self.account = Account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.py_bot_wallet = Web3.to_checksum_address(py_bot_wallet)
        
        # Polymarket CLOB Client (SDK oficial)
        self.polymarket = PolymarketClient(chain_id=137)  # 137 = Polygon
        
        # Web3
        self.w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
        self.w3.middleware_onion.inject(lambda method: lambda params: 
            self.w3.provider.make_request(method, params), layer=0)
        
        # USDC
        self.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        # State
        self.last_opportunity: Optional[Dict] = None
        self.last_flash_loan_amount = 0
        self.orders_placed: Dict[str, str] = {}  # market_id -> order_id
        
    def calculate_order_parameters(
        self, 
        market_id: str,
        outcome: str,  # "YES" ou "NO"
        amount_usdc: float,
        current_price: float
    ) -> Tuple[float, float]:
        """
        Calcula quantas shares comprar e qual o preço limite
        
        Args:
            market_id: ID do mercado na Polymarket
            outcome: "YES" ou "NO"
            amount_usdc: Quanto USDC usar
            current_price: Preço atual do outcome (0-1)
        
        Returns:
            (shares, price_limit)
        """
        # Se preço é 0.30, posso comprar 100/0.30 = 333 shares
        shares = amount_usdc / current_price if current_price > 0 else 0
        
        # Slippage protection: coloca ordem 2% pior que mercado
        # Se comprando YES a 0.30, coloca ordem a 0.32 (pior pra gente)
        slippage_protection = 1.02
        price_limit = current_price * slippage_protection
        
        return shares, min(price_limit, 0.99)  # Cap a 0.99
    
    def request_flash_loan(self, amount_usdc: int) -> bool:
        """
        Solicita flash loan via contrato Solidity
        
        Args:
            amount_usdc: Quantidade em USDC (com 6 decimals, então 3000*1e6)
        
        Returns:
            True se requisição enviada com sucesso
        """
        logger.info(f"📡 Requisitando flash loan de {amount_usdc/1e6:.2f} USDC")
        
        try:
            # ABI do contrato
            contract_abi = [
                {
                    "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
                    "name": "requestFlashLoan",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
            
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=contract_abi
            )
            
            # Prepara transação
            tx = contract.functions.requestFlashLoan(amount_usdc).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
            })
            
            # Assina e envia
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"✅ Flash loan requisitado: {tx_hash.hex()}")
            self.last_flash_loan_amount = amount_usdc
            
            # Aguarda confirmação
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            return receipt.status == 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao requisitar flash loan: {e}")
            return False
    
    async def execute_polymarket_arbitrage(
        self,
        market_id: str,
        outcome: str,  # "YES" ou "NO"
        amount_usdc: float,
        sentiment_score: float
    ) -> Optional[Dict]:
        """
        Executa arbitrage na Polymarket com py-clob-client
        
        Args:
            market_id: ID do mercado
            outcome: "YES" ou "NO"
            amount_usdc: Quantidade em USDC a usar
            sentiment_score: Score de sentimento (para logging)
        
        Returns:
            Dict com resultado ou None se falhou
        """
        logger.info(f"🎯 Iniciando arbitrage Polymarket")
        logger.info(f"   Mercado: {market_id}")
        logger.info(f"   Outcome: {outcome}")
        logger.info(f"   Capital: ${amount_usdc:.2f}")
        logger.info(f"   Sentimento: {sentiment_score:.2f}")
        
        try:
            # 1. Fetch preço e liquidity atual
            market_data = await self.polymarket.get_market(market_id)
            current_price = market_data.get(f"{outcome.lower()}_price", 0)
            
            logger.info(f"   Preço atual {outcome}: {current_price:.2%}")
            
            # 2. Calcula parâmetros da ordem
            shares, price_limit = self.calculate_order_parameters(
                market_id, outcome, amount_usdc, current_price
            )
            
            logger.info(f"   Comprando {shares:.0f} shares a máximo {price_limit:.2%}")
            
            # 3. Assina ordem EIP-712 (py-clob-client faz automaticamente)
            # Tipo: LIMIT order (não market) pra ter controle sobre o preço
            order_result = await self.polymarket.create_order(
                market_id=market_id,
                outcome=outcome,
                shares=shares,
                price=price_limit,
                order_type="LIMIT",
                signer=self.account,  # py-clob-client assina automaticamente
            )
            
            order_id = order_result.get("order_id")
            logger.info(f"✅ Ordem criada: {order_id}")
            
            self.orders_placed[market_id] = order_id
            
            # 4. Aguarda casamento (timeout: 2 minutos)
            logger.info(f"⏳ Aguardando casamento da ordem (max 2 min)...")
            
            start_time = time.time()
            timeout = 120  # 2 minutos
            poll_interval = 5  # Poll a cada 5s
            
            while time.time() - start_time < timeout:
                order_status = await self.polymarket.get_order_status(order_id)
                
                if order_status.get("status") == "FILLED":
                    filled_shares = order_status.get("filled_shares", 0)
                    avg_price = order_status.get("average_price", 0)
                    total_cost = filled_shares * avg_price
                    
                    logger.info(f"✅ Ordem casada!")
                    logger.info(f"   Shares compradas: {filled_shares:.0f}")
                    logger.info(f"   Preço médio: {avg_price:.2%}")
                    logger.info(f"   Custo: ${total_cost:.2f}")
                    
                    return {
                        "status": "filled",
                        "order_id": order_id,
                        "market_id": market_id,
                        "outcome": outcome,
                        "shares": filled_shares,
                        "price": avg_price,
                        "cost": total_cost,
                    }
                
                elif order_status.get("status") == "FAILED":
                    logger.warning(f"❌ Ordem rejeitada")
                    return {"status": "rejected", "order_id": order_id}
                
                # Ainda pending, aguarda
                logger.debug(f"⏳ Ordem ainda pending, aguardando...")
                await asyncio.sleep(poll_interval)
            
            # Timeout
            logger.warning(f"⏱️ Timeout aguardando casamento (2 min)")
            return {"status": "timeout", "order_id": order_id}
        
        except Exception as e:
            logger.error(f"❌ Erro na execução: {e}")
            return None
    
    def repay_flash_loan(self) -> bool:
        """
        Repaga o flash loan para o contrato Solidity
        
        O fluxo é:
        1. Python ganhou lucro na Polymarket
        2. Python volta o USDC emprestado + lucro pra esse endereço
        3. Chama repayFlashLoan() no contrato
        4. Contrato repaga Aave
        5. Contrato extrai lucro pro owner
        """
        logger.info(f"💰 Repagando flash loan...")
        
        try:
            # ABI do contrato
            contract_abi = [
                {
                    "inputs": [],
                    "name": "repayFlashLoan",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
            
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=contract_abi
            )
            
            # Prepara transação
            tx = contract.functions.repayFlashLoan().build_transaction({
                "from": self.py_bot_wallet,  # Python wallet chama
                "gas": 300000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(self.py_bot_wallet),
            })
            
            # Assina com private key do Python
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"✅ Repagamento iniciado: {tx_hash.hex()}")
            
            # Aguarda confirmação
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt.status == 1:
                logger.info(f"✅ Flash loan repagado com sucesso!")
                return True
            else:
                logger.error(f"❌ Transação de repagamento reverteu")
                return False
        
        except Exception as e:
            logger.error(f"❌ Erro ao repagar: {e}")
            return False
    
    async def run_hybrid_arbitrage(
        self,
        market_id: str,
        outcome: str,
        amount_usdc: float,
        sentiment_score: float
    ) -> bool:
        """
        Fluxo completo:
        1. Requisita flash loan
        2. Aguarda USDC ser transferido
        3. Arbitra na Polymarket
        4. Repaga flash loan
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 INICIANDO ARBITRAGE HÍBRIDA")
        logger.info(f"{'='*60}\n")
        
        amount_wei = int(amount_usdc * 1e6)  # USDC tem 6 decimals
        
        # Passo 1: Flash loan
        if not self.request_flash_loan(amount_wei):
            logger.error(f"Flash loan falhou")
            return False
        
        # Passo 2: Aguarda confirmação (o USDC vai ser transferido automaticamente)
        logger.info(f"⏳ Aguardando confirmação do flash loan...")
        await asyncio.sleep(10)  # Espera um pouco pra transação confirmar
        
        # Passo 3: Arbitra na Polymarket
        result = await self.execute_polymarket_arbitrage(
            market_id, outcome, amount_usdc, sentiment_score
        )
        
        if not result or result.get("status") != "filled":
            logger.error(f"Arbitrage falhou ou timeout")
            # TODO: Cancelar ordem se estiver pending
            return False
        
        # Passo 4: Repaga flash loan
        if not self.repay_flash_loan():
            logger.error(f"Repagamento falhou")
            return False
        
        logger.info(f"{'='*60}")
        logger.info(f"✅ ARBITRAGE COMPLETA COM SUCESSO")
        logger.info(f"{'='*60}\n")
        
        return True

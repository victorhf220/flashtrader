"""
dex_executor.py
================

Executor de arbitragem DEX-a-DEX REAL na Polygon (QuickSwap vs SushiSwap),
via flash loan da Aave V3, com submissão opcional protegida pelo FastLane.

Este é o caminho que substitui o fluxo de "arbitragem" com a Polymarket do
executor.py original — aquele fluxo foi documentado como inviável on-chain
em POLYMARKET_ONCHAIN_LIMITACAO.md (a Polymarket não permite compra/venda
atômica via contrato de terceiro). Arbitragem entre AMMs estilo Uniswap V2
é atômica e determinística por natureza, então o padrão flash-loan-arbitrage
funciona de verdade aqui.

Requisitos para rodar em modo LIVE (DRY_RUN=false):
    1. Deployar contracts/DexArbitrage.sol na Polygon mainnet e configurar
       DEX_ARBITRAGE_CONTRACT_ADDRESS no .env
    2. Ter capital em USDC.e na própria carteira do bot NÃO é necessário
       (o capital vem do flash loan) — mas a carteira precisa de MATIC/POL
       para pagar gas (ou lance do FastLane).
    3. Validar em DRY_RUN e/ou testnet (Amoy) antes de operar com o contrato
       real na mainnet.
"""

import json
import logging
from typing import Optional, Tuple

from web3 import Web3

from config import (
    DEX_ARBITRAGE_CONTRACT_ADDRESS,
    QUICKSWAP_ROUTER,
    SUSHISWAP_ROUTER,
    USDC_ADDRESS,
    WPOL_ADDRESS,
    DEX_SPREAD_MINIMO,
    CAPITAL_POR_OP,
    DRY_RUN,
)
from database.db import save_operation

logger = logging.getLogger(__name__)

# ABI real, gerado a partir da compilação de contracts/DexArbitrage.sol
# (solc 0.8.19, com as interfaces oficiais da Aave V3 — não é um ABI
# hipotético/simplificado). Ver contracts/DexArbitrage.abi.json.
DEX_ARBITRAGE_ABI = json.loads('''[{"inputs": [{"internalType": "address", "name": "provider", "type": "address"}], "stateMutability": "nonpayable", "type": "constructor"}, {"anonymous": false, "inputs": [{"indexed": true, "internalType": "address", "name": "tokenBorrowed", "type": "address"}, {"indexed": false, "internalType": "uint256", "name": "flashAmount", "type": "uint256"}, {"indexed": false, "internalType": "uint256", "name": "profit", "type": "uint256"}, {"indexed": false, "internalType": "address", "name": "routerBuy", "type": "address"}, {"indexed": false, "internalType": "address", "name": "routerSell", "type": "address"}], "name": "ArbitrageExecuted", "type": "event"}, {"anonymous": false, "inputs": [{"indexed": true, "internalType": "address", "name": "owner", "type": "address"}, {"indexed": true, "internalType": "address", "name": "token", "type": "address"}, {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "ProfitWithdrawn", "type": "event"}, {"inputs": [], "name": "ADDRESSES_PROVIDER", "outputs": [{"internalType": "contract IPoolAddressesProvider", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name": "OWNER", "outputs": [{"internalType": "address", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name": "POOL", "outputs": [{"internalType": "contract IPool", "name": "", "type": "address"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "address", "name": "token", "type": "address"}], "name": "emergencyWithdraw", "outputs": [], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "uint256", "name": "flashAmount", "type": "uint256"}, {"components": [{"internalType": "address", "name": "tokenBorrowed", "type": "address"}, {"internalType": "address", "name": "tokenIntermediate", "type": "address"}, {"internalType": "address", "name": "routerBuy", "type": "address"}, {"internalType": "address", "name": "routerSell", "type": "address"}, {"internalType": "uint256", "name": "minProfit", "type": "uint256"}, {"internalType": "uint256", "name": "amountOutMinBuy", "type": "uint256"}, {"internalType": "uint256", "name": "amountOutMinSell", "type": "uint256"}], "internalType": "struct DexArbitrage.ArbitrageParams", "name": "params", "type": "tuple"}], "name": "executeArbitrage", "outputs": [], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [{"internalType": "address", "name": "asset", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}, {"internalType": "uint256", "name": "premium", "type": "uint256"}, {"internalType": "address", "name": "initiator", "type": "address"}, {"internalType": "bytes", "name": "data", "type": "bytes"}], "name": "executeOperation", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}, {"inputs": [], "name": "getStats", "outputs": [{"internalType": "uint256", "name": "operations", "type": "uint256"}, {"internalType": "uint256", "name": "totalProfitAccumulated", "type": "uint256"}, {"internalType": "uint256", "name": "lastProfitAmount", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name": "lastProfit", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name": "totalOperations", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [], "name": "totalProfit", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}, {"inputs": [{"internalType": "address", "name": "token", "type": "address"}], "name": "withdrawProfit", "outputs": [], "stateMutability": "nonpayable", "type": "function"}, {"stateMutability": "payable", "type": "receive"}]''')

# ABI mínimo do router (só o necessário pra ler preços, função real e verificada)
ROUTER_ABI = json.loads('''[
    {
        "name": "getAmountsOut",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"}
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}]
    }
]''')


class DexArbitrageExecutor:
    """
    Detecta e executa arbitragem real entre QuickSwap e SushiSwap na Polygon,
    usando o mesmo ContractExecutor (RPC/conta/FastLane) já configurado.
    """

    def __init__(self, contract_executor):
        """
        Args:
            contract_executor: instância de executor.ContractExecutor já
                inicializada (reaproveita w3, account, nonce lock e o
                método send_transaction() com suporte a FastLane).
        """
        self.ce = contract_executor
        self.w3: Web3 = contract_executor.w3
        self.dex_contract = None

        if DEX_ARBITRAGE_CONTRACT_ADDRESS:
            try:
                self.dex_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(DEX_ARBITRAGE_CONTRACT_ADDRESS),
                    abi=DEX_ARBITRAGE_ABI,
                )
                logger.info(f"Contrato DexArbitrage carregado: {DEX_ARBITRAGE_CONTRACT_ADDRESS}")
            except Exception as e:
                logger.error(f"Erro ao carregar DexArbitrage: {e}")
        else:
            logger.warning(
                "DEX_ARBITRAGE_CONTRACT_ADDRESS não configurado - "
                "deploy o contrato e configure o .env antes de operar em modo LIVE"
            )

        self.quickswap = self.w3.eth.contract(
            address=Web3.to_checksum_address(QUICKSWAP_ROUTER), abi=ROUTER_ABI
        )
        self.sushiswap = self.w3.eth.contract(
            address=Web3.to_checksum_address(SUSHISWAP_ROUTER), abi=ROUTER_ABI
        )

    def _get_price_quote(self, router_contract, amount_in: int, path: list) -> Optional[int]:
        """Chamada de leitura (getAmountsOut) - não custa gas, é view."""
        try:
            amounts = router_contract.functions.getAmountsOut(amount_in, path).call()
            return amounts[-1]
        except Exception as e:
            logger.warning(f"Erro ao consultar preço no router {router_contract.address}: {e}")
            return None

    def scan_opportunity(self, capital_usdc: float = None) -> Optional[dict]:
        """
        Consulta os preços REAIS (on-chain, via getAmountsOut) nos dois DEXs
        para o ciclo USDC -> WPOL -> USDC e calcula se há spread lucrativo.

        Returns:
            dict com detalhes da oportunidade se lucrativa, ou None.
        """
        capital = capital_usdc or CAPITAL_POR_OP
        amount_in = int(capital * 1e6)  # USDC tem 6 decimais

        usdc = Web3.to_checksum_address(USDC_ADDRESS)
        wpol = Web3.to_checksum_address(WPOL_ADDRESS)

        # Perna 1: quanto WPOL eu recebo comprando com USDC em cada DEX
        wpol_from_quickswap = self._get_price_quote(self.quickswap, amount_in, [usdc, wpol])
        wpol_from_sushiswap = self._get_price_quote(self.sushiswap, amount_in, [usdc, wpol])

        if not wpol_from_quickswap or not wpol_from_sushiswap:
            logger.debug("Não foi possível obter cotação de ambos os DEXs - pulando ciclo")
            return None

        # Decide onde comprar (mais WPOL por USDC) e onde vender (melhor preço de volta)
        if wpol_from_quickswap > wpol_from_sushiswap:
            router_buy, router_buy_addr = self.quickswap, QUICKSWAP_ROUTER
            router_sell, router_sell_addr = self.sushiswap, SUSHISWAP_ROUTER
            wpol_received = wpol_from_quickswap
        else:
            router_buy, router_buy_addr = self.sushiswap, SUSHISWAP_ROUTER
            router_sell, router_sell_addr = self.quickswap, QUICKSWAP_ROUTER
            wpol_received = wpol_from_sushiswap

        # Perna 2: quanto USDC eu recebo vendendo esse WPOL no OUTRO router
        usdc_back = self._get_price_quote(router_sell, wpol_received, [wpol, usdc])
        if not usdc_back:
            return None

        gross_spread = (usdc_back - amount_in) / amount_in

        logger.info(
            f"Ciclo USDC->WPOL->USDC: recebido {usdc_back/1e6:.2f} USDC de {capital} "
            f"investido (spread bruto {gross_spread:.3%}) via {router_buy_addr[:8]}.../{router_sell_addr[:8]}..."
        )

        if gross_spread < DEX_SPREAD_MINIMO:
            return None

        return {
            "router_buy": router_buy_addr,
            "router_sell": router_sell_addr,
            "amount_in": amount_in,
            "wpol_intermediate": wpol_received,
            "usdc_back": usdc_back,
            "gross_spread": gross_spread,
        }

    def execute(self, opportunity: dict) -> Tuple[bool, str]:
        """Executa a arbitragem detectada em scan_opportunity()."""

        if DRY_RUN:
            logger.info(f"[DRY RUN] Arbitragem DEX seria executada: {opportunity}")
            save_operation(
                termo="DEX_ARBITRAGE_USDC_WPOL",
                direction=f"{opportunity['router_buy'][:8]}->{opportunity['router_sell'][:8]}",
                score=opportunity["gross_spread"],
                lucro=(opportunity["usdc_back"] - opportunity["amount_in"]) / 1e6,
                status="DRY_RUN",
                detalhes=json.dumps(opportunity),
            )
            return True, "DRY_RUN_SUCCESS"

        if not self.dex_contract:
            error = "DEX_ARBITRAGE_CONTRACT_ADDRESS não configurado - deploy o contrato primeiro"
            logger.error(error)
            return False, error

        try:
            # Tolerância de slippage simples (2%) sobre as cotações on-chain já obtidas.
            # Para produção com capital maior, considere recalcular a cotação
            # logo antes de montar a tx (o preço pode mover entre o scan e o envio).
            min_out_buy = int(opportunity["wpol_intermediate"] * 0.98)
            min_out_sell = int(opportunity["usdc_back"] * 0.98)
            min_profit = int((opportunity["usdc_back"] - opportunity["amount_in"]) * 0.9)

            params = (
                Web3.to_checksum_address(USDC_ADDRESS),
                Web3.to_checksum_address(WPOL_ADDRESS),
                Web3.to_checksum_address(opportunity["router_buy"]),
                Web3.to_checksum_address(opportunity["router_sell"]),
                max(min_profit, 0),
                min_out_buy,
                min_out_sell,
            )

            max_fee, max_priority_fee = self.ce._get_gas_price()

            tx_data = self.dex_contract.functions.executeArbitrage(
                opportunity["amount_in"], params
            ).build_transaction({
                "from": self.ce.account.address,
                "nonce": self.ce._get_safe_nonce(),
                "chainId": 137,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            })
            tx_data["gas"] = self.ce._estimate_gas(tx_data)

            success, result = self.ce.send_transaction(
                tx_data, solver_contract_address=DEX_ARBITRAGE_CONTRACT_ADDRESS
            )

            status = "SUCCESS" if success else "ERROR"
            save_operation(
                termo="DEX_ARBITRAGE_USDC_WPOL",
                direction=f"{opportunity['router_buy'][:8]}->{opportunity['router_sell'][:8]}",
                score=opportunity["gross_spread"],
                lucro=(opportunity["usdc_back"] - opportunity["amount_in"]) / 1e6 if success else 0,
                status=status,
                detalhes=result,
            )
            return success, result

        except Exception as e:
            error = f"Erro ao executar arbitragem DEX: {e}"
            logger.error(error)
            save_operation(
                termo="DEX_ARBITRAGE_USDC_WPOL", direction="ERROR",
                score=0, lucro=0, status="ERROR", detalhes=error,
            )
            return False, error

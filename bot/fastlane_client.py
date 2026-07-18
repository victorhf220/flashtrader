"""
fastlane_client.py
===================

Cliente para submissão de transações de arbitragem via FastLane (PFL) na
Polygon, usando o protocolo Atlas mais recente (SolverOperation + EIP-712).

⚠️ IMPORTANTE — LEIA ANTES DE USAR EM PRODUÇÃO:

1. Este módulo é aplicável a arbitragem DEX-a-DEX (Uniswap/QuickSwap/etc.)
   executada via flash loan, NÃO ao fluxo atual de "arbitragem" com a
   Polymarket em FlashTrader.sol — esse fluxo já foi documentado como
   inviável on-chain em POLYMARKET_ONCHAIN_LIMITACAO.md (a interface
   ICTFExchange é fictícia). Uma transação de arbitragem Polymarket sempre
   reverteria, então priorizar sua submissão via FastLane não resolveria
   o problema de fundo.

2. Os endereços de contrato do Atlas/FastLane (dAppControl, atlasVerification,
   atlas, etc.) e o formato exato do endpoint do relay evoluem com o tempo
   (o protocolo já passou por pelo menos uma migração de "top-of-block" para
   "searcher bundles/backruns" com EIP-712). ANTES de usar em mainnet:
   - Confirme os endereços atuais em:
     https://fastlane-labs.gitbook.io/polygon-fastlane/searcher-guides/searcher-contract-integration/addresses-and-endpoints
   - Confirme o endpoint e o método JSON-RPC/REST atual em:
     https://fastlane-labs.gitbook.io/polygon-fastlane/searcher-guides/bundles-backruns/bid-submission
   - Considere usar o SDK oficial (@fastlane-labs/atlas-sdk, atualmente só em
     JS/TS) como referência de formato, já que não há SDK Python oficial
     confirmado no momento da escrita deste módulo (18/07/2026).

3. Este código é uma camada de infraestrutura (ESQUELETO), não testada em
   mainnet. Rode extensivamente em DRY_RUN / testnet antes de usar com
   capital real.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from eth_account import Account
from eth_account.messages import encode_structured_data
from web3 import Web3

logger = logging.getLogger(__name__)

# ===== ENDEREÇOS (Polygon mainnet) =====
# ⚠️ VERIFICAR antes de ir para produção — ver aviso no topo do arquivo.
ATLAS_ADDRESS = "0x4A394bD4Bc2f4309ac0b75c052b242ba3e0f32e0"
ATLAS_VERIFICATION_ADDRESS = "0xf31cf8740Dc4438Bb89a56Ee2234Ba9d5595c0E9"
DAPP_CONTROL_ADDRESS = "0x3e23e4282FcE0cF42DCd0E9bdf39056434E65C1F"
DAPP_OP_SIGNER_ADDRESS = "0x96D501A4C52669283980dc5648EEC6437e2E6346"

# ⚠️ Endpoint do relay — CONFIRMAR na doc "Addresses & Endpoints" antes de usar.
FASTLANE_RELAY_URL = "https://relay.fastlane.xyz"

# EIP-712 domain para assinatura da SolverOperation (Atlas)
EIP712_DOMAIN_NAME = "Atlas"
EIP712_DOMAIN_VERSION = "1.0.0"


@dataclass
class SolverOperation:
    """Representa uma SolverOperation do protocolo Atlas/FastLane.

    Corresponde ao struct Solidity documentado em:
    https://fastlane-labs.gitbook.io/polygon-fastlane/searcher-guides/getting-started-as-a-searcher/migration-guide-for-searchers
    """
    from_address: str          # Endereço do solver (sua conta/bot)
    to: str = ATLAS_ADDRESS    # Endereço do contrato Atlas
    value: int = 0             # MATIC necessário para a operação
    gas: int = 500_000         # Gas limit da operação do solver
    max_fee_per_gas: int = 0   # Deve casar com a tx de oportunidade
    deadline: int = 0          # Deadline em NÚMERO DE BLOCO, não timestamp
    solver: str = ""           # Endereço do seu contrato solver (ISolverContract)
    control: str = DAPP_CONTROL_ADDRESS
    user_op_hash: bytes = field(default_factory=lambda: b"\x00" * 32)
    bid_token: str = "0x0000000000000000000000000000000000000000"  # address(0) = MATIC
    bid_amount: int = 0        # Quanto você está dando de lance pelo bloco/prioridade
    data: bytes = b""          # Calldata da chamada ao seu contrato solver
    signature: bytes = b""     # Preenchido após assinar


class FastLaneClient:
    """
    Constrói, assina e submete SolverOperations para o relay do FastLane.

    Uso típico (arbitragem DEX real, não Polymarket):
        client = FastLaneClient(w3, private_key)
        op = client.build_solver_operation(
            solver_contract=CONTRACT_ADDRESS,
            calldata=encoded_execute_arbitrage_call,
            bid_amount_wei=Web3.to_wei(0.01, 'ether'),  # lance em MATIC
            deadline_block=current_block + 5,
            max_fee_per_gas=max_fee,
        )
        result = client.submit(op, user_op_hash=opportunity_tx_hash)
    """

    def __init__(self, w3: Web3, private_key: str, relay_url: str = FASTLANE_RELAY_URL):
        self.w3 = w3
        self.account = Account.from_key(private_key)
        self.relay_url = relay_url

    def build_solver_operation(
        self,
        solver_contract: str,
        calldata: bytes,
        bid_amount_wei: int,
        deadline_block: int,
        max_fee_per_gas: int,
        gas_limit: int = 500_000,
        bid_token: str = "0x0000000000000000000000000000000000000000",
    ) -> SolverOperation:
        """Monta uma SolverOperation pronta para assinatura."""
        return SolverOperation(
            from_address=self.account.address,
            to=ATLAS_ADDRESS,
            value=0,
            gas=gas_limit,
            max_fee_per_gas=max_fee_per_gas,
            deadline=deadline_block,
            solver=Web3.to_checksum_address(solver_contract),
            control=DAPP_CONTROL_ADDRESS,
            bid_token=bid_token,
            bid_amount=bid_amount_wei,
            data=calldata,
        )

    def _eip712_message(self, op: SolverOperation) -> dict:
        """
        Monta a estrutura EIP-712 para assinatura da SolverOperation.

        ⚠️ Os nomes/tipos dos campos abaixo seguem o struct documentado na
        migration guide do FastLane, mas o typehash EIP-712 EXATO deve ser
        conferido contra o contrato AtlasVerification atual antes de assinar
        operações com valor real — uma divergência de um campo faz a
        assinatura ser rejeitada on-chain (não custa gas, mas não funciona).
        """
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "SolverOperation": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "gas", "type": "uint256"},
                    {"name": "maxFeePerGas", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "solver", "type": "address"},
                    {"name": "control", "type": "address"},
                    {"name": "userOpHash", "type": "bytes32"},
                    {"name": "bidToken", "type": "address"},
                    {"name": "bidAmount", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
            },
            "primaryType": "SolverOperation",
            "domain": {
                "name": EIP712_DOMAIN_NAME,
                "version": EIP712_DOMAIN_VERSION,
                "chainId": self.w3.eth.chain_id,
                "verifyingContract": ATLAS_VERIFICATION_ADDRESS,
            },
            "message": {
                "from": op.from_address,
                "to": op.to,
                "value": op.value,
                "gas": op.gas,
                "maxFeePerGas": op.max_fee_per_gas,
                "deadline": op.deadline,
                "solver": op.solver,
                "control": op.control,
                "userOpHash": op.user_op_hash,
                "bidToken": op.bid_token,
                "bidAmount": op.bid_amount,
                "data": op.data,
            },
        }

    def sign_operation(self, op: SolverOperation) -> SolverOperation:
        """Assina a SolverOperation via EIP-712 e preenche op.signature.

        Usa encode_structured_data (não encode_typed_data) porque a versão
        de eth-account fixada no requirements.txt (0.8.0) não tem a função
        mais nova. Se atualizar eth-account no futuro, encode_typed_data é
        a substituta recomendada — troque as duas junto.
        """
        typed_data = self._eip712_message(op)
        encoded = encode_structured_data(primitive=typed_data)
        signed = self.account.sign_message(encoded)
        op.signature = signed.signature
        return op

    def submit(self, op: SolverOperation, opportunity_tx_hash: Optional[str] = None) -> dict:
        """
        Assina e envia a SolverOperation para o relay do FastLane.

        Retorna um dict com {"success": bool, "detail": ...}. Nunca lança
        exceção para cima — falha de submissão ao FastLane não deve derrubar
        o bot; o chamador decide se cai para envio via RPC público normal.

        ⚠️ O payload exato (JSON-RPC method name / REST path) deve ser
        conferido contra a doc "Relay JSON-RPC API" / "Relay REST API" antes
        de operar com capital real — o formato abaixo é uma estimativa
        baseada na estrutura documentada, não confirmada em produção.
        """
        try:
            signed_op = self.sign_operation(op)

            payload = {
                "solverOperation": {
                    "from": signed_op.from_address,
                    "to": signed_op.to,
                    "value": str(signed_op.value),
                    "gas": str(signed_op.gas),
                    "maxFeePerGas": hex(signed_op.max_fee_per_gas),
                    "deadline": signed_op.deadline,
                    "solver": signed_op.solver,
                    "control": signed_op.control,
                    "userOpHash": signed_op.user_op_hash.hex(),
                    "bidToken": signed_op.bid_token,
                    "bidAmount": str(signed_op.bid_amount),
                    "data": signed_op.data.hex(),
                    "signature": signed_op.signature.hex(),
                },
                "opportunityTxHash": opportunity_tx_hash,
            }

            resp = requests.post(
                f"{self.relay_url}/solverOperation",
                json=payload,
                timeout=5,
            )

            if resp.status_code == 200:
                logger.info(f"Bundle submetido ao FastLane com sucesso: {resp.json()}")
                return {"success": True, "detail": resp.json()}
            else:
                logger.warning(
                    f"FastLane relay retornou status {resp.status_code}: {resp.text}"
                )
                return {"success": False, "detail": resp.text}

        except requests.exceptions.RequestException as e:
            logger.warning(f"Erro de rede ao submeter ao FastLane relay: {e}")
            return {"success": False, "detail": str(e)}
        except Exception as e:
            logger.error(f"Erro inesperado ao montar/assinar SolverOperation: {e}")
            return {"success": False, "detail": str(e)}

#!/usr/bin/env python3
"""
Script para deploy do contrato FlashTrader na Polygon mainnet
Uso: python deploy.py
"""

import os
import json
import sys
from pathlib import Path
from web3 import Web3
from eth_account import Account
from solcx import compile_source, install_solc

from bot.config import PRIVATE_KEY, POLYGON_RPC, AAVE_POOL_PROVIDER

def main():
    print("=" * 80)
    print("SENTINEL ARBITRAGE - CONTRACT DEPLOYMENT")
    print("=" * 80)
    
    if not PRIVATE_KEY:
        print("❌ ERRO: PRIVATE_KEY não está definida em .env")
        sys.exit(1)
    
    # Inicializa Web3
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        print("❌ ERRO: Não foi possível conectar ao Polygon RPC")
        sys.exit(1)
    
    print(f"✓ Conectado ao Polygon RPC")
    
    # Carrega conta
    account = Account.from_key(PRIVATE_KEY)
    print(f"✓ Conta: {account.address}")
    
    # Verifica saldo
    balance = w3.eth.get_balance(account.address)
    balance_matic = w3.from_wei(balance, 'ether')
    print(f"✓ Saldo: {balance_matic:.4f} MATIC")
    
    if balance_matic < 0.5:
        print("⚠️  Aviso: Saldo baixo (recomendado: > 0.5 MATIC para gas)")
    
    # Lê arquivo do contrato
    contract_path = Path("contracts/FlashTrader.sol")
    if not contract_path.exists():
        print(f"❌ ERRO: Arquivo {contract_path} não encontrado")
        sys.exit(1)
    
    with open(contract_path) as f:
        contract_source = f.read()
    
    print("\n📝 Compilando contrato...")
    
    # Instala versão correta do solc
    try:
        install_solc("0.8.10")
    except:
        pass  # Talvez já esteja instalado
    
    try:
        compiled = compile_source(
            contract_source,
            solc_version="0.8.10",
            optimize=True,
            optimize_runs=200
        )
    except Exception as e:
        print(f"❌ ERRO ao compilar: {e}")
        sys.exit(1)
    
    contract_id = "FlashTrader"
    contract_interface = compiled[f"<stdin>:{contract_id}"]
    
    print(f"✓ Contrato compilado: {contract_id}")
    
    # Prepara deployment
    contract = w3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin']
    )
    
    # Constrói transação de deployment
    constructor_args = [AAVE_POOL_PROVIDER]
    
    print("\n🚀 Enviando transação de deployment...")
    
    try:
        tx = contract.constructor(*constructor_args).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': 137,  # Polygon mainnet
        })
        
        # Estima gas
        gas_estimate = w3.eth.estimate_gas(tx)
        tx['gas'] = int(gas_estimate * 1.2)
        
        # Gas price (EIP-1559)
        block = w3.eth.get_block('latest')
        base_fee = block.get('baseFeePerGas', w3.to_wei(50, 'gwei'))
        max_fee = (base_fee * 2)
        max_priority_fee = w3.to_wei(2, 'gwei')
        
        tx['maxFeePerGas'] = max_fee
        tx['maxPriorityFeePerGas'] = max_priority_fee
        
        print(f"  Gas: {tx['gas']}")
        print(f"  Max Fee: {w3.from_wei(max_fee, 'gwei'):.2f} GWEI")
        
        # Assina transação
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        
        # Envia
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        print(f"\n✓ Transação enviada: {tx_hash.hex()}")
        
        print("\n⏳ Aguardando confirmação (pode levar 1-2 minutos)...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt['status'] == 1:
            contract_address = receipt['contractAddress']
            print(f"\n✅ SUCESSO! Contrato deployado em:")
            print(f"\n   {contract_address}\n")
            
            print("=" * 80)
            print("PRÓXIMOS PASSOS:")
            print("=" * 80)
            print(f"\n1. Copie o endereço do contrato:")
            print(f"   {contract_address}")
            print(f"\n2. Cole em .env como:")
            print(f"   CONTRACT_ADDRESS={contract_address}")
            print(f"\n3. Deposite USDC no contrato (transação adicional):")
            print(f"   Quantidade mínima: 3000 USDC")
            print(f"\n4. Inicie o bot:")
            print(f"   python bot/main.py")
            
            return contract_address
        else:
            print("\n❌ Transação falhou (status 0)")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ ERRO ao enviar transação: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

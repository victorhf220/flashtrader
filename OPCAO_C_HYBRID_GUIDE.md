# 🚀 OPÇÃO C: Flash Loan Híbrida + Polymarket

## 📋 Visão Geral

A **Opção C** combina o melhor dos dois mundos:

- ✅ **Flash loans da Aave V3** (capital zero, paga apenas fee de 0.09%)
- ✅ **Arbitrage real na Polymarket** (via py-clob-client, SDK oficial)
- ✅ **Execução assistida** (contrato orquestra, Python executa)

### Como funciona

```
1. Python analisa oportunidade na Polymarket
   ↓
2. Python pede flash loan ao contrato Solidity
   ↓
3. Contrato Solidity pega USDC da Aave V3 (em 1 transação)
   ↓
4. Contrato transfere USDC pro Python
   ↓
5. Python arbitra na Polymarket (via py-clob-client)
   - Assina ordem EIP-712
   - Envia pra Polymarket
   - Aguarda casamento
   - Ganha lucro em USDC
   ↓
6. Python devolve USDC (original + premium + lucro) pro contrato
   ↓
7. Contrato repaga Aave + extrai lucro
```

---

## 🛠️ Setup

### 1. Deploy do Contrato

```bash
# Instale Hardhat (se não tiver)
npm install -g hardhat

# No diretório raiz
npx hardhat compile
```

Depois use Remix ou Hardhat pra fazer deploy:

```javascript
// Remixにコピペして deploy
const PyBotWallet = "0xSuaCarteiraQue_Python_Controla";
const contract = await PolymarketFlashLoan.deploy(PyBotWallet);
```

**Guarde:**
- `CONTRACT_ADDRESS` (contrato deployado)
- `PRIVATE_KEY` (sua chave privada)
- `PY_BOT_WALLET` (carteira Python - pode ser a mesma ou diferente)

### 2. Instale Dependências

```bash
pip install -r requirements.txt
```

Depois em Python, importe:

```python
from bot.polymarket_executor import PolymarketExecutorHybrid
from bot.sentiment import SentimentAnalyzer
from bot.main import SentinelBot
```

### 3. Configure `.env`

```env
# Blockchain
POLYGON_RPC=https://polygon-rpc.com
PRIVATE_KEY=0xSUA_CHAVE_PRIVADA
CONTRACT_ADDRESS=0xSeu_Contrato_Deployado

# Python Bot
PY_BOT_WALLET=0xCarteira_Python

# Polymarket
POLYMARKET_CHAIN_ID=137

# Parâmetros
FLASH_LOAN_AMOUNT=3000  # USDC
SPREAD_MINIMO=0.02      # 2%
SCORE_LIMIAR=0.3        # Sentimento > 0.3 = COMPRA

# Sentiment (opcional, se usar análise)
TWITTER_BEARER=...
REDDIT_CLIENT=...
```

---

## 📊 Fluxo de Execução

### Passo 1: Analisar Oportunidade

```python
# bot/main.py
analyzer = SentimentAnalyzer()

for market in ["bitcoin", "ethereum", "trump"]:
    score = analyzer.get_combined_score(market)
    
    if score > SCORE_LIMIAR:
        # Oportunidade detectada!
        # Próximo passo: pedir flash loan
        break
```

### Passo 2: Requisitar Flash Loan

```python
executor = PolymarketExecutorHybrid(
    private_key=PRIVATE_KEY,
    contract_address=CONTRACT_ADDRESS,
    py_bot_wallet=PY_BOT_WALLET
)

# Pede 3000 USDC emprestados
success = executor.request_flash_loan(3000 * 1e6)

if success:
    print("✅ Flash loan confirmado, USDC a caminho...")
    time.sleep(10)  # Aguarda confirmação
```

Neste momento, o contrato Solidity:
1. Pegou USDC da Aave
2. Transferiu pra `PY_BOT_WALLET`
3. Emitiu evento "FlashLoanExecuted"

### Passo 3: Arbitra na Polymarket

```python
result = await executor.execute_polymarket_arbitrage(
    market_id="123456",  # ID do mercado
    outcome="YES",        # ou "NO"
    amount_usdc=3000,
    sentiment_score=0.65
)

if result["status"] == "filled":
    print(f"✅ Ordem casada!")
    print(f"   Shares compradas: {result['shares']}")
    print(f"   Custo: ${result['cost']:.2f}")
```

A ordem é:
- Tipo: **LIMIT** (não market, pra controlar preço)
- Preço: 2% pior que mercado (slippage protection)
- Aguarda casamento até 2 minutos

### Passo 4: Repaga Flash Loan

```python
# Python devolveu o USDC + lucro pra carteira do contrato
profit = executor.repay_flash_loan()

if profit:
    print("✅ Flash loan repagado!")
    print("   Lucro extraído: ${lucro}")
```

No contrato:
1. Verifica que Python devolveu USDC
2. Repaga Aave automaticamente
3. Extrai lucro (USDC_recebido - USDC_emprestado - fee_aave)

---

## 💰 Matemática de Lucro

### Exemplo Concreto

```
Flash Loan:        3000 USDC
Aave Fee (0.09%):  2.70 USDC
---
A Pagar Aave:      3002.70 USDC

Arbitrage na Polymarket:
- Compra YES a 0.25
- Vende a 0.27
- Spread: 2%
- Lucro bruto:     60 USDC  (3000 * 0.02)

Resultado Final:
- Recebe Polymarket: 3060 USDC
- Paga Aave:        -3002.70 USDC
- Lucro Líquido:    57.30 USDC

Taxa (0.09%):  2.70 USDC
Lucro Real:    57.30 USDC ← Esse é seu! 🎉
```

### Breakeven

O spread mínimo pra cobrir a fee da Aave:

```
spread_minimo = (fee_aave / capital) * 100
spread_minimo = (2.70 / 3000) * 100
spread_minimo = 0.09%
```

Então qualquer spread acima de 0.09% já é lucro!

---

## ⚠️ Riscos e Proteções

### 1. Ordem Não Casa em Tempo

**Proteção:**
```python
timeout = 120  # 2 minutos
# Se não casada, cancela e repaga Aave
```

### 2. Preço Pior que Esperado

**Proteção:**
```python
slippage_protection = 1.02  # Coloca ordem 2% pior
price_limit = current_price * slippage_protection

# Rejeita se preço for pior
```

### 3. Saldo Insuficiente pra Repagar

**Proteção:**
```solidity
require(balance >= totalOwed, "Insufficient USDC for repayment");
// Contrato reverte se falta dinheiro
```

---

## 🎮 Começar do Zero

### Testnet (Polygon Mumbai)

```bash
# 1. Pega MATIC de faucet
# https://faucet.polygon.technology/

# 2. Pega USDC de faucet
# https://faucet.aave.com/ (seleciona Mumbai)

# 3. Deploy contrato em Mumbai
# RPC: https://rpc-mumbai.maticvigil.com

# 4. Testa fluxo completo em testnet
# NÃO colocar dinheiro real ainda
```

### Mainnet (Polygon)

```bash
# 1. Tem USDC? NÃO? Compra no Uniswap/Quickswap

# 2. Saldo mínimo recomendado:
#    - 3000 USDC (capital do arbitrage)
#    - 10 MATIC (gas fees)

# 3. Deploy contrato com ContractAddress

# 4. Deixa rodando em DRY_RUN=true por 1 semana

# 5. Se tudo ok, muda pra DRY_RUN=false e começa com 500 USDC
```

---

## 📝 Código Completo de Exemplo

```python
import asyncio
import os
from bot.polymarket_executor import PolymarketExecutorHybrid
from bot.sentiment import SentimentAnalyzer

async def main():
    # Setup
    private_key = os.getenv("PRIVATE_KEY")
    contract_addr = os.getenv("CONTRACT_ADDRESS")
    py_wallet = os.getenv("PY_BOT_WALLET")
    
    executor = PolymarketExecutorHybrid(private_key, contract_addr, py_wallet)
    analyzer = SentimentAnalyzer()
    
    # Detecta oportunidade
    markets = ["bitcoin", "ethereum"]
    for market in markets:
        score = analyzer.get_combined_score(market)
        
        if score > 0.3:  # Compra
            # Fluxo completo
            success = await executor.run_hybrid_arbitrage(
                market_id="12345",  # Mapear market -> market_id
                outcome="YES",
                amount_usdc=3000,
                sentiment_score=score
            )
            
            if success:
                print(f"✅ Arbitrage bem-sucedido em {market}!")
            else:
                print(f"❌ Arbitrage falhou em {market}")
            
            break

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔍 Debug / Troubleshooting

### Flash Loan não aparece

```bash
# Verificar:
1. Contrato tem saldo na Aave? (pode ser que não)
2. Aave está funcionando em Polygon? (sim, é mainnet)
3. Que tipo de token? USDC (decimal 6) - confirmado
```

### Ordem não casa

```bash
# Verificar:
1. Market ID existe no Polymarket?
2. Outcome ("YES" ou "NO") está correto?
3. Preço é razoável? (não muito alto/baixo)
4. Há liquidez no mercado? (volume > 1000 USDC)
```

### Repagamento falha

```bash
# Verificar:
1. Python devolveu o USDC? (verificar saldo do contrato)
2. Fee foi debitada? (Aave pega automaticamente)
3. Há lucro sobrando? (ou quebrou no zero)
```

---

## 🎯 Próximos Passos

1. ✅ Deploy do contrato em Polygon (Mumbai testnet primeiro)
2. ✅ Teste fluxo em DRY_RUN por 1 semana
3. ✅ Integre py-clob-client com market real
4. ✅ Monitore logs e ajuste parâmetros
5. ✅ Escale capital após 1 mês de histórico positivo

---

## 📚 Referências

- [Aave V3 Docs](https://docs.aave.com/developers/core-contracts/pool)
- [Polymarket CLOB API](https://docs.polymarket.com/api)
- [py-clob-client SDK](https://github.com/polymarket/py-clob-client)
- [EIP-712 (Order Signing)](https://eips.ethereum.org/EIPS/eip-712)

---

**Bom luck! 🚀**

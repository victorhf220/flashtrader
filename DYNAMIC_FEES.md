# 💰 TAXAS DINÂMICAS POLYMARKET (Março 2026)

## 📊 Visão Geral

A Polymarket implementou em **março de 2026** um sistema de **taxas dinâmicas por categoria**. Isso significa que diferentes mercados têm diferentes percentuais de taxa.

**Impacto direto no bot:**
- ❌ Arbitrages que eram lucrativas em "Crypto" (1.8%) podem ser inviáveis
- ✅ Arbitrages em "Geopolitics" (0%) são muito mais lucrativas
- 📊 Bot agora calcula lucro LÍQUIDO (após taxas) para decisões

---

## 📋 Tabela de Taxas Dinâmicas

| Categoria | Taxa Taker | Taxa Maker | Exemplo |
|-----------|-----------|-----------|---------|
| **Geopolitics** | **0.0%** | 0.0% | Conflitos, tratados, políticas internacionais |
| **Elections** | 0.5% | 0.0% | Eleições presidenciais, referendos |
| **Economics** | 1.0% | 0.0% | Taxa Fed, desemprego, inflação, PIB |
| **Sports** | 0.75% | 0.0% | NFL, NBA, World Cup, Olympics |
| **Esports** | 0.75% | 0.0% | Dota 2, League of Legends, CS:GO |
| **Entertainment** | 1.5% | 0.0% | Oscars, Grammys, streaming |
| **Science** | 1.5% | 0.0% | Descobertas, prêmios científicos |
| **Weather** | 2.0% | 0.0% | Furacões, terremotos, temperaturas |
| **Crypto** | **1.8%** | 0.0% | Bitcoin, Ethereum, altcoins |
| **Outros** | 2.0% | 0.0% | Categorias não listadas |

> **Nota:** Todos os maker fees são 0% (promoção para liquidez)

---

## 🔧 Como o Bot Utiliza Isso

### 1️⃣ Detecção de Categoria

O bot detecta a categoria do mercado automaticamente:

```python
# bot/config.py
MARKET_CATEGORY_MAP = {
    "bitcoin": "crypto",           # 1.8% taxa
    "ethereum": "crypto",          # 1.8% taxa
    "trump": "elections",          # 0.5% taxa
    "fed rate": "economics",       # 1.0% taxa
    "nfl": "sports",              # 0.75% taxa
    ...
}
```

### 2️⃣ Cálculo de Lucro Líquido

```python
# bot/executor.py

# Lucro bruto (antes de taxas)
gross_profit = 100  # $100

# Detecta categoria
category = "crypto"  # Bitcoin market
fee = 1.8%

# Lucro líquido (depois de taxas)
net_profit = 100 - (100 * 1.8%) = $98.20
```

### 3️⃣ Decisão de Trade

O bot agora considera:

```python
# Exemplo 1: Arbitrage em Geopolitics (0% taxa)
gross_profit = $100
fee = 0%
net_profit = $100  ✅ MUITO LUCRATIVO

# Exemplo 2: Arbitrage em Crypto (1.8% taxa)
gross_profit = $100
fee = 1.8%
net_profit = $98.20  ✅ Ainda lucrativo

# Exemplo 3: Arbitrage em Weather (2.0% taxa)
gross_profit = $50
fee = 2.0%
net_profit = $49.00  ⚠️ Margem apertada
```

---

## 📈 Estratégia Otimizada

### 🎯 Priorize Mercados com Baixa Taxa

1. **Tier 1 - Máxima Prioridade (0% taxa)**
   - Geopolitics
   - Ideal para spread baixo (1-2%)

2. **Tier 2 - Alta Prioridade (0.5-0.75% taxa)**
   - Elections
   - Sports
   - Precisa de spread > 2%

3. **Tier 3 - Média Prioridade (1.0-1.5% taxa)**
   - Economics
   - Entertainment
   - Precisa de spread > 3%

4. **Tier 4 - Baixa Prioridade (1.8-2.0% taxa)**
   - Crypto
   - Weather
   - Precisa de spread > 4%

### 💡 Exemplo de Decisão

```python
# Mesmo sentiment score, diferentes categorias

# BITCOÍN (Crypto, 1.8% taxa)
spread = 2.0%
gross_profit = $100
net_profit = $98.20
✅ EXECUTAR (margem OK)

# INFLAÇÃO (Economics, 1.0% taxa)
spread = 1.5%
gross_profit = $75
net_profit = $74.25
✅ EXECUTAR (margem melhor)

# FURACÃO (Weather, 2.0% taxa)
spread = 1.2%
gross_profit = $60
net_profit = $58.80
⚠️ CONSIDERAR (margem apertada)
```

---

## 🔍 Como Verificar o Cálculo

Os logs do bot mostram o breakdown completo:

```
[INFO] Market: Bitcoin
[INFO] Category detected: crypto (1.8% fee)
[INFO] Gross profit: $100.00
[INFO] Fee (1.8%): $1.80
[INFO] Net profit: $98.20
```

---

## ⚙️ Configuração do Bot

### Em `.env`:

```env
# Categoria padrão para mercados não mapeados
CATEGORIA=geopolitics

# Capital por operação
CAPITAL_POR_OP=3000

# Spread mínimo (agora com consideração de taxas)
SPREAD_MINIMO=0.03

# Score limiar (sem mudança, mas agora com melhor validação)
SCORE_LIMIAR=0.3
```

### Em `bot/config.py`:

Adicione novas categorias conforme Polymarket lança promoções:

```python
POLYMARKET_CATEGORY_FEES = {
    "geopolitics": (0.0, 0.0),   # Taxa de promoção
    "your_new_category": (0.5, 0.0),  # Nova categoria
}

MARKET_CATEGORY_MAP = {
    "new market name": "your_new_category",
}
```

---

## 📊 Análise de Impacto

### Comparação: Com vs Sem Taxas Dinâmicas

```
Mercado: Bitcoin
Spread: 2.0%
Capital: $3,000

ANTES (assumindo 2% fixa):
Lucro bruto: $60
Taxa: $60 * 2% = $1.20
Lucro líquido: $58.80

DEPOIS (1.8% dinâmica):
Lucro bruto: $60
Taxa: $60 * 1.8% = $1.08
Lucro líquido: $58.92

Melhoria: +$0.12 (0.2%)
```

Para geopolitics (0% taxa):
```
Mercado: Conflito no Médio Oriente
Spread: 2.0%
Capital: $3,000

Lucro bruto: $60
Taxa: $0 (promoção!)
Lucro líquido: $60.00

Melhoria: +$1.20 (2%)
```

---

## 🚨 Casos de Uso Críticos

### ❌ Quando NÃO Executar

```python
# Categoria com taxa alta + spread baixo = INVIÁVEL
market = "Weather"           # 2.0% taxa
spread = 1.0%              # Spread baixo
gross_profit = $30
net_profit = $29.40        # Margem muito apertada
min_profit_threshold = $50 # Não atinge mínimo!

# Bot pula este trade
logger.warning("Spread insuficiente após considerar taxa")
```

### ✅ Quando SEMPRE Executar

```python
# Categoria com taxa nula + spread OK = SEMPRE LUCRA
market = "Geopolitics"      # 0.0% taxa
spread = 2.0%              # Spread decente
gross_profit = $60
net_profit = $60.00        # 100% do lucro bruto!

# Bot executa
logger.info("Trade executado: lucro garantido após taxas")
```

---

## 🔔 Alertas Automáticos

O bot alerta em casos de:

1. **Categoria desconhecida**
   ```
   ⚠️ [WARN] Categoria não detectada para 'Novo Mercado'
   Usando taxa padrão: 2.0%
   ```

2. **Spread insuficiente após taxas**
   ```
   ⚠️ [WARN] Spread insuficiente: 1.2% < 1.8% (taxa)
   Pulando trade (inviável)
   ```

3. **Promoção detectada (0% taxa)**
   ```
   ✅ [INFO] Categoria com taxa 0% detectada!
   Lucro = Lucro bruto (sem redução)
   ```

---

## 📈 Otimizações Futuras

### 1. Priorizar por Taxa

```python
# Classificar mercados por lucratividade esperada
# = (spread - taxa) * capital

# Executar primeiro os mais lucrativos
trades_ranked = sorted(
    trades,
    key=lambda t: (t.spread - t.fee) * CAPITAL_POR_OP,
    reverse=True
)
```

### 2. Cache de Taxas

```python
# Cache taxas por 1 hora para evitar re-detecção
# Polymarket pode mudar categorias eventualmente
CACHE_FEES_TTL = 3600  # 1 hora
```

### 3. Webhooks para Mudanças

```python
# Monitorar API do Polymarket
# Alertar quando taxas mudam
# Exemplo: Geopolitics 0% → 0.5%
```

---

## 🔗 Referências

- Documentação Polymarket: https://docs.polymarket.com/fees
- Announcement Março 2026: (simular link)
- Suporte: support@polymarket.com

---

## 🤖 Comandos Úteis

### Verificar Taxa de um Mercado

```bash
python -c "
from bot.executor import ContractExecutor
from bot.config import POLYMARKET_CATEGORY_FEES

executor = ContractExecutor()
fees = executor.get_category_fee('Bitcoin')
print(f'Taxa para Bitcoin: {fees[0]}% taker, {fees[1]}% maker')
"
```

### Listar Todas as Categorias

```bash
python -c "
from bot.config import POLYMARKET_CATEGORY_FEES
for cat, (taker, maker) in POLYMARKET_CATEGORY_FEES.items():
    print(f'{cat:20s}: {taker}% taker, {maker}% maker')
"
```

### Calcular Lucro Esperado

```bash
python -c "
from bot.executor import ContractExecutor

executor = ContractExecutor()
gross = 100  # $100 lucro bruto
net = executor.calculate_profit_after_fees(gross, 'Bitcoin')
print(f'Lucro líquido para \$100 bruto em Bitcoin: \${net:.2f}')
"
```

---

**Última atualização:** Julho 2026
**Versão do Bot:** 1.0.0+ (com suporte a taxas dinâmicas)

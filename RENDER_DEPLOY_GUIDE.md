# 🚀 Deploy no Render

## Quick Start (5 minutos)

### 1. Vai em https://render.com

Conecta sua conta GitHub (autoriza Render)

### 2. Clica em "New Web Service"

```
┌─────────────────────────────┐
│ New Web Service             │
└─────────────────────────────┘
         ↓
    GitHub
         ↓
  victorhf220/flashtrader
```

### 3. Configura o Serviço

```
Name:              flashtrader-bot
Repository:        victorhf220/flashtrader
Branch:            main
Root Directory:    (deixa vazio)
Environment:       Docker
Plan:              Free (ou $7/mês para 24/7)
Auto-deploy:       Yes
```

### 4. Clica em "Create Web Service"

Render vai:
- Detectar `Dockerfile` automaticamente
- Build a imagem Docker
- Fazer deploy
- Iniciar o bot

### 5. Aguarda o deploy (2-3 minutos)

Quando verde = pronto!

```
✅ Live at: https://flashtrader-bot.onrender.com
```

---

## Configurar Variáveis de Ambiente

**No Render Dashboard → Settings → Environment Variables:**

```env
PRIVATE_KEY=0xSUA_CHAVE_PRIVADA_AQUI
CONTRACT_ADDRESS=0xSEU_CONTRATO_DEPLOYADO
PY_BOT_WALLET=0xSUA_CARTEIRA_PYTHON
POLYGON_RPC=https://polygon-rpc.com
DRY_RUN=true
SCORE_LIMIAR=0.3
SPREAD_MINIMO=0.03
CAPITAL_POR_OP=3000
```

⚠️ **NÃO coloque valores reais de chave privada aqui no início**
- Comece com `DRY_RUN=true`
- Deixa rodar 1-2 dias vendo logs
- Se tudo OK, muda pra `DRY_RUN=false` e `CAPITAL_POR_OP=100`

---

## Monitorar o Bot

### Logs em Tempo Real

No Render dashboard:
```
Logs → Real-time tail
```

Você vê tudo que o bot está fazendo:

```
2026-07-17 10:15:22 [INFO] Analisando mercados...
2026-07-17 10:15:25 [INFO] Bitcoin score: 0.65 ✅
2026-07-17 10:15:26 [INFO] Ethereum score: 0.32 ✅
2026-07-17 10:15:30 [INFO] Requisitando flash loan...
2026-07-17 10:15:35 [INFO] ✅ Flash loan executado
```

### Status do Bot

```
https://flashtrader-bot.onrender.com/api/status
```

Retorna JSON com:
```json
{
  "status": "running",
  "uptime": 3600,
  "operations": 5,
  "last_profit": 57.30,
  "total_profit": 286.50
}
```

### Métricas

No Render dashboard → Metrics:
- CPU usage
- Memory usage
- Network I/O
- Build logs

---

## Troubleshooting

### ❌ "Build failed"

**Causas comuns:**
```bash
# 1. requirements.txt ruim
   → Tira "py-clob-client" no início (lib experimental)
   → Usa apenas: vaderSentiment, web3, requests, flask

# 2. Versão Python incompatível
   → Usa Python 3.11+ (já está no Dockerfile)

# 3. Arquivo faltando
   → Checa se bot/main.py existe
   → Checa se contracts/ tem os arquivos
```

**Solução:**
```bash
git add -A
git commit -m "Fix: remover py-clob-client temporário"
git push
# Render faz re-deploy automaticamente
```

### ⚠️ "Health check failing"

Significa o bot está crashando repetidamente.

**Debug:**
1. Clica em "Logs"
2. Procura por "ERROR" ou "Traceback"
3. Copia o erro
4. Corrige localmente
5. Faz commit e push

**Causa comum:** Falta variável de ambiente
```bash
# Render Settings → Environment
# Verifica se PRIVATE_KEY, CONTRACT_ADDRESS, etc. estão lá
```

### 🟡 "Free plan suspended after 15 min inactivity"

Normal no plano gratuito.

**Soluções:**
1. **Upgrade pra pago** ($7/mês = 24/7)
2. **Usar cron job** que faz ping a cada 10 min
3. **Rodar em VPS próprio** (melhor longo prazo)

---

## Upgrade para Pago ($7/mês)

### Por que upgradar?

| Recurso | Free | Pro ($7/mês) |
|---------|------|-------------|
| Uptime | Hibernação 15min | 24/7 continuo ✅ |
| Suporte | Comunidade | Priority |
| Builds | 100/mês | Unlimited |
| Discos | Removido ao restart | Persistente ✅ |

### Como fazer upgrade

1. **Render Dashboard** → Settings → Plan
2. **Click em "Upgrade to Pro"**
3. **Seleciona Pro**
4. **Autoriza cartão de crédito**

Pronto! Bot roda 24/7.

---

## Monitorar em Produção

### Alertas

Render suporta webhooks. Configure em seu Slack/Discord:

```
Render Settings → Notifications
Add: Slack/Discord webhook
Alert on: Deploy failure, Health check failing
```

### Logs Persistentes

No plano Free, logs são perdidos ao reiniciar.

**Solução:**
```bash
# Usar Render Disk (pago)
# Ou enviar logs pra serviço externo:
# - LogDNA
# - Datadog
# - Papertrail
```

---

## Próximas Ações

1. **Hoje:**
   - [ ] Deploy em Render (free plan)
   - [ ] Configure variáveis de ambiente
   - [ ] Mude `DRY_RUN=true`

2. **Amanhã:**
   - [ ] Monitorar logs por 24h
   - [ ] Validar que não há crashes
   - [ ] Checar dashboard: `/api/status`

3. **Em 1-2 dias:**
   - [ ] Se tudo OK, upgrade pra pago ($7/mês)
   - [ ] Mude `DRY_RUN=false`
   - [ ] Comece com `CAPITAL_POR_OP=100` (100 USDC)

4. **Em 1-2 semanas:**
   - [ ] Valide lucros
   - [ ] Escale capital conforme ganhar
   - [ ] Considere VPS próprio se lucro for grande

---

## Links Úteis

- [Render Docs](https://render.com/docs)
- [Docker na Render](https://render.com/docs/deploy-docker)
- [Variáveis de Ambiente](https://render.com/docs/environment-variables)
- [Health Checks](https://render.com/docs/health-checks)

---

**Deploy agora e bom luck! 🚀**

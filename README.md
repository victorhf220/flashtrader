# Sentinel Arbitrage Bot

Bot de arbitragem automatizado que combina **análise de sentimento multi-source** com **flash loans da Aave** para execução de trades no **Polymarket**.

## 🎯 Características

- ✅ **Análise de Sentimento Multi-Source**: Twitter, Reddit, Telegram, NewsAPI
- ✅ **Flash Loans**: Alavanca capital da Aave V3 sem colateral
- ✅ **Smart Contract Solidity**: Execução segura via contrato inteligente
- ✅ **Bot Robusto**: Circuit breakers, retry logic, error handling
- ✅ **Dashboard Tempo Real**: Flask + Chart.js com métricas ao vivo
- ✅ **SQLite**: Histórico completo de operações
- ✅ **DRY RUN**: Teste sem usar capital real
- ✅ **Logging Completo**: Rastreamento detalhado de todas as ações

## ⚠️ AVISOS DE SEGURANÇA

1. **Nunca compartilhe sua chave privada**. Use uma wallet separada com fundos limitados.
2. **Teste em DRY_RUN primeiro**. Execute por pelo menos 1 semana antes de ativar transações reais.
3. **Flash loans têm riscos**. Arbitrage é arriscado; você pode perder tudo.
4. **Market volatility**. Preços mudam rápido; spreads podem desaparecer instantaneamente.
5. **Gas fees**. Cada transação custa gas. Lucro deve ser > gas + taxa Aave.

## 📋 Pré-requisitos

### Sistema
- Python 3.9+
- pip
- Git
- Ubuntu/Linux (recomendado para produção)

### Carteira
- MetaMask ou outra wallet Ethereum-compatible
- Polygon mainnet configurada
- Fundos em USDC na Polygon (ex: $5000+ para começar)

### Chaves de API

#### Twitter API v2
- Acesse https://developer.twitter.com/en/portal/dashboard
- Crie uma aplicação
- Gere um Bearer Token

#### Reddit API
- Acesse https://www.reddit.com/prefs/apps
- Crie um "script" application
- Anote Client ID e Client Secret

#### NewsAPI
- Acesse https://newsapi.org
- Crie uma conta
- Gere uma API key

#### Telegram (opcional)
- Documentação: https://docs.telethon.dev/
- Requer Phone Number + API Hash do Telegram

## 🚀 Instalação Rápida

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/sentinel-arbitrage.git
cd sentinel-arbitrage
```

### 2. Crie ambiente virtual
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale dependências
```bash
pip install -r requirements.txt
```

### 4. Configure .env
```bash
cp .env.example .env
# Edite .env com suas chaves e valores
nano .env
```

### 5. Deploy do Contrato Smart (Solidity)

#### Opção A: Remix (GUI - mais fácil)
1. Acesse https://remix.ethereum.org
2. Crie um arquivo `FlashTrader.sol`
3. Copie o conteúdo de `contracts/FlashTrader.sol`
4. Compile com Solidity 0.8.10+
5. Faça deploy na Polygon mainnet via MetaMask
6. Copie o endereço do contrato
7. Cole em `.env` como `CONTRACT_ADDRESS`

#### Opção B: Hardhat (CLI - mais profissional)
```bash
# Instale Hardhat
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox

# Crie projeto Hardhat
npx hardhat

# Copie contrato para hardhat/contracts/
cp contracts/FlashTrader.sol hardhat/contracts/

# Configure hardhat.config.js para Polygon
# Faça deploy
npx hardhat run scripts/deploy.js --network polygon
```

### 6. Teste o Bot em DRY RUN
```bash
# Certifique-se que DRY_RUN=true em .env
python bot/main.py
```

Você deve ver:
```
================================
SENTINEL ARBITRAGE BOT INICIALIZADO
Mercados: ['BTC', 'ETH', 'SOL']
Intervalo: 60s
Score Limiar: 0.3
================================
```

### 7. Rode o Dashboard (em outro terminal)
```bash
python web/api.py
```

Acesse: http://localhost:5000

### 8. Ative Transações Reais (após testar)
```bash
# Edite .env
# DRY_RUN=false
# Comece com CAPITAL_POR_OP baixo (ex: 100 USDC)

python bot/main.py
```

## 📊 Fluxo de Funcionamento

```
┌─────────────────────────────────────┐
│   Coleta Dados de Sentimento        │
│ (Twitter, Reddit, News, Telegram)   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Calcula Score Agregado            │
│   (Ponderado por fonte)             │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Score > 0.3? │
        │   (BUY)      │
        └──────┬───────┘
               │
        ┌──────┴──────┐
        │             │
       SIM           NÃO
        │             │
        ▼             ▼
    ┌─────┐    ┌──────────────┐
    │ YES │    │ Score < -0.3?│
    └─────┘    │   (SELL)     │
        │      └──────┬───────┘
        │             │
        │            SIM
        │             │
        │            NÃO
        │             │
        │             ▼
        │          HOLD
        │          (skip)
        │
        └──────────┬─────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  Chama Smart Contract        │
    │  executeArbitrage()          │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  Aave V3 Flash Loan          │
    │  (3000 USDC)                 │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  Polymarket CTF Exchange     │
    │  Buy/Sell Shares             │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  Repaga Flash Loan + Taxa    │
    │  Profit = Proceeds - Loan - Gas│
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────┐
    │  Registra em SQLite          │
    │  Atualiza Dashboard          │
    └──────────────────────────────┘
```

## 🔧 Configuração Avançada

### Ajustar Pesos de Sentimento
Em `bot/config.py`:
```python
SENTIMENT_WEIGHTS = {
    "twitter": 0.3,   # Aumente para confiar mais em Twitter
    "reddit": 0.25,
    "telegram": 0.2,
    "news": 0.25,
}
```

### Alterar Intervalos de Scan
```python
INTERVALO = 30  # Scan a cada 30s (cuidado: mais caro em gas)
```

### Limitar Capital por Operação
```python
CAPITAL_POR_OP = 500  # Comece pequeno, aumente depois
```

### Aumentar Sensibilidade
```python
SCORE_LIMIAR = 0.2  # Mais sensível (mais trades, mais risco)
```

## 📈 Monitoramento

### Logs
```bash
tail -f logs/bot.log
```

### Dashboard
Acesse http://localhost:5000 no navegador

### Métricas em Tempo Real
- Lucro total / hoje / semana / mês
- Número de operações
- Lucro médio por operação
- Gráfico de lucro acumulado

## 🛡️ Gestão de Erros

O bot implementa **circuit breakers** automáticos:

1. **2 erros consecutivos** → Pausa 10 minutos
2. **3+ erros totais** → Pausa 1 hora
3. Reseta contador ao executar com sucesso

Monitore `logs/bot.log` para entender falhas.

## 🔐 Boas Práticas

### 1. Rotação de Chaves
```bash
# A cada 30 dias
# 1. Gere uma nova wallet
# 2. Transfira fundos
# 3. Atualize PRIVATE_KEY em .env
```

### 2. Backup do Banco de Dados
```bash
cp database/sentinel.db database/sentinel.db.backup
```

### 3. Monitoramento 24/7
```bash
# Use systemd, supervisor ou similar para manter rodando
# Veja scripts/ para exemplos
```

### 4. Alertas
Implemente notificações Telegram (opcional):
```python
# Em bot/main.py
if success:
    send_telegram_alert(f"✓ Trade {term}: ${profit}")
```

## 📚 Estrutura de Pastas

```
sentinel-arbitrage/
├── contracts/
│   └── FlashTrader.sol           # Smart contract Solidity
├── bot/
│   ├── __init__.py
│   ├── main.py                   # Loop principal
│   ├── sentiment.py              # Análise de sentimento
│   ├── executor.py               # Executor de trades
│   └── config.py                 # Configurações
├── database/
│   ├── db.py                     # SQLite utilities
│   └── sentinel.db               # Database (gerado)
├── web/
│   ├── api.py                    # API Flask
│   ├── templates/
│   │   └── dashboard.html        # Frontend
│   └── static/
│       ├── script.js             # JavaScript
│       └── style.css             # CSS
├── logs/                         # Logs (gerado)
├── .env                          # Variáveis de ambiente (GITIGNORED)
├── .env.example                  # Template
├── .gitignore
├── requirements.txt              # Dependências Python
└── README.md                     # Este arquivo
```

## 🧪 Testando Componentes

### Testar Análise de Sentimento
```python
from bot.sentiment import SentimentAnalyzer

analyzer = SentimentAnalyzer()
score = analyzer.get_aggregated_sentiment("Bitcoin")
print(f"Sentimento BTC: {score}")
```

### Testar Conexão Blockchain
```python
from bot.executor import ContractExecutor

executor = ContractExecutor()
print(f"Conectado? {executor.is_connected()}")
stats = executor.get_contract_stats()
print(stats)
```

### Testar Database
```python
from database.db import save_operation, get_operations

save_operation("BTC", "YES", 0.5, 100, "SUCCESS", "Test")
ops = get_operations(limit=10)
print(ops)
```

## 🚀 Deploy em VPS (Hostinger)

### 1. SSH
```bash
ssh root@seu_vps_ip
```

### 2. Setup Ubuntu
```bash
apt update && apt upgrade -y
apt install python3-pip python3-venv git -y
```

### 3. Clone Repo
```bash
cd /opt
git clone https://github.com/seu-usuario/sentinel-arbitrage.git
cd sentinel-arbitrage
```

### 4. Setup Venv
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Systemd Service
Crie `/etc/systemd/system/sentinel.service`:
```ini
[Unit]
Description=Sentinel Arbitrage Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sentinel-arbitrage
Environment="PATH=/opt/sentinel-arbitrage/venv/bin"
ExecStart=/opt/sentinel-arbitrage/venv/bin/python bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Inicie:
```bash
systemctl enable sentinel
systemctl start sentinel
systemctl status sentinel
```

### 6. Nginx para Dashboard
```bash
apt install nginx -y

# Crie /etc/nginx/sites-available/sentinel
upstream flask_app {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name seu_dominio.com;

    location / {
        proxy_pass http://flask_app;
    }
}

# Ative
ln -s /etc/nginx/sites-available/sentinel /etc/nginx/sites-enabled/
systemctl restart nginx
```

## 📞 Suporte

### Problemas Comuns

**"ConnectionError ao conectar RPC"**
- Verifique POLYGON_RPC em .env
- Teste: `curl https://polygon-rpc.com`

**"Transação falls com 'Invalid flash loan'"**
- Certifique-se que o contrato tem saldo em USDC
- Verifique se `CONTRACT_ADDRESS` está correto
- Teste em Polygonscan

**"Score de sentimento sempre 0"**
- Verifique chaves de API (Twitter, Reddit, etc.)
- Teste cada fonte individualmente
- Aumente LOG level a DEBUG

**"Dashboard não carrega"**
- Certifique-se que Flask está rodando: `python web/api.py`
- Verifique porta 5000: `lsof -i :5000`
- Limpe cache do navegador

## 📄 Licença

MIT License

## ⚡ Próximos Passos

1. **Leia o código** - Entenda cada módulo antes de usar em produção
2. **Teste em DRY_RUN** - Rode por 1+ semana
3. **Monitore lógica** - Sentimento realmente prediz bons trades?
4. **Optimize pesos** - Ajuste SENTIMENT_WEIGHTS baseado em resultados reais
5. **Escale capital** - Aumente CAPITAL_POR_OP gradualmente

## 🤝 Contribuições

Pull requests são bem-vindos. Para grandes mudanças, abra uma issue primeiro.

---

**⚠️ Disclaimer**: Este bot é fornecido "como está" sem garantias. Trading envolve risco. Você pode perder dinheiro. Não sou responsável por perdas.

**Boa sorte! 🚀**

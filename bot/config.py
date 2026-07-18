import os
from dotenv import load_dotenv

load_dotenv()

# ===== BLOCKCHAIN =====
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
POLYGON_RPC_BACKUP = os.getenv("POLYGON_RPC_BACKUP", "https://rpc-mainnet.maticvigil.com")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
AAVE_POOL_PROVIDER = "0xA97684ead0e402dC232d5A977953DF7ECBaB3CDb"  # Polygon Aave Provider

# ===== FASTLANE (MEV / anti-front-running na Polygon) =====
# ⚠️ Aplicável à arbitragem DEX-a-DEX real (Uniswap/QuickSwap), NÃO ao fluxo
# atual de Polymarket em FlashTrader.sol, que já foi documentado como
# inviável on-chain (ver POLYMARKET_ONCHAIN_LIMITACAO.md). Ver avisos
# completos em bot/fastlane_client.py antes de habilitar em produção.
USE_FASTLANE = os.getenv("USE_FASTLANE", "false").lower() == "true"
FASTLANE_RELAY_URL = os.getenv("FASTLANE_RELAY_URL", "https://relay.fastlane.xyz")
# Lance mínimo/máximo em MATIC (wei) que o bot está disposto a ofertar no
# leilão do FastLane pela prioridade de inclusão. Ajuste com base no lucro
# líquido esperado da operação (o lance não pode "comer" o lucro).
FASTLANE_MIN_BID_WEI = int(os.getenv("FASTLANE_MIN_BID_WEI", str(int(0.001 * 1e18))))
FASTLANE_MAX_BID_WEI = int(os.getenv("FASTLANE_MAX_BID_WEI", str(int(0.05 * 1e18))))
# Quantos blocos de deadline dar à SolverOperation antes que ela expire
FASTLANE_DEADLINE_BLOCKS = int(os.getenv("FASTLANE_DEADLINE_BLOCKS", "5"))

# ===== API KEYS =====
TWITTER_BEARER = os.getenv("TWITTER_BEARER", "")
REDDIT_CLIENT = os.getenv("REDDIT_CLIENT", "")
REDDIT_SECRET = os.getenv("REDDIT_SECRET", "")
TELEGRAM_ID = os.getenv("TELEGRAM_ID", "")
TELEGRAM_HASH = os.getenv("TELEGRAM_HASH", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# ===== NOTIFICAÇÕES (OPCIONAL) =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ===== PARÂMETROS DO BOT =====
CAPITAL_POR_OP = int(os.getenv("CAPITAL_POR_OP", "3000"))  # USDC por operação
SPREAD_MINIMO = float(os.getenv("SPREAD_MINIMO", "0.03"))  # 3% de spread mínimo
SCORE_LIMIAR = float(os.getenv("SCORE_LIMIAR", "0.3"))  # Threshold de sentimento
INTERVALO = int(os.getenv("INTERVALO", "60"))  # Segundos entre scans
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
CATEGORIA = os.getenv("CATEGORIA", "geopolitics")  # Para taxa zero no Polymarket
MERCADOS = os.getenv("MERCADOS", "BTC,ETH,SOL").split(",")
SLIPPAGE_TOLERANCE = float(os.getenv("SLIPPAGE_TOLERANCE", "0.02"))  # 2% tolerância de slippage (proteção)

# ===== CACHE E LIMITE =====
CACHE_SENTIMENTO_TTL = int(os.getenv("CACHE_SENTIMENTO_TTL", "300"))  # 5 minutos (configurável)
MAX_ERROS_CONSECUTIVOS = 2
PAUSA_APOS_ERROS = 600  # 10 minutos
MAX_ERROS_TOTAL = 3
PAUSA_APOS_MUITOS_ERROS = 3600  # 1 hora

# ===== PESOS DE SENTIMENTO =====
SENTIMENT_WEIGHTS = {
    "twitter": 0.3,
    "reddit": 0.25,
    "telegram": 0.2,
    "news": 0.25,
}

# ===== TAXAS DINÂMICAS POLYMARKET (Março 2026) =====
# Referência: https://docs.polymarket.com/fees
POLYMARKET_CATEGORY_FEES = {
    # Categoria: (fee_taker%, fee_maker%)
    "geopolitics": (0.0, 0.0),      # 0% - Promoção especial
    "esports": (0.75, 0.0),          # 0.75% taker, 0% maker
    "crypto": (1.8, 0.0),            # 1.8% taker, 0% maker
    "sports": (0.75, 0.0),           # 0.75% taker, 0% maker
    "elections": (0.5, 0.0),         # 0.5% taker, 0% maker
    "economics": (1.0, 0.0),         # 1.0% taker, 0% maker
    "weather": (2.0, 0.0),           # 2.0% taker, 0% maker
    "science": (1.5, 0.0),           # 1.5% taker, 0% maker
    "entertainment": (1.5, 0.0),     # 1.5% taker, 0% maker
    "default": (2.0, 0.0),           # 2.0% para categorias não listadas
}

# Mapeamento alternativo de categoria (por nome de mercado)
MARKET_CATEGORY_MAP = {
    "bitcoin": "crypto",
    "ethereum": "crypto",
    "btc": "crypto",
    "eth": "crypto",
    "sol": "crypto",
    "solana": "crypto",
    "trump": "elections",
    "biden": "elections",
    "election": "elections",
    "election 2024": "elections",
    "election 2026": "elections",
    "nfl": "sports",
    "nba": "sports",
    "world cup": "sports",
    "olympics": "sports",
    "fed rate": "economics",
    "inflation": "economics",
    "unemployment": "economics",
    "gdp": "economics",
    "hurricane": "weather",
    "earthquake": "weather",
    "temperature": "weather",
}

# ===== ENDEREÇOS DE MERCADOS POLYMARKET (CTF) =====
# Esses são exemplos - SUBSTITUA pelos endereços reais de seus mercados
# Encontre em: https://polymarket.com ou https://clob.polymarket.com/markets
MARKET_ADDRESSES = {
    # Exemplo de mercados (SUBSTITUA pelos seus):
    # Geopolitics (0% fee - PRIORIDADE!)
    "putin ukraine": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "taiwan invasion": "0x" + "0"*40,  # TODO: Adicionar endereço real
    
    # Elections
    "trump 2024": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "biden": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "election 2024": "0x" + "0"*40,  # TODO: Adicionar endereço real
    
    # Crypto (1.8% fee - evitar)
    "bitcoin": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "ethereum": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "bitcoin 100k": "0x" + "0"*40,  # TODO: Adicionar endereço real
    
    # Sports
    "nfl": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "world cup": "0x" + "0"*40,  # TODO: Adicionar endereço real
    
    # Economics
    "fed rate": "0x" + "0"*40,  # TODO: Adicionar endereço real
    "inflation": "0x" + "0"*40,  # TODO: Adicionar endereço real
}

# Endereço padrão para mercados não configurados (opcional)
# Se vazio, o bot pula mercados sem endereço configurado
DEFAULT_MARKET_ADDRESS = None

# ===== URLs POLYMARKET =====
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_API_URL = "https://polymarket.com/api"

# ===== LOGS =====
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

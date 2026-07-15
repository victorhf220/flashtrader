import os
from dotenv import load_dotenv

load_dotenv()

# ===== BLOCKCHAIN =====
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
POLYGON_RPC_BACKUP = os.getenv("POLYGON_RPC_BACKUP", "https://rpc-mainnet.maticvigil.com")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
AAVE_POOL_PROVIDER = "0xA97684ead0e402dC232d5A977953DF7ECBaB3CDb"  # Polygon Aave Provider

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

# ===== CACHE E LIMITE =====
CACHE_SENTIMENTO_TTL = 300  # 5 minutos
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

# ===== URLs POLYMARKET =====
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_API_URL = "https://polymarket.com/api"

# ===== LOGS =====
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

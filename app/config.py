import os
from dotenv import load_dotenv

load_dotenv()
APP_NAME = os.getenv("APP_NAME", "JARVIS AI")
API_TOKEN = os.getenv("JARVIS_API_TOKEN", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "jarvis.db")
# Delta Exchange India public API. Override only if your account/region uses another host.
DELTA_BASE_URL = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange").rstrip("/")
DELTA_READONLY_ENABLED = os.getenv("DELTA_READONLY_ENABLED", "false").lower() == "true"
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
NEWS_RSS_URLS = [x.strip() for x in os.getenv("NEWS_RSS_URLS", "").split(",") if x.strip()]
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
NTFY_BASE_URL = os.getenv("NTFY_BASE_URL", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "").strip()
LOCAL_AGENT_URL = os.getenv("LOCAL_AGENT_URL", "").rstrip("/")
LOCAL_AGENT_TOKEN = os.getenv("LOCAL_AGENT_TOKEN", "")
POLL_SECONDS = max(30, int(os.getenv("POLL_SECONDS", "60")))
MARKET_POLL_SECONDS = max(30, int(os.getenv("MARKET_POLL_SECONDS", "60")))
DELTA_SYMBOLS = [x.strip().upper() for x in os.getenv("DELTA_SYMBOLS", "BTCUSD,ETHUSD").split(",") if x.strip()]
DELTA_RESOLUTION = os.getenv("DELTA_RESOLUTION", "5m").strip()
DELTA_LOOKBACK_CANDLES = min(500, max(50, int(os.getenv("DELTA_LOOKBACK_CANDLES", "150"))))
SR_PIVOT_WINDOW = min(5, max(2, int(os.getenv("SR_PIVOT_WINDOW", "3"))))
SR_APPROACH_PCT = min(0.03, max(0.0005, float(os.getenv("SR_APPROACH_PCT", "0.003"))))
ALERT_COOLDOWN_MINUTES = min(1440, max(5, int(os.getenv("ALERT_COOLDOWN_MINUTES", "60"))))

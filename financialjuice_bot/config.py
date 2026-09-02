import os


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None and raw.strip() else default


FINANCIALJUICE_RSS_URL = os.getenv(
    "FINANCIALJUICE_RSS_URL",
    "https://www.financialjuice.com/feed.ashx?xy=rss",
)

STATE_PATH = os.getenv("STATE_PATH", "data/state.json")
LOOKBACK_MINUTES = env_int("LOOKBACK_MINUTES", 180)
MAX_NEWS_ITEMS = env_int("MAX_NEWS_ITEMS", 100)
STATE_RETENTION_DAYS = env_int("STATE_RETENTION_DAYS", 14)
HTTP_TIMEOUT = env_int("HTTP_TIMEOUT", 25)
POLL_MINUTES = env_int("POLL_MINUTES", 5)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Baku")

ENABLE_NEWS = env_bool("ENABLE_NEWS", True)
ENABLE_CALENDAR = env_bool("ENABLE_CALENDAR", True)
ALERT_30M = env_bool("ALERT_30M", True)
ALERT_15M = env_bool("ALERT_15M", True)
ALERT_5M = env_bool("ALERT_5M", True)
ALERT_ACTUAL = env_bool("ALERT_ACTUAL", True)

MARKETS = tuple(
    x.strip().upper()
    for x in os.getenv(
        "MARKETS", "XAUUSD,DXY,EURUSD,GBPUSD,USDJPY,USDCAD"
    ).split(",")
    if x.strip()
)

TE_API_KEY = os.getenv("TRADING_ECONOMICS_API_KEY", "").strip()
CALENDAR_MIN_IMPORTANCE = env_int("CALENDAR_MIN_IMPORTANCE", 1)
CALENDAR_LOOKAHEAD_HOURS = env_int("CALENDAR_LOOKAHEAD_HOURS", 48)
CALENDAR_LOOKBACK_HOURS = env_int("CALENDAR_LOOKBACK_HOURS", 6)
CALENDAR_COUNTRIES = tuple(
    x.strip()
    for x in os.getenv(
        "CALENDAR_COUNTRIES",
        "united states,euro area,united kingdom,japan,canada,australia,new zealand,switzerland",
    ).split(",")
    if x.strip()
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DRY_RUN = env_bool("DRY_RUN", False)

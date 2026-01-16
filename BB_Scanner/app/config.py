"""Configuration constants"""

# BetBoom URLs
LIVE_URL = "https://betboom.ru/sport/table-tennis?period=all&type=live"

# Signal conditions
FAV_MATCH_MAX = 1.20  # Максимальный коэффициент фаворита по матчу
MAX_MATCH_ODDS = FAV_MATCH_MAX  # Для обратной совместимости
FAVORITE_SETS_LEAD = (2, 0)  # Фаворит ведёт 2:0

# Dominance thresholds
DOMINANCE_MIN = 65  # Минимальный dominance для сигнала

# Set 3 odds thresholds
SET3_HIGH_ODDS = 1.90  # Высокий кф на 3-й сет (перекос) - TYPE A
SET3_FAIR_TOO_EQUAL_MIN = 1.75  # Минимум для "подозрительно равной линии" - TYPE C
SET3_FAIR_TOO_EQUAL_MAX = 2.05  # Максимум для "подозрительно равной линии" - TYPE C
MIN_SET3_ODDS = SET3_HIGH_ODDS  # Для обратной совместимости

# TYPE B signal conditions (1:0 + set2 lead)
SET2_MIN_LEAD = 3  # Минимальное преимущество в очках во 2-м сете
SET2_MIN_LEADER_POINTS = 6  # Минимум очков у лидера во 2-м сете
SET2_MAX_LEADER_POINTS = 9  # Максимум очков у лидера во 2-м сете (чтобы не ловить концовку)

# General
SET3_EARLY_MAX_POINTS = 1  # Максимум очков в 3-м сете для сигнала (0:0/1:0/0:1)
DOMINANCE_PRE_FILTER = 55  # Предварительный фильтр dominance перед открытием деталки

# Anti-spam
COOLDOWN_SEC = 180  # Cooldown между алертами на один матч (секунды)
RE_ALERT_ODDS_DELTA = 0.15  # Повторный алерт если кф вырос на эту величину

# Scan intervals (seconds)
SCAN_INTERVAL_MIN = 2
SCAN_INTERVAL_MAX = 5

# Browser settings
MAX_TABS = 3
BROWSER_HEADLESS = False
BROWSER_TIMEOUT = 30000  # ms

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Storage
APP_DATA_DIR = "app_data"
SIGNALS_CSV = "signals.csv"
SIGNALS_DB = "signals.sqlite"
ERRORS_LOG = "errors.log"


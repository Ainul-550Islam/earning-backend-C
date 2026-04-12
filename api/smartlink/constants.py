"""
SmartLink System Constants
CPAlead-style affiliate smartlink platform constants.
"""

# Slug configuration
SLUG_DEFAULT_LENGTH = 8
SLUG_MIN_LENGTH = 4
SLUG_MAX_LENGTH = 32
SLUG_ALLOWED_CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789'
SLUG_RESERVED_WORDS = [
    'admin', 'api', 'go', 'click', 'track', 'static', 'media',
    'login', 'logout', 'register', 'dashboard', 'health', 'status',
]

# Cache keys
CACHE_PREFIX_SMARTLINK = 'sl:'
CACHE_PREFIX_CLICK = 'cl:'
CACHE_PREFIX_EPC = 'epc:'
CACHE_PREFIX_CAP = 'cap:'
CACHE_PREFIX_FRAUD = 'fraud:'
CACHE_PREFIX_DOMAIN = 'domain:'
CACHE_PREFIX_OFFER_SCORE = 'offer_score:'

# Cache TTLs (seconds)
CACHE_TTL_SMARTLINK = 300          # 5 minutes
CACHE_TTL_TARGETING = 600          # 10 minutes
CACHE_TTL_OFFER_POOL = 60          # 1 minute (changes frequently)
CACHE_TTL_EPC_SCORE = 1800         # 30 minutes
CACHE_TTL_DOMAIN = 3600            # 1 hour
CACHE_TTL_UNIQUE_CLICK = 86400     # 24 hours (dedup window)
CACHE_TTL_FRAUD_IP = 3600          # 1 hour

# Performance targets
TARGET_REDIRECT_MS = 5             # <5ms redirect target
MAX_REDIRECT_CHAIN_HOPS = 5        # max hops in redirect chain

# Click tracking
CLICK_DEDUP_WINDOW_HOURS = 24
MAX_SUB_PARAMS = 5                 # sub1 to sub5
MAX_CUSTOM_PARAMS = 10

# Fraud detection thresholds
FRAUD_SCORE_FLAG_THRESHOLD = 60    # 0-100 score
FRAUD_SCORE_BLOCK_THRESHOLD = 85
MAX_CLICKS_PER_IP_PER_HOUR = 50
MAX_CLICKS_PER_IP_PER_DAY = 200
BOT_UA_PATTERNS = [
    'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
    'python-requests', 'java/', 'go-http-client', 'libwww',
    'headlesschrome', 'phantomjs', 'selenium',
]

# A/B Test
AB_TEST_MIN_SAMPLE_SIZE = 100
AB_TEST_CONFIDENCE_LEVEL = 0.95
AB_TEST_MAX_VARIANTS = 10

# Offer rotation
ROTATION_MAX_RETRIES = 3           # retries when offer is capped/unavailable
EPC_SMOOTHING_FACTOR = 0.1         # for EPC moving average
EPC_MIN_CLICKS_FOR_SCORE = 10      # min clicks before EPC-based routing

# Cap tracking
CAP_RESET_HOUR = 0                 # midnight UTC
CAP_BUFFER_PERCENT = 5             # 5% buffer before hard cap

# Publisher settings
MAX_CUSTOM_DOMAINS_PER_PUBLISHER = 5
MAX_SMARTLINKS_PER_PUBLISHER = 1000
MAX_OFFER_POOL_SIZE = 100

# Analytics
STAT_ROLLUP_INTERVAL_MINUTES = 60  # hourly rollup
HEATMAP_UPDATE_INTERVAL_MINUTES = 30
EPC_UPDATE_INTERVAL_MINUTES = 30

# Redirect
REDIRECT_TIMEOUT_SECONDS = 3
DEFAULT_FALLBACK_URL = 'https://example.com'

# Domain verification
DOMAIN_DNS_TXT_PREFIX = 'smartlink-verify='
DOMAIN_VERIFY_TIMEOUT_SECONDS = 10

# Tracking pixel
PIXEL_ENDPOINT = '/pixel/fire/'
S2S_PIXEL_TIMEOUT_SECONDS = 2

# Geo
GEO_IP_HEADER_PRIORITY = [
    'HTTP_CF_IPCOUNTRY',      # Cloudflare
    'HTTP_X_REAL_IP',
    'HTTP_X_FORWARDED_FOR',
    'REMOTE_ADDR',
]

# API rate limits (per minute)
API_RATE_LIMIT_REDIRECT = 10000    # public redirect endpoint
API_RATE_LIMIT_PUBLISHER = 1000    # publisher API
API_RATE_LIMIT_ADMIN = 500

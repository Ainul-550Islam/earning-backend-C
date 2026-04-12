# api/publisher_tools/constants.py
"""
Publisher Tools — সব constant values এক জায়গায়।
"""

# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_REVENUE_SHARE = 70.0          # পাবলিশার পাবে 70%
MIN_REVENUE_SHARE     = 30.0
MAX_REVENUE_SHARE     = 95.0

PUBLISHER_ID_PREFIX   = 'PUB'
PUBLISHER_ID_LENGTH   = 6             # PUB000001

API_KEY_LENGTH        = 64
API_SECRET_LENGTH     = 128

# ──────────────────────────────────────────────────────────────────────────────
# SITE CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

SITE_ID_PREFIX        = 'SITE'
SITE_ID_LENGTH        = 6             # SITE000001

MIN_QUALITY_SCORE     = 0
MAX_QUALITY_SCORE     = 100
QUALITY_SCORE_GOOD    = 70            # 70+ = Good
QUALITY_SCORE_POOR    = 40            # 40- = Poor

# ads.txt verification check interval (hours)
ADS_TXT_CHECK_INTERVAL = 24

# ──────────────────────────────────────────────────────────────────────────────
# APP CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

APP_ID_PREFIX         = 'APP'
APP_ID_LENGTH         = 6             # APP000001

PLAY_STORE_BASE_URL   = 'https://play.google.com/store/apps/details?id='
APP_STORE_BASE_URL    = 'https://apps.apple.com/app/'

# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

UNIT_ID_PREFIX        = 'UNIT'
UNIT_ID_LENGTH        = 6             # UNIT000001

# Standard banner sizes (width x height)
BANNER_SIZES = {
    'banner':      (320, 50),
    'leaderboard': (728, 90),
    'rectangle':   (300, 250),
    'skyscraper':  (160, 600),
    'billboard':   (970, 250),
    'half_page':   (300, 600),
    'large_rect':  (336, 280),
}

# eCPM floor price defaults (USD)
DEFAULT_FLOOR_PRICE       = 0.0
MIN_FLOOR_PRICE           = 0.0
MAX_FLOOR_PRICE           = 100.0

# Refresh interval limits (seconds)
MIN_REFRESH_INTERVAL      = 15
MAX_REFRESH_INTERVAL      = 300
DEFAULT_REFRESH_INTERVAL  = 30

# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

MAX_WATERFALL_ITEMS       = 20
DEFAULT_BID_TIMEOUT_MS    = 1000      # 1 second
MIN_BID_TIMEOUT_MS        = 100
MAX_BID_TIMEOUT_MS        = 5000

WATERFALL_OPTIMIZE_INTERVAL = 24      # hours

# ──────────────────────────────────────────────────────────────────────────────
# EARNING CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

EARNING_DECIMAL_PLACES    = 6
REVENUE_DECIMAL_PLACES    = 4

# IVT threshold — এর বেশি হলে revenue deduct হবে
IVT_DEDUCTION_THRESHOLD   = 10.0     # 10% IVT acceptable

# ──────────────────────────────────────────────────────────────────────────────
# PAYMENT CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

INVOICE_NUMBER_FORMAT     = 'INV-{year}-{month:02d}-{count:06d}'

# Default minimum payout thresholds (USD)
MIN_PAYOUT_THRESHOLDS = {
    'paypal':        10.00,
    'bank_transfer': 100.00,
    'wire':          500.00,
    'crypto_btc':    50.00,
    'crypto_usdt':   10.00,
    'payoneer':      50.00,
    'bkash':         5.00,
    'nagad':         5.00,
    'rocket':        5.00,
    'check':         100.00,
}

# Processing fees (USD flat)
PROCESSING_FEES = {
    'paypal':        1.00,
    'bank_transfer': 5.00,
    'wire':          25.00,
    'crypto_btc':    2.00,
    'crypto_usdt':   1.00,
    'payoneer':      3.00,
    'bkash':         0.50,
    'nagad':         0.50,
    'rocket':        0.50,
    'check':         5.00,
}

# Net payment terms (days)
PAYMENT_NET_TERMS = {
    'monthly':   30,
    'bimonthly': 15,
    'weekly':    7,
    'on_demand': 3,
}

# ──────────────────────────────────────────────────────────────────────────────
# FRAUD / QUALITY CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

FRAUD_SCORE_SAFE       = 30           # 0-30 = safe
FRAUD_SCORE_SUSPICIOUS = 50           # 31-50 = suspicious
FRAUD_SCORE_HIGH_RISK  = 70           # 51-70 = high risk
FRAUD_SCORE_BLOCKED    = 80           # 80+ = auto-block

MAX_IVT_PERCENTAGE     = 20.0         # এর বেশি = publisher warning
CRITICAL_IVT_THRESHOLD = 40.0         # এর বেশি = suspend

# Quality score components weights
QUALITY_WEIGHT_VIEWABILITY = 0.35
QUALITY_WEIGHT_CONTENT     = 0.30
QUALITY_WEIGHT_TRAFFIC     = 0.25
QUALITY_WEIGHT_PERFORMANCE = 0.10

# Core Web Vitals thresholds (ms)
LCP_GOOD     = 2500
LCP_NEEDS_IMPROVEMENT = 4000
FID_GOOD     = 100
FID_NEEDS_IMPROVEMENT = 300
CLS_GOOD     = 0.1
CLS_NEEDS_IMPROVEMENT = 0.25

# ──────────────────────────────────────────────────────────────────────────────
# A/B TESTING CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

MIN_STATISTICAL_CONFIDENCE = 95.0     # 95% confidence required
MIN_TEST_DURATION_DAYS     = 7        # minimum 7 days
MAX_VARIANTS               = 5        # maximum 5 variants per test
MIN_SAMPLE_SIZE            = 1000     # minimum 1000 impressions per variant

# ──────────────────────────────────────────────────────────────────────────────
# CACHE CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

CACHE_TTL_SHORT    = 60               # 1 minute
CACHE_TTL_MEDIUM   = 300              # 5 minutes
CACHE_TTL_LONG     = 3600             # 1 hour
CACHE_TTL_DAY      = 86400            # 24 hours

CACHE_KEY_PREFIX   = 'pub_tools'

# Cache key templates
CACHE_PUBLISHER_STATS   = f'{CACHE_KEY_PREFIX}:publisher:{{publisher_id}}:stats'
CACHE_SITE_QUALITY      = f'{CACHE_KEY_PREFIX}:site:{{site_id}}:quality'
CACHE_UNIT_PERFORMANCE  = f'{CACHE_KEY_PREFIX}:unit:{{unit_id}}:performance'
CACHE_EARNING_DAILY     = f'{CACHE_KEY_PREFIX}:earning:{{publisher_id}}:{{date}}'
CACHE_WATERFALL         = f'{CACHE_KEY_PREFIX}:waterfall:{{group_id}}'

# ──────────────────────────────────────────────────────────────────────────────
# REPORT CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

REPORT_DATE_FORMAT    = '%Y-%m-%d'
REPORT_DATETIME_FORMAT= '%Y-%m-%d %H:%M:%S'
MAX_REPORT_DAYS       = 365           # maximum 1 year lookback

# Supported report export formats
EXPORT_FORMATS = ['csv', 'xlsx', 'json', 'pdf']

# ──────────────────────────────────────────────────────────────────────────────
# WEBHOOK CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_MAX_RETRIES     = 3
WEBHOOK_RETRY_DELAYS    = [60, 300, 900]  # 1min, 5min, 15min

# ──────────────────────────────────────────────────────────────────────────────
# CURRENCY CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_CURRENCY = 'USD'

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'BDT': '৳',
    'INR': '₹',
    'JPY': '¥',
    'AED': 'د.إ',
    'SAR': '﷼',
}

SUPPORTED_CURRENCIES = list(CURRENCY_SYMBOLS.keys())

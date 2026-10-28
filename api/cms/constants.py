# api/cms/constants.py
"""All CMS constants — numbers, strings, limits."""
from decimal import Decimal

# ── CPAlead ──────────────────────────────────────────────────────
CPALEAD_OFFER_FEED_URL    = "https://api.cpalead.com/offers.php"
CPALEAD_OFFERWALL_CDN     = "https://cdn.cpalead.com/offerwall/v2/offerwall.min.js"
CPALEAD_POSTBACK_RESPONSE = "1"          # Must return exactly "1" on success
CPALEAD_REFERRAL_RATE     = Decimal("0.05")   # 5% of referral earnings
CPALEAD_REFERRAL_MONTHS   = 6            # Active for 6 months
CPALEAD_DAILY_PAYOUT_MIN  = Decimal("1.00")   # $1 minimum daily payout

# ── Virtual Currency ──────────────────────────────────────────────
DEFAULT_COIN_RATIO        = Decimal("100")  # $1 = 100 coins
MAX_DAILY_COINS_EARN      = Decimal("5000")
MAX_POSTBACK_PAYOUT_USD   = Decimal("100")  # Reject suspicious amounts

# ── Rate Limits ───────────────────────────────────────────────────
MAX_CLICKS_PER_IP_HOUR    = 10
MAX_POSTBACKS_PER_IP_DAY  = 500
MIN_CLICK_INTERVAL_SEC    = 30
POSTBACK_SLA_MS           = 200          # CPAlead expects fast response

# ── Cache TTLs (seconds) ──────────────────────────────────────────
CACHE_TTL_SITE_CONFIG     = 300          # 5 min
CACHE_TTL_OFFER_FEED      = 1800         # 30 min
CACHE_TTL_LEADERBOARD     = 3600         # 1 hour
CACHE_TTL_HEALTH_CHECK    = 60           # 1 min
CACHE_TTL_USER_BALANCE    = 60           # 1 min
CACHE_TTL_STREAK          = 300          # 5 min

# ── Circuit Breaker ───────────────────────────────────────────────
CIRCUIT_FAIL_THRESHOLD    = 5
CIRCUIT_TIMEOUT_SEC       = 300          # 5 min cooldown
CIRCUIT_HALF_OPEN_TRIES   = 2

# ── Pagination ────────────────────────────────────────────────────
PAGE_SIZE_DEFAULT         = 20
PAGE_SIZE_MAX             = 100
PAGE_SIZE_SMALL           = 10

# ── Withdrawal Fees ───────────────────────────────────────────────
WITHDRAWAL_FEE_RATE       = Decimal("0.02")   # 2%
WITHDRAWAL_MIN_USD = {
    'paypal':   Decimal("1.00"),
    'payoneer': Decimal("1.00"),
    'usdt':     Decimal("25.00"),  # CPAlead USDT Fast Pay Jul 2025
    'bitcoin':  Decimal("10.00"),
    'wire':     Decimal("100.00"),
    'ach':      Decimal("10.00"),
    'bank':     Decimal("50.00"),
}

# ── Survey & Profile Constants ─────────────────────────────────────
SURVEY_MIN_QUESTIONS        = 5
SURVEY_MAX_QUESTIONS        = 100
SURVEY_MIN_COMPLETION_TIME   = 60   # 1 minute minimum
SURVEY_MAX_COMPLETION_TIME   = 7200 # 2 hours maximum
SURVEY_QUALITY_THRESHOLD     = 0.7  # 70% minimum quality score
SURVEY_BONUS_QUALITY_MIN     = 0.8  # 80% quality for bonus
SURVEY_SPEEDING_THRESHOLD    = 10   # seconds per question threshold
SURVEY_MAX_FAILED_CHECKS    = 3    # maximum failed attention checks

PROFILE_COMPLETENESS_MIN    = 50   # 50% minimum completeness
PROFILE_COMPLETENESS_GOOD   = 80   # 80% considered good
PROFILE_INTERESTS_MAX        = 20   # maximum interests allowed
PROFILE_LANGUAGES_MAX        = 5    # maximum additional languages

SEGMENT_MIN_USERS            = 10   # minimum users for segment
SEGMENT_MAX_CRITERIA        = 10   # maximum criteria per segment

# ── Reward Management Constants ───────────────────────────────────
REWARD_MIN_AMOUNT            = Decimal("0.01")
REWARD_MAX_AMOUNT            = Decimal("1000.00")
REWARD_DAILY_LIMIT           = Decimal("100.00")
REWARD_MONTHLY_LIMIT         = Decimal("1000.00")

POOL_MIN_BUDGET            = Decimal("100.00")
POOL_MAX_BUDGET            = Decimal("100000.00")
POOL_REFILL_THRESHOLD        = 20    # 20% remaining triggers refill
POOL_UTILIZATION_WARNING     = 70    # 70% utilization warning
POOL_UTILIZATION_CRITICAL    = 90    # 90% utilization critical

TRANSACTION_BATCH_SIZE       = 100
TRANSACTION_TIMEOUT_MIN     = 30    # 30 minutes timeout
TRANSACTION_MAX_RETRIES    = 3

# ── Task Management Constants ─────────────────────────────────────
TASK_MAX_RUNTIME_SECONDS     = 3600  # 1 hour maximum
TASK_DEFAULT_TIMEOUT        = 1800  # 30 minutes default
TASK_MAX_RETRIES           = 5
TASK_RETRY_DELAY_BASE      = 60    # 1 minute base delay
TASK_MEMORY_LIMIT_MB       = 512   # 512MB default memory limit

QUEUE_MAX_SIZE             = 10000
QUEUE_PROCESSING_BATCH     = 50
QUEUE_RETRY_DELAY_MIN     = 5     # 5 minutes minimum retry delay

LOCK_DEFAULT_TIMEOUT       = 300   # 5 minutes default lock timeout
LOCK_MAX_TIMEOUT          = 3600  # 1 hour maximum lock timeout
LOCK_CLEANUP_INTERVAL     = 900   # 15 minutes cleanup interval

# ── Notification Constants ─────────────────────────────────────────
NOTIFICATION_BATCH_SIZE     = 100
NOTIFICATION_RETRY_ATTEMPTS = 3
NOTIFICATION_RETRY_DELAY    = 300   # 5 minutes retry delay

EMAIL_RATE_LIMIT_PER_MIN   = 60
EMAIL_RATE_LIMIT_PER_HOUR  = 1000
PUSH_RATE_LIMIT_PER_MIN   = 100
PUSH_RATE_LIMIT_PER_HOUR  = 5000

# ── Analytics & Reporting Constants ───────────────────────────────
ANALYTICS_CACHE_TTL        = 1800  # 30 minutes
ANALYTICS_BATCH_SIZE       = 1000
ANALYTICS_RETENTION_DAYS   = 90    # 3 months retention

REPORT_GENERATION_TIMEOUT   = 300   # 5 minutes max
REPORT_MAX_ROWS            = 50000 # maximum rows per report
REPORT_EXPORT_FORMATS      = ['csv', 'xlsx', 'pdf']

# ── Security & Validation Constants ───────────────────────────────
MAX_LOGIN_ATTEMPTS         = 5
LOGIN_LOCKOUT_MINUTES      = 15
PASSWORD_MIN_LENGTH        = 8
PASSWORD_MAX_LENGTH        = 128
SESSION_TIMEOUT_MINUTES    = 1440  # 24 hours

API_RATE_LIMIT_PER_MIN     = 1000
API_RATE_LIMIT_PER_HOUR    = 10000
API_TOKEN_EXPIRE_HOURS    = 24

# ── Performance & Monitoring Constants ─────────────────────────────
SLOW_REQUEST_THRESHOLD_MS  = 1000  # 1 second threshold
MEMORY_WARNING_PERCENTAGE    = 80    # 80% memory usage warning
CPU_WARNING_PERCENTAGE       = 70    # 70% CPU usage warning

HEALTH_CHECK_INTERVAL       = 60    # 1 minute health checks
METRICS_RETENTION_HOURS    = 720   # 30 days metrics retention

# ── File Upload & Storage Constants ───────────────────────────────
MAX_UPLOAD_SIZE_MB         = 50
ALLOWED_IMAGE_TYPES       = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_DOCUMENT_TYPES    = ['pdf', 'doc', 'docx', 'txt', 'csv']

FILE_STORAGE_PATH          = 'cms/uploads/'
THUMBNAIL_SIZE           = (300, 300)  # width, height
IMAGE_QUALITY            = 85

# ── Integration & External API Constants ───────────────────────────
EXTERNAL_API_TIMEOUT       = 30    # 30 seconds timeout
EXTERNAL_API_RETRIES      = 3
WEBHOOK_TIMEOUT_SECONDS    = 10
WEBHOOK_MAX_RETRIES      = 5

INTEGRATION_CACHE_TTL    = 600   # 10 minutes cache
INTEGRATION_BATCH_SIZE    = 50

# ── Streak Multipliers ────────────────────────────────────────────
STREAK_MAX_MULTIPLIER     = Decimal("2.0")
STREAK_PER_DAY_INCREMENT  = Decimal("0.033")

# ── Content Blocks ────────────────────────────────────────────────
MAX_BLOCKS_PER_PAGE       = 50
MAX_BLOCK_DATA_SIZE_KB    = 500

# ── User Levels (USD thresholds) ─────────────────────────────────
LEVEL_THRESHOLDS = {
    7: 1000,   # Elite
    6: 500,    # Diamond
    5: 200,    # Platinum
    4: 100,    # Gold
    3: 50,     # Silver
    2: 10,     # Bronze
    1: 0,      # Beginner
}

# ── Quiz ──────────────────────────────────────────────────────────
MAX_QUESTIONS_PER_QUIZ    = 20
MAX_ANSWERS_PER_QUESTION  = 10
QUIZ_ATTEMPT_TIMEOUT_MIN  = 60  # 1 hour to complete

# ── Referral ──────────────────────────────────────────────────────
REFERRAL_CODE_LENGTH      = 8
REFERRAL_DEDUP_WINDOW_SEC = 60

# ── SmartLink ─────────────────────────────────────────────────────
SMARTLINK_MAX_RULES       = 100

# ── Attachment Upload ─────────────────────────────────────────────
ATTACHMENT_MAX_SIZE_MB    = 10
ATTACHMENT_ALLOWED_TYPES  = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf', 'video/mp4', 'video/webm',
    'text/csv', 'application/zip',
]

# ── Misc ──────────────────────────────────────────────────────────
CMS_VERSION               = "2.0.0"
CMS_API_PREFIX            = "/api/cms"

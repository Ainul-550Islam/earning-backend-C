"""
api/tasks/constants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
System-wide constants for the task system.
All magic numbers, limits, timeouts, and configuration
values are defined here for easy tuning without code changes.
"""

from decimal import Decimal

# ══════════════════════════════════════════════════════════════════════════════
# PAYOUT THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

# CPAlead-style minimum payouts per method
MIN_PAYOUT = {
    'paypal':      Decimal('1.00'),
    'payoneer':    Decimal('5.00'),
    'usdt_trc20':  Decimal('25.00'),
    'usdt_erc20':  Decimal('25.00'),
    'bitcoin':     Decimal('50.00'),
    'ethereum':    Decimal('30.00'),
    'bank_wire':   Decimal('100.00'),
    'bank_ach':    Decimal('5.00'),
    'bkash':       Decimal('0.75'),
    'nagad':       Decimal('0.75'),
    'rocket':      Decimal('0.75'),
    'wise':        Decimal('5.00'),
    'cashapp':     Decimal('5.00'),
    'venmo':       Decimal('5.00'),
    'gift_card':   Decimal('5.00'),
    'default':     Decimal('0.75'),
}

# Maximum single withdrawal
MAX_WITHDRAWAL_AMOUNT = Decimal('10000.00')

# Minimum test traffic purchase (CPAlead self-serve)
MIN_TEST_TRAFFIC_SPEND = Decimal('5.00')

# Revenue share by publisher tier
PUBLISHER_REVENUE_SHARE = {
    'platinum': Decimal('0.85'),
    'gold':     Decimal('0.80'),
    'silver':   Decimal('0.75'),
    'bronze':   Decimal('0.70'),
}

# Platform fee (1 - publisher share)
PLATFORM_FEE_RATE = Decimal('0.30')  # default 30%

# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICATION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# XP required per level
XP_PER_LEVEL = {
    1: 0,        2: 100,      3: 250,
    4: 500,      5: 1000,     6: 2000,
    7: 4000,     8: 8000,     9: 15000,
    10: 30000,   15: 100000,  20: 500000,
    25: 1500000, 30: 5000000,
}

MAX_LEVEL = 30
XP_PER_TASK_COMPLETION = 5
XP_PER_REFERRAL = 50
XP_PER_SURVEY = 20
XP_PER_QUIZ = 15

# Community points
COMMUNITY_POINTS_PER_DOLLAR = 1000

# Streak bonuses (XP)
STREAK_XP_BONUS = {
    1:  5,    3: 30,   7: 70,
    14: 140,  30: 300, 60: 600, 90: 900,
}

# Milestone bonuses (total earnings → cash bonus)
MILESTONE_BONUSES = {
    Decimal('1'):    Decimal('0.10'),
    Decimal('10'):   Decimal('0.50'),
    Decimal('50'):   Decimal('2.00'),
    Decimal('100'):  Decimal('5.00'),
    Decimal('250'):  Decimal('10.00'),
    Decimal('500'):  Decimal('25.00'),
    Decimal('1000'): Decimal('75.00'),
    Decimal('5000'): Decimal('500.00'),
}

# Prize tiers (monthly community points)
PRIZE_TIERS = {
    10000:   {'name': 'Bronze Prize',   'value': '$10 Amazon Gift Card'},
    50000:   {'name': 'Silver Prize',   'value': '$50 Amazon Gift Card'},
    100000:  {'name': 'Gold Prize',     'value': '$100 + Merchandise'},
    500000:  {'name': 'Platinum Prize', 'value': '$500 Cash'},
    1000000: {'name': 'Diamond Prize',  'value': 'Luxury Item'},
}

# ══════════════════════════════════════════════════════════════════════════════
# FRAUD DETECTION THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

FRAUD_SCORE_CLEAN    = 20
FRAUD_SCORE_LOW      = 40
FRAUD_SCORE_MEDIUM   = 60
FRAUD_SCORE_HIGH     = 80
FRAUD_SCORE_CRITICAL = 90

MAX_COMPLETIONS_PER_HOUR     = 20
MAX_CONVERSIONS_PER_IP_HOUR  = 5
MAX_EMAIL_SUBMITS_PER_IP_HOUR = 10
MAX_QUIZ_COMPLETIONS_PER_IP_HOUR = 10
MAX_CLICKS_PER_AD_PER_HOUR   = 50

# Velocity windows
VELOCITY_WINDOW_SECONDS    = 3600   # 1 hour
DEDUP_WINDOW_DAYS          = 30
CLICK_DEDUP_TTL            = 3600
POSTBACK_DEDUP_TTL         = 86400 * 7
QUIZ_DEDUP_TTL             = 86400 * 30
EMAIL_SUBMIT_DEDUP_TTL     = 86400 * 30
CPI_DEDUP_TTL              = 86400 * 7
OVERLAY_DEDUP_TTL          = 86400 * 30

# Traffic quality thresholds
TRAFFIC_TIER1_MIN_SCORE = 80
TRAFFIC_TIER2_MIN_SCORE = 50
TRAFFIC_TIER3_MIN_SCORE = 20
AUTO_BLACKLIST_SCORE    = 10

# ══════════════════════════════════════════════════════════════════════════════
# KYC WITHDRAWAL LIMITS
# ══════════════════════════════════════════════════════════════════════════════

KYC_DAILY_WITHDRAWAL_LIMIT = {
    'none':     Decimal('10.00'),
    'basic':    Decimal('100.00'),
    'standard': Decimal('500.00'),
    'full':     Decimal('5000.00'),
    'edd':      Decimal('50000.00'),
}

KYC_ROTATION_DAYS     = 90
API_KEY_ROTATION_DAYS = 90

# ══════════════════════════════════════════════════════════════════════════════
# CACHE TTLs (seconds)
# ══════════════════════════════════════════════════════════════════════════════

CACHE_TTL_SHORT      = 60       # 1 minute
CACHE_TTL_MEDIUM     = 300      # 5 minutes
CACHE_TTL_LONG       = 1800     # 30 minutes
CACHE_TTL_HOUR       = 3600     # 1 hour
CACHE_TTL_DAY        = 86400    # 24 hours
CACHE_TTL_WEEK       = 604800   # 7 days
CACHE_TTL_MONTH      = 2592000  # 30 days
CACHE_TTL_PERMANENT  = None     # No expiry

# Specific cache TTLs
OFFER_FEED_TTL        = 600     # 10 min
RTB_BID_CACHE_TTL     = 30      # 30 sec (critical path)
FLOOR_PRICE_TTL       = 300     # 5 min
CRYPTO_RATE_TTL       = 300     # 5 min
WEB3_RATE_TTL         = 300     # 5 min
GEO_ROUTING_TTL       = 1800    # 30 min
LOCKER_STATS_TTL      = 1800    # 30 min
USER_SEGMENT_TTL      = 86400   # 1 day
FRAUD_SCORE_TTL       = 3600    # 1 hour
KYC_STATUS_TTL        = 3600    # 1 hour
PPC_RATE_TTL          = 300     # 5 min
UNLOCK_TOKEN_TTL      = 86400   # 24 hours (overlays)
QUIZ_SESSION_TTL      = 7200    # 2 hours

# ══════════════════════════════════════════════════════════════════════════════
# CELERY QUEUE NAMES
# ══════════════════════════════════════════════════════════════════════════════

QUEUE_HIGH     = 'high'
QUEUE_DEFAULT  = 'default'
QUEUE_LOW      = 'low'
QUEUE_PAYMENTS = 'payments'
QUEUE_EMAILS   = 'emails'
QUEUE_REPORTS  = 'reports'
QUEUE_ML       = 'ml'
QUEUE_WEBHOOKS = 'webhooks'

ALL_QUEUES = [
    QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW,
    QUEUE_PAYMENTS, QUEUE_EMAILS, QUEUE_REPORTS,
    QUEUE_ML, QUEUE_WEBHOOKS,
]

# ══════════════════════════════════════════════════════════════════════════════
# TASK TIMEOUTS (seconds)
# ══════════════════════════════════════════════════════════════════════════════

TASK_TIMEOUT_SHORT    = 60      # 1 min  — simple DB ops
TASK_TIMEOUT_MEDIUM   = 300     # 5 min  — API calls
TASK_TIMEOUT_LONG     = 1800    # 30 min — bulk processing
TASK_TIMEOUT_REPORT   = 3600    # 1 hour — reports
TASK_TIMEOUT_BACKUP   = 7200    # 2 hours — backups
TASK_TIMEOUT_ML       = 14400   # 4 hours — ML training
TASK_TIMEOUT_WORKFLOW = 7200    # 2 hours — workflows

# Soft time limits (before hard kill)
TASK_SOFT_TIMEOUT_DEFAULT = 270  # 4.5 min before 5 min hard

# ══════════════════════════════════════════════════════════════════════════════
# RETRY CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_MAX_RETRIES        = 3
PAYMENT_MAX_RETRIES        = 5
POSTBACK_MAX_RETRIES       = 5
WEBHOOK_MAX_RETRIES        = 5
CRYPTO_MAX_RETRIES         = 3
NOTIFICATION_MAX_RETRIES   = 3

DEFAULT_RETRY_DELAY        = 60     # 1 min
PAYMENT_RETRY_DELAY        = 30     # 30 sec
POSTBACK_RETRY_DELAY       = 15     # 15 sec
WEBHOOK_RETRY_DELAY        = 30     # 30 sec
CRYPTO_RETRY_DELAY         = 60     # 1 min

# ══════════════════════════════════════════════════════════════════════════════
# PAGINATION & BATCH SIZES
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_PAGE_SIZE     = 20
MAX_PAGE_SIZE         = 100
BATCH_SIZE_SMALL      = 50
BATCH_SIZE_MEDIUM     = 200
BATCH_SIZE_LARGE      = 1000
BATCH_SIZE_BULK       = 5000

LEADERBOARD_TOP_N     = 100
EVENT_HISTORY_MAX     = 500
DLQ_SUMMARY_EMAIL_TOP_N = 5

# ══════════════════════════════════════════════════════════════════════════════
# CPALEAD SPECIFIC
# ══════════════════════════════════════════════════════════════════════════════

CPALEAD_MIN_PAYOUT      = Decimal('0.75')  # CPAlead daily min
CPALEAD_USDT_MIN        = Decimal('25.00')  # USDT Fast Pay min
CPALEAD_TEST_TRAFFIC_MIN = Decimal('5.00')  # Self-serve test traffic min

# Attribution windows
CPA_ATTRIBUTION_WINDOW_DAYS = 30
CPI_ATTRIBUTION_WINDOW_DAYS = 7
CPL_ATTRIBUTION_WINDOW_DAYS = 14

# Minimum clicks for CVR calculation
MIN_CLICKS_FOR_CVR = 100
MIN_CLICKS_FOR_ROTATE = 1000

# RTB auction
RTB_MIN_BID      = Decimal('0.001')
RTB_DEFAULT_FLOOR = Decimal('0.001')
RTB_AUCTION_TIMEOUT_MS = 100   # 100ms hard deadline

# Ad serving
PPC_DEFAULT_RATE = Decimal('0.03')   # $0.03/click default
CPM_DEFAULT_RATE = Decimal('1.00')   # $1.00/1000 impressions

# ══════════════════════════════════════════════════════════════════════════════
# OVERLAY LOCKER
# ══════════════════════════════════════════════════════════════════════════════

OVERLAY_PAYOUT = {
    '0h':   Decimal('0.05'),
    '24h':  Decimal('0.10'),
    '720h': Decimal('0.25'),
}

# ══════════════════════════════════════════════════════════════════════════════
# DATA RETENTION (days)
# ══════════════════════════════════════════════════════════════════════════════

RETENTION_TASK_PERF_LOGS     = 30
RETENTION_CLICK_LOGS         = 90
RETENTION_SESSION_DATA       = 7
RETENTION_QUEUE_SNAPSHOTS    = 7
RETENTION_WEBHOOK_LOGS       = 30
RETENTION_IMPRESSION_LOGS    = 30
RETENTION_POSTBACK_LOGS      = 90
RETENTION_AUDIT_LOGS         = 365
RETENTION_BACKUP_FILES       = 30
RETENTION_GDPR_EXPORTS       = 30
RETENTION_DORMANT_USERS      = 365  # auto-deactivate after 1 year

# ══════════════════════════════════════════════════════════════════════════════
# EXPORT ALL
# ══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Payouts
    'MIN_PAYOUT', 'MAX_WITHDRAWAL_AMOUNT', 'MIN_TEST_TRAFFIC_SPEND',
    'PUBLISHER_REVENUE_SHARE', 'PLATFORM_FEE_RATE',
    # Gamification
    'XP_PER_LEVEL', 'MAX_LEVEL', 'XP_PER_TASK_COMPLETION',
    'XP_PER_REFERRAL', 'XP_PER_SURVEY', 'XP_PER_QUIZ',
    'COMMUNITY_POINTS_PER_DOLLAR', 'STREAK_XP_BONUS',
    'MILESTONE_BONUSES', 'PRIZE_TIERS',
    # Fraud
    'FRAUD_SCORE_CLEAN', 'FRAUD_SCORE_LOW', 'FRAUD_SCORE_MEDIUM',
    'FRAUD_SCORE_HIGH', 'FRAUD_SCORE_CRITICAL',
    'MAX_COMPLETIONS_PER_HOUR', 'MAX_CONVERSIONS_PER_IP_HOUR',
    'VELOCITY_WINDOW_SECONDS', 'DEDUP_WINDOW_DAYS',
    'CLICK_DEDUP_TTL', 'POSTBACK_DEDUP_TTL',
    'TRAFFIC_TIER1_MIN_SCORE', 'TRAFFIC_TIER2_MIN_SCORE',
    'TRAFFIC_TIER3_MIN_SCORE', 'AUTO_BLACKLIST_SCORE',
    # KYC
    'KYC_DAILY_WITHDRAWAL_LIMIT', 'KYC_ROTATION_DAYS', 'API_KEY_ROTATION_DAYS',
    # Cache TTLs
    'CACHE_TTL_SHORT', 'CACHE_TTL_MEDIUM', 'CACHE_TTL_LONG',
    'CACHE_TTL_HOUR', 'CACHE_TTL_DAY', 'CACHE_TTL_WEEK',
    'CACHE_TTL_PERMANENT', 'OFFER_FEED_TTL', 'RTB_BID_CACHE_TTL',
    'CRYPTO_RATE_TTL', 'UNLOCK_TOKEN_TTL', 'QUIZ_SESSION_TTL',
    # Queues
    'QUEUE_HIGH', 'QUEUE_DEFAULT', 'QUEUE_LOW', 'QUEUE_PAYMENTS',
    'QUEUE_EMAILS', 'QUEUE_REPORTS', 'QUEUE_ML', 'QUEUE_WEBHOOKS',
    'ALL_QUEUES',
    # Timeouts
    'TASK_TIMEOUT_SHORT', 'TASK_TIMEOUT_MEDIUM', 'TASK_TIMEOUT_LONG',
    'TASK_TIMEOUT_REPORT', 'TASK_TIMEOUT_BACKUP', 'TASK_TIMEOUT_ML',
    # Retries
    'DEFAULT_MAX_RETRIES', 'PAYMENT_MAX_RETRIES', 'POSTBACK_MAX_RETRIES',
    'DEFAULT_RETRY_DELAY', 'PAYMENT_RETRY_DELAY', 'POSTBACK_RETRY_DELAY',
    # Pagination
    'DEFAULT_PAGE_SIZE', 'MAX_PAGE_SIZE', 'BATCH_SIZE_SMALL',
    'BATCH_SIZE_MEDIUM', 'BATCH_SIZE_LARGE', 'LEADERBOARD_TOP_N',
    # CPAlead
    'CPALEAD_MIN_PAYOUT', 'CPALEAD_USDT_MIN', 'CPALEAD_TEST_TRAFFIC_MIN',
    'CPA_ATTRIBUTION_WINDOW_DAYS', 'RTB_MIN_BID', 'PPC_DEFAULT_RATE',
    # Overlay
    'OVERLAY_PAYOUT',
    # Retention
    'RETENTION_TASK_PERF_LOGS', 'RETENTION_CLICK_LOGS',
    'RETENTION_SESSION_DATA', 'RETENTION_QUEUE_SNAPSHOTS',
    'RETENTION_BACKUP_FILES', 'RETENTION_DORMANT_USERS',
]

# ══════════════════════════════════════════════════════════════════════════════
# MISSING CONSTANTS — Added to fix import errors across task files
# ══════════════════════════════════════════════════════════════════════════════

# Postback & Click retention
MAX_POSTBACK_RETRIES          = 5
POSTBACK_RETRY_DELAYS         = [15, 30, 60, 120, 300]   # seconds
POSTBACK_LOG_RETENTION_DAYS   = 90
CLICK_LOG_RETENTION_DAYS      = 90
IMPRESSION_RETENTION_DAYS     = 30
API_LOG_RETENTION_DAYS        = 90
PERFORMANCE_METRIC_RETENTION_DAYS = 30

# Subscription / payment retry
MAX_PAYMENT_RETRY_ATTEMPTS    = 5
PAYMENT_RETRY_INTERVALS_DAYS  = [1, 3, 5, 7, 14]
RENEWAL_REMINDER_DAYS         = 7
TRIAL_ENDING_REMINDER_DAYS    = 3

# Delivery / notification
MAX_DELIVERY_RETRY_ATTEMPTS   = 5

# Webhook
WEBHOOK_TIMEOUT_SECONDS       = 30
WEBHOOK_SIGNATURE_HEADER      = 'X-Webhook-Signature'

# Bot / automation
MAX_BOT_RETRIES               = 3
BOT_HEARTBEAT_INTERVAL_SEC    = 60
TASK_BOT_PROCESS              = 'tasks.auto_mod_tasks.process_bot_queue'

# Points / rewards
POINTS_EXPIRY_DAYS            = 365

# Traffic / IVT
MAX_IVT_PERCENTAGE            = 20
CRITICAL_IVT_THRESHOLD        = 40
WATERFALL_OPTIMIZE_INTERVAL   = 3600   # seconds

# Call / messaging
CALL_RING_TIMEOUT_SECONDS     = 30
CALL_MAX_DURATION_SECONDS     = 3600
PRESENCE_OFFLINE_AFTER_SECONDS = 300

# Inventory / version control
CODE_EXPIRY_WARNING_DAYS      = 7
TASK_EXPIRE_CODES             = 'tasks.inventory_tasks.expire_redemption_codes'
TASK_CHECK_LOW_STOCK          = 'tasks.inventory_tasks.check_low_stock'
TASK_SYNC_STOCK_COUNTS        = 'tasks.inventory_tasks.sync_stock_counts'

# Content moderation / ML
TASK_RUN_IMAGE_SCAN           = 'tasks.auto_mod_tasks.run_image_scan'
TASK_RUN_TEXT_ANALYSIS        = 'tasks.auto_mod_tasks.run_text_analysis'
TASK_SCAN_SUBMISSION          = 'tasks.auto_mod_tasks.scan_submission'
TASK_RETRAIN_MODEL            = 'tasks.ml_tasks.retrain_model'

# Delivery retries
TASK_RETRY_FAILED_DELIVERIES  = 'tasks.inventory_tasks.retry_failed_deliveries'

# Maintenance / version control
TASK_SCHEDULE_MAINTENANCE     = 'tasks.version_control_tasks.schedule_maintenance'
TASK_END_MAINTENANCE          = 'tasks.version_control_tasks.end_maintenance'
TASK_CHECK_UPDATES            = 'tasks.version_control_tasks.check_for_updates'
TASK_CLEANUP_OLD_POLICIES     = 'tasks.version_control_tasks.cleanup_old_policies'

# Promotions
TASK_EVALUATE_RULES           = 'tasks.promotions_tasks.evaluate_promotion_rules'
TASK_CLEANUP_OLD_SUBMISSIONS  = 'tasks.promotions_tasks.cleanup_old_submissions'

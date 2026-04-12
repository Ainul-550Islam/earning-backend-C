"""
api/monetization_tools/constants.py
=====================================
All magic numbers, limits, and config constants.
"""

# ---------------------------------------------------------------------------
# Ad Campaign
# ---------------------------------------------------------------------------
MIN_CAMPAIGN_BUDGET_USD     = 1.00
MAX_CAMPAIGN_BUDGET_USD     = 10_000_000.00
DEFAULT_DAILY_BUDGET_USD    = 100.00
MIN_BID_AMOUNT              = 0.0001
MAX_BID_AMOUNT              = 100.00

# ---------------------------------------------------------------------------
# Ad Unit / Creative
# ---------------------------------------------------------------------------
BANNER_SIZES = [
    (320, 50),    # Mobile Banner
    (300, 250),   # Medium Rectangle
    (728, 90),    # Leaderboard
    (320, 100),   # Large Mobile Banner
    (300, 600),   # Half Page
    (970, 90),    # Large Leaderboard
]
MAX_CREATIVE_FILE_SIZE_MB   = 5
AD_REFRESH_RATE_MIN_SECONDS = 10
AD_REFRESH_RATE_MAX_SECONDS = 300

# ---------------------------------------------------------------------------
# Revenue / eCPM
# ---------------------------------------------------------------------------
DEFAULT_FLOOR_ECPM          = 0.10   # USD
MIN_FLOOR_ECPM              = 0.00
MAX_FLOOR_ECPM              = 500.00

# ---------------------------------------------------------------------------
# Offerwall / Offer
# ---------------------------------------------------------------------------
MAX_OFFER_TITLE_LENGTH      = 300
MAX_OFFER_DESC_LENGTH       = 2000
DEFAULT_OFFER_MIN_AGE       = 13
MAX_DAILY_OFFERS_PER_USER   = 50
OFFER_FRAUD_BLOCK_THRESHOLD = 70    # fraud_score >= this → auto-block

# ---------------------------------------------------------------------------
# Reward / Points
# ---------------------------------------------------------------------------
MIN_REWARD_AMOUNT           = 0.01
MAX_REWARD_AMOUNT           = 1_000_000.00
POINTS_EXPIRY_DAYS          = 365   # points expire after 1 year of inactivity

# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------
MAX_TRIAL_DAYS              = 90
DEFAULT_TRIAL_DAYS          = 7
MAX_SUBSCRIPTION_PLANS      = 10

# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------
MIN_TRANSACTION_AMOUNT      = 1.00   # BDT
MAX_TRANSACTION_AMOUNT      = 500_000.00
MAX_RETRY_ATTEMPTS          = 3
PAYMENT_TIMEOUT_SECONDS     = 300    # 5 minutes

# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------
DEFAULT_XP_MULTIPLIER       = 1.5   # XP needed to next level grows by this factor
MAX_USER_LEVEL              = 100
SPIN_WHEEL_DAILY_LIMIT      = 3
SCRATCH_CARD_DAILY_LIMIT    = 5

# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------
MIN_AB_TEST_CONFIDENCE      = 80.0   # %
DEFAULT_AB_TEST_CONFIDENCE  = 95.0
MAX_AB_VARIANTS             = 5
MIN_AB_TRAFFIC_SPLIT        = 1      # %

# ---------------------------------------------------------------------------
# Waterfall / Mediation
# ---------------------------------------------------------------------------
DEFAULT_WATERFALL_TIMEOUT_MS = 5000
MAX_WATERFALL_ENTRIES        = 20

# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------
CACHE_TTL_AD_UNIT            = 300       # 5 min
CACHE_TTL_OFFERWALL          = 600       # 10 min
CACHE_TTL_LEADERBOARD        = 120       # 2 min
CACHE_TTL_REVENUE_SUMMARY    = 3600      # 1 hour
CACHE_TTL_SUBSCRIPTION_PLAN  = 600       # 10 min

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE            = 20
MAX_PAGE_SIZE                = 100


# ---------------------------------------------------------------------------
# Publisher / Advertiser
# ---------------------------------------------------------------------------
DEFAULT_PAYMENT_TERMS_DAYS   = 30
DEFAULT_CREDIT_LIMIT_USD     = 1000.00
MIN_PUBLISHER_PAYOUT_USD     = 50.00
PUBLISHER_INVOICE_DUE_DAYS   = 15

# ---------------------------------------------------------------------------
# Referral
# ---------------------------------------------------------------------------
MAX_REFERRAL_LEVELS          = 5
DEFAULT_REFERRAL_CODE_LENGTH = 10
MIN_REFERRAL_CODE_LENGTH     = 6
MAX_REFERRAL_CODE_LENGTH     = 20
REFERRAL_LINK_EXPIRY_DAYS    = 0   # 0 = never expires

# ---------------------------------------------------------------------------
# Spin Wheel
# ---------------------------------------------------------------------------
DEFAULT_PRIZE_POOL_SIZE      = 8   # number of segments on wheel
MAX_JACKPOT_PER_DAY          = 1   # max jackpot wins per tenant per day
MIN_PRIZE_WEIGHT             = 1
MAX_PRIZE_WEIGHT             = 10000

# ---------------------------------------------------------------------------
# Flash Sale
# ---------------------------------------------------------------------------
MIN_FLASH_SALE_DURATION_HOURS = 1
MAX_FLASH_SALE_DURATION_DAYS  = 30
MAX_FLASH_SALE_MULTIPLIER     = 10.0
DEFAULT_FLASH_SALE_MULTIPLIER = 2.0

# ---------------------------------------------------------------------------
# Coupon
# ---------------------------------------------------------------------------
DEFAULT_COUPON_CODE_LENGTH    = 8
MAX_COUPON_CODE_LENGTH        = 30
MIN_COUPON_CODE_LENGTH        = 4
MAX_COUPON_DISCOUNT_PCT       = 100.0

# ---------------------------------------------------------------------------
# Payout / Withdrawal
# ---------------------------------------------------------------------------
DEFAULT_EXCHANGE_RATE_BDT_USD = 110.00
MAX_DAILY_PAYOUT_REQUESTS     = 3
PAYOUT_PROCESSING_DAYS        = 3    # business days
PAYOUT_GATEWAY_TIMEOUT_SEC    = 30

# ---------------------------------------------------------------------------
# Fraud / Security
# ---------------------------------------------------------------------------
FRAUD_SCORE_HIGH_THRESHOLD    = 70
FRAUD_SCORE_CRITICAL           = 90
MAX_FAILED_POSTBACKS_PER_IP   = 20
POSTBACK_DEDUP_WINDOW_SEC     = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
MAX_REPORT_DATE_RANGE_DAYS    = 365
DEFAULT_REPORT_DATE_RANGE_DAYS = 30
HOURLY_ROLLUP_BATCH_SIZE      = 1000
DAILY_ROLLUP_BATCH_SIZE       = 500

# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
STREAK_REMINDER_MIN_DAYS      = 7    # only remind if streak >= 7 days
SUBSCRIPTION_EXPIRY_REMINDER_HOURS = 48

# ---------------------------------------------------------------------------
# Creative
# ---------------------------------------------------------------------------
MAX_CREATIVE_HEADLINE_LENGTH  = 200
MAX_CREATIVE_BODY_LENGTH      = 1000
ALLOWED_IMAGE_MIME_TYPES      = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
ALLOWED_VIDEO_MIME_TYPES      = ['video/mp4', 'video/webm', 'video/ogg']
ALLOWED_AUDIO_MIME_TYPES      = ['audio/mpeg', 'audio/ogg', 'audio/wav']

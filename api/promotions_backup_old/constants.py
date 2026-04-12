# =============================================================================
# api/promotions/constants.py
# সব Magic Number ও Config Value এখানে — কোথাও hardcode করা যাবে না
# =============================================================================

from decimal import Decimal


# ─── Campaign ─────────────────────────────────────────────────────────────────
CAMPAIGN_MIN_BUDGET_USD         = Decimal('1.00')
CAMPAIGN_MAX_SLOTS              = 1_000_000
CAMPAIGN_DEFAULT_PROFIT_MARGIN  = Decimal('30.00')   # 30%
CAMPAIGN_TITLE_MIN_LENGTH       = 5
CAMPAIGN_TITLE_MAX_LENGTH       = 200

# ─── Reward / Finance ────────────────────────────────────────────────────────
REWARD_MIN_RATE_USD             = Decimal('0.0001')
REWARD_MIN_PAYOUT_USD           = Decimal('0.01')
WITHDRAWAL_MIN_USD              = Decimal('5.00')
WITHDRAWAL_MAX_USD              = Decimal('10_000.00')
ESCROW_MIN_LOCK_USD             = Decimal('0.01')
REFERRAL_MAX_LEVEL              = 5
REFERRAL_MAX_COMMISSION_RATE    = Decimal('50.00')    # 50%
BONUS_MAX_PERCENT               = Decimal('200.00')   # 200%

# ─── Task / Submission ────────────────────────────────────────────────────────
TASK_STEP_MIN_INSTRUCTION_LEN   = 10
PROOF_MAX_FILE_SIZE_KB          = 10 * 1024           # 10 MB
PROOF_ALLOWED_IMAGE_EXTENSIONS  = ['jpg', 'jpeg', 'png', 'webp']
PROOF_ALLOWED_VIDEO_EXTENSIONS  = ['mp4', 'webm', 'mov']
DISPUTE_REASON_MIN_LENGTH       = 20
TASK_COOLDOWN_MAX_HOURS         = 8_760               # 1 year
VIDEO_MAX_DURATION_SEC          = 3_600               # 1 hour

# ─── Security / Fraud ─────────────────────────────────────────────────────────
FINGERPRINT_HASH_MIN_LENGTH     = 32
TRUST_SCORE_DEFAULT             = 50
TRUST_SCORE_MIN                 = 0
TRUST_SCORE_MAX                 = 100
USER_LEVEL_MIN                  = 1
USER_LEVEL_MAX                  = 100
AI_CONFIDENCE_MIN               = Decimal('0')
AI_CONFIDENCE_MAX               = Decimal('100')
BLACKLIST_REASON_MIN_LENGTH     = 5
IP_SUBMISSION_DEFAULT_LIMIT     = 1
DEVICE_SUBMISSION_DEFAULT_LIMIT = 1

# ─── Analytics ────────────────────────────────────────────────────────────────
ANALYTICS_CACHE_TTL_SECONDS     = 60 * 5             # 5 minutes
CURRENCY_RATE_CACHE_TTL_SECONDS = 60 * 60            # 1 hour

# ─── Pagination ───────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE               = 20
MAX_PAGE_SIZE                   = 100

# ─── Rate Limiting ────────────────────────────────────────────────────────────
THROTTLE_SUBMISSION_PER_MINUTE  = 10
THROTTLE_CAMPAIGN_CREATE_PER_DAY = 20
THROTTLE_DISPUTE_PER_DAY        = 5
THROTTLE_ANON_PER_MINUTE        = 30

# ─── Cache Key Prefixes ───────────────────────────────────────────────────────
CACHE_KEY_CAMPAIGN              = 'promo:campaign:{}'
CACHE_KEY_ANALYTICS             = 'promo:analytics:{}:{}'
CACHE_KEY_CURRENCY_RATE         = 'promo:currency:{}:{}'
CACHE_KEY_BLACKLIST_IP          = 'promo:blacklist:ip:{}'
CACHE_KEY_USER_REPUTATION       = 'promo:reputation:{}'
CACHE_KEY_ESCROW                = 'promo:escrow:{}'

# ─── Celery Task Names ────────────────────────────────────────────────────────
TASK_SYNC_CURRENCY_RATES        = 'promotions.tasks.sync_currency_rates'
TASK_EXPIRE_CAMPAIGNS           = 'promotions.tasks.expire_old_campaigns'
TASK_RECALCULATE_REPUTATION     = 'promotions.tasks.recalculate_user_reputation'
TASK_PROCESS_REFERRAL_PAYOUT    = 'promotions.tasks.process_referral_payout'
TASK_DETECT_FRAUD               = 'promotions.tasks.detect_fraud_submission'
TASK_GENERATE_ANALYTICS         = 'promotions.tasks.generate_daily_analytics'

# ─── Notification Types ───────────────────────────────────────────────────────
NOTIFY_SUBMISSION_APPROVED      = 'submission_approved'
NOTIFY_SUBMISSION_REJECTED      = 'submission_rejected'
NOTIFY_DISPUTE_RESOLVED         = 'dispute_resolved'
NOTIFY_CAMPAIGN_STARTED         = 'campaign_started'
NOTIFY_CAMPAIGN_ENDED           = 'campaign_ended'
NOTIFY_BUDGET_LOW               = 'budget_low'          # budget < 10% remaining
NOTIFY_WITHDRAWAL_PROCESSED     = 'withdrawal_processed'

# ─── HTTP Headers ─────────────────────────────────────────────────────────────
HEADER_DEVICE_FINGERPRINT       = 'X-Device-Fingerprint'
HEADER_APP_VERSION              = 'X-App-Version'
HEADER_PLATFORM                 = 'X-Platform'

# ─── Misc ────────────────────────────────────────────────────────────────────
BUDGET_LOW_THRESHOLD_PERCENT    = Decimal('10.00')    # বাজেটের ১০% বাকি থাকলে warn
DAILY_ANALYTICS_HOUR            = 0                   # midnight UTC তে generate
CURRENCY_BASE                   = 'USD'
DEFAULT_TIMEZONE                = 'UTC'

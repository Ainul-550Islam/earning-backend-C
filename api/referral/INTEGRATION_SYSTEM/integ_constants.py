# api/referral/INTEGRATION_SYSTEM/integ_constants.py
# Integration constants — referral module <-> rest of the project
# ============================================================

# ── Event Names ───────────────────────────────────────────────────────────────
# These event names are used by event_bus.py to route events
# between referral and other modules

# Inbound events (other modules → referral)
EVENT_TASK_COMPLETED        = 'task.completed'         # api/tasks → referral commission
EVENT_OFFER_COMPLETED       = 'offer.conversion.approved'  # api/offer_inventory → referral
EVENT_WITHDRAWAL_APPROVED   = 'wallet.withdrawal.approved' # api/wallet → referral commission
EVENT_DEPOSIT_COMPLETED     = 'wallet.deposit.completed'   # api/wallet → referral commission
EVENT_USER_REGISTERED       = 'user.registered'        # api/users → referral signup
EVENT_USER_TIER_UPGRADED    = 'user.tier.upgraded'     # api/users → referral bonus
EVENT_FRAUD_CONFIRMED       = 'fraud.confirmed'        # api/fraud_detection → clawback

# Outbound events (referral → other modules)
EVENT_COMMISSION_PAID       = 'referral.commission.paid'
EVENT_COMMISSION_HELD       = 'referral.commission.held'
EVENT_COMMISSION_RELEASED   = 'referral.commission.released'
EVENT_COMMISSION_CLAWBACK   = 'referral.commission.clawback'
EVENT_REFERRAL_CREATED      = 'referral.created'
EVENT_REFERRAL_FRAUD_FLAGGED= 'referral.fraud.flagged'
EVENT_MILESTONE_REACHED     = 'referral.milestone.reached'
EVENT_CONTEST_PRIZE_WON     = 'referral.contest.prize_won'
EVENT_CAMPAIGN_STARTED      = 'referral.campaign.started'
EVENT_CAMPAIGN_ENDED        = 'referral.campaign.ended'
EVENT_TREE_REBUILT          = 'referral.tree.rebuilt'

# ── Source Types (matches wallet/services.py source_type) ───────────────────
SOURCE_TASK             = 'task'
SOURCE_OFFER            = 'offer'
SOURCE_WITHDRAWAL       = 'withdrawal'
SOURCE_DEPOSIT          = 'deposit'
SOURCE_SIGNUP           = 'signup'
SOURCE_REFERRAL_COMM    = 'referral'        # wallet adds 'referral' type
SOURCE_MILESTONE        = 'referral_milestone_bonus'
SOURCE_CONTEST          = 'contest_prize'
SOURCE_CLAWBACK         = 'referral_clawback'

# ── App Labels (matches Django app_label settings) ───────────────────────────
APP_REFERRAL            = 'referral'
APP_WALLET              = 'wallet'
APP_TASKS               = 'tasks'
APP_OFFER_INVENTORY     = 'offer_inventory'   # api/offer_inventory
APP_PROMOTIONS          = 'promotions'
APP_NOTIFICATIONS       = 'notifications'
APP_FRAUD_DETECTION     = 'fraud_detection'
APP_ANALYTICS           = 'analytics'
APP_AUDIT_LOGS          = 'audit_logs'
APP_DJOYALTY            = 'djoyalty'
APP_POSTBACK_ENGINE     = 'postback_engine'
APP_ADMIN_PANEL         = 'admin_panel'
APP_USERS               = 'users'
APP_TENANTS             = 'tenants'
APP_RATE_LIMIT          = 'rate_limit'

# ── Cache Keys (follows api/cache/keys/CacheKeyGenerator.py pattern) ────────
CACHE_REFERRAL_SETTINGS      = 'referral:settings:active'
CACHE_ACTIVE_CAMPAIGN        = 'referral:campaign:active'
CACHE_USER_TREE_PREFIX       = 'referral:tree:{user_id}'
CACHE_LEADERBOARD            = 'referral:leaderboard:{period}:{date}'
CACHE_FRAUD_RULES            = 'referral:fraud:rules'
CACHE_CODE_LOOKUP            = 'referral:code:{code}'
CACHE_USER_STATS_PREFIX      = 'referral:stats:{user_id}'
CACHE_CLICK_UNIQUE_PREFIX    = 'referral:click:unique:{code_id}:{ip}'
CACHE_DEVICE_FP_PREFIX       = 'referral:device:{user_id}:{fingerprint}'
CACHE_REFERRAL_PARENT_PREFIX = 'referral:parent:{user_id}'   # matches promotions pattern

# Cache TTLs (seconds)
TTL_SETTINGS        = 300       # 5 min
TTL_CAMPAIGN        = 300       # 5 min
TTL_LEADERBOARD     = 900       # 15 min
TTL_TREE            = 3600      # 1 hour
TTL_FRAUD_RULES     = 600       # 10 min
TTL_CODE_LOOKUP     = 1800      # 30 min
TTL_USER_STATS      = 300       # 5 min
TTL_CLICK_UNIQUE    = 86400     # 24 hours
TTL_DEVICE_FP       = 2592000   # 30 days
TTL_PARENT_REF      = 315360000 # 10 years (permanent-like)

# ── Notification Types (matches api/notifications constants) ─────────────────
NOTIF_TYPE_COMMISSION       = 'referral_commission'
NOTIF_TYPE_NEW_REFERRAL     = 'new_referral'
NOTIF_TYPE_SIGNUP_BONUS     = 'signup_bonus'
NOTIF_TYPE_MILESTONE        = 'milestone_reached'
NOTIF_TYPE_HELD             = 'commission_held'
NOTIF_TYPE_RELEASED         = 'commission_released'
NOTIF_TYPE_CAMPAIGN         = 'campaign_started'
NOTIF_TYPE_CONTEST_RANK     = 'contest_rank_update'
NOTIF_TYPE_CONTEST_PRIZE    = 'contest_prize'
NOTIF_TYPE_WEEKLY_SUMMARY   = 'weekly_summary'
NOTIF_TYPE_FRAUD_ALERT      = 'fraud_alert'
NOTIF_PRIORITY_HIGH         = 'high'
NOTIF_PRIORITY_MEDIUM       = 'medium'
NOTIF_PRIORITY_LOW          = 'low'
NOTIF_CHANNEL_IN_APP        = 'in_app'
NOTIF_CHANNEL_PUSH          = 'push'
NOTIF_CHANNEL_EMAIL         = 'email'

# ── Audit Log Actions (matches api/audit_logs AuditLogAction) ────────────────
AUDIT_REFERRAL_CREATED      = 'REFERRAL_CREATED'
AUDIT_COMMISSION_PAID       = 'REFERRAL_COMMISSION_PAID'
AUDIT_COMMISSION_HELD       = 'REFERRAL_COMMISSION_HELD'
AUDIT_COMMISSION_RELEASED   = 'REFERRAL_COMMISSION_RELEASED'
AUDIT_CLAWBACK_INITIATED    = 'REFERRAL_CLAWBACK_INITIATED'
AUDIT_CLAWBACK_APPROVED     = 'REFERRAL_CLAWBACK_APPROVED'
AUDIT_FRAUD_FLAGGED         = 'REFERRAL_FRAUD_FLAGGED'
AUDIT_FRAUD_CLEARED         = 'REFERRAL_FRAUD_CLEARED'
AUDIT_FRAUD_CONFIRMED       = 'REFERRAL_FRAUD_CONFIRMED'
AUDIT_CAMPAIGN_CREATED      = 'REFERRAL_CAMPAIGN_CREATED'
AUDIT_SETTINGS_UPDATED      = 'REFERRAL_SETTINGS_UPDATED'
AUDIT_BLACKLIST_ADDED       = 'REFERRAL_BLACKLIST_ADDED'
AUDIT_MILESTONE_AWARDED     = 'REFERRAL_MILESTONE_AWARDED'
AUDIT_CONTEST_PRIZE_PAID    = 'REFERRAL_CONTEST_PRIZE_PAID'

# ── Performance Thresholds (for performance_monitor.py) ─────────────────────
PERF_SLOW_QUERY_MS      = 200    # Queries > 200ms = slow
PERF_CRITICAL_MS        = 1000   # > 1s = critical
PERF_COMMISSION_MAX_MS  = 500    # Commission processing max
PERF_FRAUD_CHECK_MAX_MS = 100    # Fraud check must be fast
PERF_TREE_BUILD_MAX_MS  = 2000   # Tree rebuild can be slower

# ── Health Check ─────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL   = 60     # seconds
HEALTH_STALE_TREE_DAYS  = 7
HEALTH_MIN_FRAUD_RULES  = 3      # Alert if < 3 active fraud rules

# ── Message Queue ─────────────────────────────────────────────────────────────
QUEUE_REFERRAL_HIGH     = 'referral_high'      # Commission, fraud
QUEUE_REFERRAL_NORMAL   = 'referral_normal'    # Analytics, notifications
QUEUE_REFERRAL_LOW      = 'referral_low'       # Cleanup, export
MAX_RETRIES             = 3
RETRY_BACKOFF           = 60     # seconds

# ── Integration Versions ──────────────────────────────────────────────────────
INTEGRATION_VERSION     = '2.0.0'
MIN_WALLET_VERSION      = '1.0.0'
MIN_NOTIFICATION_VERSION= '1.0.0'
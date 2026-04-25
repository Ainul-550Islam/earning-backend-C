# integration_system/integ_constants.py
"""
Integration System — Global Constants

All constant values, enums, status codes, event names, and
configuration defaults used across the entire integration system.

CPAlead/earning site integration covers:
  - Notifications ↔ Tasks ↔ Wallet ↔ Withdrawals ↔ Referrals
  - Offers ↔ Surveys ↔ Postbacks ↔ Fraud ↔ Analytics
  - Users ↔ KYC ↔ Admin ↔ Support
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Integration Status Codes
# ---------------------------------------------------------------------------

class IntegStatus:
    """Standard status codes for all integration operations."""
    SUCCESS       = 'success'
    FAILED        = 'failed'
    PENDING       = 'pending'
    PROCESSING    = 'processing'
    RETRYING      = 'retrying'
    SKIPPED       = 'skipped'
    PARTIAL       = 'partial_success'
    TIMEOUT       = 'timeout'
    RATE_LIMITED  = 'rate_limited'
    UNAUTHORIZED  = 'unauthorized'
    NOT_FOUND     = 'not_found'
    CONFLICT      = 'conflict'
    UNAVAILABLE   = 'service_unavailable'
    CANCELLED     = 'cancelled'


# ---------------------------------------------------------------------------
# Module Names (all Django apps in the system)
# ---------------------------------------------------------------------------

class Modules(Enum):
    """All Django application modules."""
    NOTIFICATIONS   = 'notifications'
    TASKS           = 'tasks'
    WALLET          = 'wallet'
    WITHDRAWALS     = 'withdrawals'
    REFERRALS       = 'referrals'
    OFFERS          = 'offers'
    SURVEYS         = 'surveys'
    FRAUD           = 'fraud'
    USERS           = 'users'
    KYC             = 'kyc'
    ANALYTICS       = 'analytics'
    ADMIN           = 'admin'
    SUPPORT         = 'support'
    CAMPAIGNS       = 'campaigns'
    AFFILIATES      = 'affiliates'
    POSTBACKS       = 'postbacks'
    LEADERBOARD     = 'leaderboard'
    ACHIEVEMENTS    = 'achievements'
    PAYMENTS        = 'payments'
    SETTINGS        = 'settings'


# ---------------------------------------------------------------------------
# Event Names — used by EventBus
# ---------------------------------------------------------------------------

class Events(Enum):
    """All system events published on the event bus."""

    # User lifecycle
    USER_REGISTERED             = 'user.registered'
    USER_VERIFIED               = 'user.verified'
    USER_SUSPENDED              = 'user.suspended'
    USER_REINSTATED             = 'user.reinstated'
    USER_DELETED                = 'user.deleted'
    USER_PROFILE_UPDATED        = 'user.profile_updated'
    USER_LEVEL_UP               = 'user.level_up'
    USER_RANK_CHANGED           = 'user.rank_changed'

    # Authentication
    LOGIN_SUCCESS               = 'auth.login_success'
    LOGIN_FAILED                = 'auth.login_failed'
    LOGIN_NEW_DEVICE            = 'auth.login_new_device'
    LOGOUT                      = 'auth.logout'
    PASSWORD_CHANGED            = 'auth.password_changed'
    TWO_FA_ENABLED              = 'auth.2fa_enabled'
    TWO_FA_DISABLED             = 'auth.2fa_disabled'

    # KYC
    KYC_SUBMITTED               = 'kyc.submitted'
    KYC_APPROVED                = 'kyc.approved'
    KYC_REJECTED                = 'kyc.rejected'
    KYC_RESUBMITTED             = 'kyc.resubmitted'

    # Tasks / Offers
    TASK_CREATED                = 'task.created'
    TASK_SUBMITTED              = 'task.submitted'
    TASK_APPROVED               = 'task.approved'
    TASK_REJECTED               = 'task.rejected'
    TASK_EXPIRED                = 'task.expired'
    OFFER_COMPLETED             = 'offer.completed'
    OFFER_AVAILABLE             = 'offer.available'
    SURVEY_COMPLETED            = 'survey.completed'
    SURVEY_AVAILABLE            = 'survey.available'
    AD_VIEWED                   = 'ad.viewed'
    AD_CLICKED                  = 'ad.clicked'

    # Wallet / Payments
    WALLET_CREDITED             = 'wallet.credited'
    WALLET_DEBITED              = 'wallet.debited'
    LOW_BALANCE                 = 'wallet.low_balance'
    DEPOSIT_SUCCESS             = 'payment.deposit_success'
    DEPOSIT_FAILED              = 'payment.deposit_failed'

    # Withdrawals
    WITHDRAWAL_CREATED          = 'withdrawal.created'
    WITHDRAWAL_APPROVED         = 'withdrawal.approved'
    WITHDRAWAL_REJECTED         = 'withdrawal.rejected'
    WITHDRAWAL_COMPLETED        = 'withdrawal.completed'
    WITHDRAWAL_FAILED           = 'withdrawal.failed'

    # Referrals
    REFERRAL_CREATED            = 'referral.created'
    REFERRAL_COMPLETED          = 'referral.completed'
    REFERRAL_REWARD_ISSUED      = 'referral.reward_issued'
    TEAM_BONUS_ISSUED           = 'referral.team_bonus'

    # Affiliates / CPAlead
    POSTBACK_RECEIVED           = 'affiliate.postback_received'
    POSTBACK_FAILED             = 'affiliate.postback_failed'
    CONVERSION_RECORDED         = 'affiliate.conversion_recorded'
    COMMISSION_EARNED           = 'affiliate.commission_earned'
    SUB_AFFILIATE_EARN          = 'affiliate.sub_earn'
    PUBLISHER_PAYOUT            = 'affiliate.publisher_payout'
    CAMPAIGN_LIVE               = 'affiliate.campaign_live'
    CAMPAIGN_PAUSED             = 'affiliate.campaign_paused'

    # Achievements / Gamification
    ACHIEVEMENT_UNLOCKED        = 'achievement.unlocked'
    BADGE_EARNED                = 'achievement.badge_earned'
    DAILY_REWARD_CLAIMED        = 'achievement.daily_reward'
    STREAK_UPDATED              = 'achievement.streak'
    LEADERBOARD_CHANGED         = 'achievement.leaderboard_changed'
    CHALLENGE_COMPLETED         = 'achievement.challenge_completed'
    MILESTONE_REACHED           = 'achievement.milestone'

    # Fraud / Security
    FRAUD_DETECTED              = 'fraud.detected'
    FRAUD_RESOLVED              = 'fraud.resolved'
    IP_BLOCKED                  = 'fraud.ip_blocked'
    ACCOUNT_FLAGGED             = 'fraud.account_flagged'
    CHARGEBACK_RECEIVED         = 'fraud.chargeback'

    # Notifications (internal)
    NOTIFICATION_SENT           = 'notification.sent'
    NOTIFICATION_DELIVERED      = 'notification.delivered'
    NOTIFICATION_READ           = 'notification.read'
    NOTIFICATION_CLICKED        = 'notification.clicked'
    NOTIFICATION_FAILED         = 'notification.failed'
    PUSH_TOKEN_EXPIRED          = 'notification.push_token_expired'

    # Support
    TICKET_CREATED              = 'support.ticket_created'
    TICKET_REPLIED              = 'support.ticket_replied'
    TICKET_RESOLVED             = 'support.ticket_resolved'

    # System
    SYSTEM_HEALTH_DEGRADED      = 'system.health_degraded'
    SYSTEM_HEALTH_RESTORED      = 'system.health_restored'
    MAINTENANCE_STARTED         = 'system.maintenance_started'
    MAINTENANCE_ENDED           = 'system.maintenance_ended'
    INTEGRATION_ERROR           = 'system.integration_error'
    INTEGRATION_RECOVERED       = 'system.integration_recovered'


# ---------------------------------------------------------------------------
# Webhook Event Types
# ---------------------------------------------------------------------------

class WebhookEvents(Enum):
    """Inbound webhook event types from external providers."""
    # SendGrid
    SENDGRID_DELIVERED          = 'sendgrid.delivered'
    SENDGRID_OPENED             = 'sendgrid.opened'
    SENDGRID_CLICKED            = 'sendgrid.clicked'
    SENDGRID_BOUNCED            = 'sendgrid.bounced'
    SENDGRID_SPAM               = 'sendgrid.spam_report'
    SENDGRID_UNSUBSCRIBED       = 'sendgrid.unsubscribed'

    # Twilio
    TWILIO_SMS_DELIVERED        = 'twilio.sms.delivered'
    TWILIO_SMS_FAILED           = 'twilio.sms.failed'
    TWILIO_CALL_COMPLETED       = 'twilio.call.completed'

    # Payment Gateways
    BKASH_PAYMENT_CONFIRMED     = 'bkash.payment.confirmed'
    BKASH_PAYMENT_FAILED        = 'bkash.payment.failed'
    NAGAD_PAYMENT_CONFIRMED     = 'nagad.payment.confirmed'
    ROCKET_PAYMENT_CONFIRMED    = 'rocket.payment.confirmed'
    STRIPE_PAYMENT_SUCCEEDED    = 'stripe.payment.succeeded'
    STRIPE_PAYMENT_FAILED       = 'stripe.payment.failed'

    # CPAlead / Affiliate
    CPALEAD_POSTBACK            = 'cpalead.postback'
    CPABUILD_POSTBACK           = 'cpabuild.postback'
    MAXBOUNTY_POSTBACK          = 'maxbounty.postback'
    ADMITAD_POSTBACK            = 'admitad.postback'
    CUSTOM_POSTBACK             = 'custom.postback'

    # FCM
    FCM_DELIVERY_RECEIPT        = 'fcm.delivery_receipt'


# ---------------------------------------------------------------------------
# Priority Levels
# ---------------------------------------------------------------------------

class IntegPriority:
    """Integration operation priority levels (1=lowest, 10=highest)."""
    CRITICAL   = 10
    URGENT     = 9
    HIGH       = 7
    MEDIUM     = 5
    LOW        = 3
    BACKGROUND = 1


# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------

class RetryConfig:
    """Default retry settings for integration operations."""
    MAX_RETRIES              = 3
    BASE_BACKOFF_SECONDS     = 60
    MAX_BACKOFF_SECONDS      = 3600
    BACKOFF_MULTIPLIER       = 2
    JITTER_FACTOR            = 0.1

    # Per-service max retries
    NOTIFICATION_MAX_RETRIES = 3
    WEBHOOK_MAX_RETRIES      = 5
    PAYMENT_MAX_RETRIES      = 2
    EMAIL_MAX_RETRIES        = 3
    SMS_MAX_RETRIES          = 2
    PUSH_MAX_RETRIES         = 3


# ---------------------------------------------------------------------------
# Rate Limits
# ---------------------------------------------------------------------------

class RateLimits:
    """Default rate limits per operation type."""
    # Per user / per minute
    NOTIFICATIONS_PER_MINUTE    = 5
    API_CALLS_PER_MINUTE        = 60
    WEBHOOKS_PER_MINUTE         = 200
    BULK_SEND_PER_HOUR          = 3

    # Per system / per second
    FCM_MESSAGES_PER_SECOND     = 500
    EMAIL_MESSAGES_PER_SECOND   = 100
    SMS_MESSAGES_PER_SECOND     = 50

    # Daily limits
    EMAIL_PER_DAY_PER_USER      = 5
    SMS_PER_DAY_PER_USER        = 2
    PUSH_PER_DAY_PER_USER       = 10


# ---------------------------------------------------------------------------
# Timeout Settings (seconds)
# ---------------------------------------------------------------------------

class Timeouts:
    """Service timeout values in seconds."""
    DEFAULT             = 10
    FAST                = 3
    SLOW                = 30
    DATABASE            = 5
    CACHE               = 2
    HTTP_REQUEST        = 15
    WEBHOOK_PROCESSING  = 30
    BULK_OPERATION      = 300
    REPORT_GENERATION   = 600
    HEALTH_CHECK        = 5


# ---------------------------------------------------------------------------
# Cache Keys & TTLs
# ---------------------------------------------------------------------------

class CacheKeys:
    """Redis/cache key templates."""
    USER_NOTIFICATION_COUNT  = 'notif:count:{user_id}'
    USER_FATIGUE             = 'notif:fatigue:{user_id}'
    SEGMENT_USERS            = 'segment:users:{segment_id}'
    HEALTH_STATUS            = 'health:status:{service}'
    RATE_LIMIT               = 'ratelimit:{key}:{window}'
    INTEGRATION_STATUS       = 'integ:status:{name}'
    EVENT_BUS_QUEUE          = 'eventbus:queue:{event}'
    WEBHOOK_IDEMPOTENCY      = 'webhook:idem:{key}'


class CacheTTL:
    """Cache TTL values in seconds."""
    SHORT         = 60          # 1 minute
    MEDIUM        = 300         # 5 minutes
    LONG          = 3600        # 1 hour
    DAILY         = 86400       # 24 hours
    WEEKLY        = 604800      # 7 days
    HEALTH_CHECK  = 30          # 30 seconds
    RATE_LIMIT    = 60          # 1 minute window
    SEGMENT       = 300         # 5 minutes


# ---------------------------------------------------------------------------
# HTTP Status Codes
# ---------------------------------------------------------------------------

class HTTPStatus:
    OK                  = 200
    CREATED             = 201
    ACCEPTED            = 202
    NO_CONTENT          = 204
    BAD_REQUEST         = 400
    UNAUTHORIZED        = 401
    FORBIDDEN           = 403
    NOT_FOUND           = 404
    CONFLICT            = 409
    UNPROCESSABLE       = 422
    TOO_MANY_REQUESTS   = 429
    SERVER_ERROR        = 500
    BAD_GATEWAY         = 502
    UNAVAILABLE         = 503
    GATEWAY_TIMEOUT     = 504


# ---------------------------------------------------------------------------
# Integration Names (external services)
# ---------------------------------------------------------------------------

class ExternalServices(Enum):
    """External service identifiers."""
    # Notifications
    FIREBASE_FCM     = 'firebase_fcm'
    APPLE_APNS       = 'apple_apns'
    SENDGRID         = 'sendgrid'
    TWILIO_SMS       = 'twilio_sms'
    TWILIO_WHATSAPP  = 'twilio_whatsapp'
    SHOHO_SMS        = 'shoho_sms'
    TELEGRAM_BOT     = 'telegram_bot'
    WEB_PUSH         = 'web_push'

    # Payments (Bangladesh)
    BKASH            = 'bkash'
    NAGAD            = 'nagad'
    ROCKET           = 'rocket'
    DBBL             = 'dbbl'
    DUTCH_BANGLA     = 'dutch_bangla'

    # International Payments
    STRIPE           = 'stripe'
    PAYPAL           = 'paypal'
    WISE             = 'wise'
    PAYONEER         = 'payoneer'

    # Affiliate/CPA Networks
    CPALEAD          = 'cpalead'
    CPABUILD         = 'cpabuild'
    MAXBOUNTY        = 'maxbounty'
    ADMITAD          = 'admitad'
    CLICKDEALER      = 'clickdealer'

    # Analytics
    GOOGLE_ANALYTICS = 'google_analytics'
    MIXPANEL         = 'mixpanel'
    AMPLITUDE        = 'amplitude'

    # Storage
    AWS_S3           = 'aws_s3'
    CLOUDINARY       = 'cloudinary'

    # Communication
    SLACK            = 'slack'
    DISCORD          = 'discord'

    # Auth
    GOOGLE_AUTH      = 'google_auth'
    FACEBOOK_AUTH    = 'facebook_auth'


# ---------------------------------------------------------------------------
# Data Sync Strategies
# ---------------------------------------------------------------------------

class SyncStrategy(Enum):
    """How data conflicts are resolved in sync_manager."""
    LATEST_WINS         = 'latest_wins'         # Newer timestamp always wins
    SOURCE_WINS         = 'source_wins'          # Source module always wins
    TARGET_WINS         = 'target_wins'          # Target module always wins
    MANUAL_REVIEW       = 'manual_review'        # Flag for human review
    MERGE               = 'merge'                # Merge non-conflicting fields
    REJECT              = 'reject'               # Reject conflicting update


# ---------------------------------------------------------------------------
# Health Check Status
# ---------------------------------------------------------------------------

class HealthStatus(Enum):
    HEALTHY     = 'healthy'
    DEGRADED    = 'degraded'
    UNHEALTHY   = 'unhealthy'
    UNKNOWN     = 'unknown'
    MAINTENANCE = 'maintenance'


# ---------------------------------------------------------------------------
# Audit Action Types
# ---------------------------------------------------------------------------

class AuditAction(Enum):
    CREATE          = 'create'
    READ            = 'read'
    UPDATE          = 'update'
    DELETE          = 'delete'
    SEND            = 'send'
    RECEIVE         = 'receive'
    APPROVE         = 'approve'
    REJECT          = 'reject'
    EXECUTE         = 'execute'
    ROLLBACK        = 'rollback'
    LOGIN           = 'login'
    LOGOUT          = 'logout'
    EXPORT          = 'export'
    IMPORT          = 'import'
    SYNC            = 'sync'
    WEBHOOK         = 'webhook'
    API_CALL        = 'api_call'
    PERMISSION      = 'permission_check'
    RATE_LIMITED    = 'rate_limited'
    ERROR           = 'error'


# ---------------------------------------------------------------------------
# Queue Names (Celery)
# ---------------------------------------------------------------------------

class Queues:
    """Celery queue names for all integration tasks."""
    DEFAULT             = 'default'
    HIGH_PRIORITY       = 'high_priority'
    NOTIFICATIONS       = 'notifications_high'
    PUSH                = 'notifications_push'
    EMAIL               = 'notifications_email'
    SMS                 = 'notifications_sms'
    WEBHOOKS            = 'webhooks'
    PAYMENTS            = 'payments'
    ANALYTICS           = 'analytics'
    MAINTENANCE         = 'maintenance'
    CAMPAIGNS           = 'campaigns'
    BATCH               = 'batch'
    FRAUD               = 'fraud'


# ---------------------------------------------------------------------------
# Error Codes
# ---------------------------------------------------------------------------

ERROR_CODES = {
    # General
    'E001': 'Unknown error',
    'E002': 'Service unavailable',
    'E003': 'Timeout',
    'E004': 'Rate limit exceeded',
    'E005': 'Invalid configuration',

    # Integration
    'I001': 'Integration not registered',
    'I002': 'Integration disabled',
    'I003': 'Adapter not found',
    'I004': 'Bridge connection failed',
    'I005': 'Event bus publish failed',
    'I006': 'Webhook processing failed',
    'I007': 'Data transformation failed',
    'I008': 'Sync conflict detected',

    # Auth
    'A001': 'Authentication failed',
    'A002': 'Permission denied',
    'A003': 'Token expired',
    'A004': 'Invalid API key',

    # Data
    'D001': 'Validation failed',
    'D002': 'Data type mismatch',
    'D003': 'Required field missing',
    'D004': 'Data conflict',
    'D005': 'Duplicate record',
}


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

FEATURE_FLAGS = {
    'ENABLE_EVENT_BUS':              True,
    'ENABLE_WEBHOOK_SIGNATURE':      True,
    'ENABLE_RATE_LIMITING':          True,
    'ENABLE_AUDIT_LOGS':             True,
    'ENABLE_PERFORMANCE_MONITORING': True,
    'ENABLE_HEALTH_CHECKS':          True,
    'ENABLE_SMART_RETRY':            True,
    'ENABLE_FALLBACK_LOGIC':         True,
    'ENABLE_DATA_SYNC':              True,
    'ENABLE_CROSS_MODULE_AUTH':      True,
}

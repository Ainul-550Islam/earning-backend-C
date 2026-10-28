# api/djoyalty/integration_system/integ_constants.py
"""
Integration System Constants & Enums।
All integration-related constants in one place।
"""
from enum import Enum, auto


# ─── Integration Types ────────────────────────────────────────────────────────

class IntegrationType(str, Enum):
    """All supported integration types।"""
    # Payment / Cashout
    BKASH          = 'bkash'
    NAGAD          = 'nagad'
    ROCKET         = 'rocket'
    SSLCOMMERZ     = 'sslcommerz'
    # SMS
    BULKSMSBD      = 'bulksmsbd'
    SSL_WIRELESS   = 'ssl_wireless'
    TWILIO         = 'twilio'
    # Email
    SMTP           = 'smtp'
    SENDGRID       = 'sendgrid'
    MAILGUN        = 'mailgun'
    # Push
    FIREBASE_FCM   = 'firebase_fcm'
    # OCR
    GOOGLE_VISION  = 'google_vision'
    TESSERACT      = 'tesseract'
    # CPA/Offerwall
    CPALEAD        = 'cpalead'
    TAPJOY         = 'tapjoy'
    XSOLLA         = 'xsolla'
    # Internal
    INTERNAL       = 'internal'


class IntegrationStatus(str, Enum):
    """Integration health status।"""
    HEALTHY    = 'healthy'
    DEGRADED   = 'degraded'
    UNHEALTHY  = 'unhealthy'
    UNKNOWN    = 'unknown'
    DISABLED   = 'disabled'


class EventType(str, Enum):
    """Loyalty domain events।"""
    # Points
    POINTS_EARNED           = 'points.earned'
    POINTS_REDEEMED         = 'points.redeemed'
    POINTS_EXPIRED          = 'points.expired'
    POINTS_TRANSFERRED      = 'points.transferred'
    POINTS_ADJUSTED         = 'points.adjusted'
    # Tiers
    TIER_UPGRADED           = 'tier.upgraded'
    TIER_DOWNGRADED         = 'tier.downgraded'
    TIER_EVALUATED          = 'tier.evaluated'
    # Customer
    CUSTOMER_CREATED        = 'customer.created'
    CUSTOMER_UPDATED        = 'customer.updated'
    CUSTOMER_DEACTIVATED    = 'customer.deactivated'
    # Engagement
    BADGE_UNLOCKED          = 'badge.unlocked'
    STREAK_MILESTONE        = 'streak.milestone'
    CHALLENGE_COMPLETED     = 'challenge.completed'
    MILESTONE_ACHIEVED      = 'milestone.achieved'
    # Redemption
    REDEMPTION_CREATED      = 'redemption.created'
    REDEMPTION_APPROVED     = 'redemption.approved'
    REDEMPTION_REJECTED     = 'redemption.rejected'
    VOUCHER_GENERATED       = 'voucher.generated'
    VOUCHER_USED            = 'voucher.used'
    GIFTCARD_ISSUED         = 'giftcard.issued'
    # Gamification
    SPIN_WHEEL_RESULT       = 'spin_wheel.result'
    SCRATCH_CARD_CLAIMED    = 'scratch_card.claimed'
    LOTTERY_TICKET_BOUGHT   = 'lottery.ticket_bought'
    LOTTERY_WINNER          = 'lottery.winner'
    # Offerwall
    OFFER_COMPLETED         = 'offer.completed'
    POSTBACK_RECEIVED       = 'offer.postback_received'
    # Referral
    REFERRAL_SIGNUP         = 'referral.signup'
    REFERRAL_CONVERSION     = 'referral.conversion'
    # Cashout
    CASHOUT_REQUESTED       = 'cashout.requested'
    CASHOUT_APPROVED        = 'cashout.approved'
    CASHOUT_COMPLETED       = 'cashout.completed'
    # AI
    CHURN_ALERT             = 'ai.churn_alert'
    OFFER_PERSONALIZED      = 'ai.offer_personalized'
    # Eco
    ECO_ACTION_COMPLETED    = 'eco.action_completed'
    CHARITY_DONATED         = 'charity.donated'
    # Family
    FAMILY_MEMBER_JOINED    = 'family.member_joined'
    FAMILY_POINTS_POOLED    = 'family.points_pooled'
    # System
    SYSTEM_ERROR            = 'system.error'
    FRAUD_DETECTED          = 'system.fraud_detected'
    CAMPAIGN_STARTED        = 'campaign.started'
    CAMPAIGN_ENDED          = 'campaign.ended'


class MessagePriority(int, Enum):
    """Message queue priority levels।"""
    CRITICAL = 10
    HIGH     = 7
    NORMAL   = 5
    LOW      = 3
    BULK     = 1


class CircuitBreakerState(str, Enum):
    """Circuit breaker states।"""
    CLOSED    = 'closed'    # Normal operation
    OPEN      = 'open'      # Failing -- reject calls
    HALF_OPEN = 'half_open' # Testing recovery


# ─── Constants ────────────────────────────────────────────────────────────────

# Cache keys
CACHE_KEY_INTEGRATION_STATUS = 'djoyalty:integ:status:{name}'
CACHE_KEY_CIRCUIT_BREAKER    = 'djoyalty:circuit:{name}'
CACHE_KEY_RATE_LIMIT         = 'djoyalty:ratelimit:{name}:{key}'
CACHE_KEY_HEALTH_CHECK       = 'djoyalty:health:{name}'

# Default timeouts (seconds)
DEFAULT_HTTP_TIMEOUT     = 15
DEFAULT_RETRY_DELAY      = 2       # seconds between retries
DEFAULT_MAX_RETRIES      = 3
DEFAULT_CIRCUIT_THRESHOLD = 5      # failures before opening circuit
DEFAULT_CIRCUIT_TIMEOUT  = 60      # seconds to wait before half-open

# Queue names
QUEUE_NOTIFICATIONS     = 'djoyalty_notifications'
QUEUE_WEBHOOKS          = 'djoyalty_webhooks'
QUEUE_POINTS_EVENTS     = 'djoyalty_points'
QUEUE_CASHOUT           = 'djoyalty_cashout'
QUEUE_AI_TASKS          = 'djoyalty_ai'
QUEUE_BULK              = 'djoyalty_bulk'
QUEUE_CRITICAL          = 'djoyalty_critical'

# Webhook delivery
WEBHOOK_MAX_RETRIES     = 5
WEBHOOK_RETRY_DELAYS    = [10, 30, 120, 600, 3600]  # seconds
WEBHOOK_TIMEOUT         = 10

# Performance thresholds (ms)
PERF_THRESHOLD_FAST    = 100   # < 100ms = fast
PERF_THRESHOLD_NORMAL  = 500   # < 500ms = normal
PERF_THRESHOLD_SLOW    = 2000  # < 2s = slow, > 2s = critical

# Health check intervals
HEALTH_CHECK_INTERVAL   = 60   # seconds
HEALTH_CHECK_TIMEOUT    = 5    # seconds

# Postback signature headers
POSTBACK_SIG_HEADER     = 'X-Djoyalty-Signature'
POSTBACK_TS_HEADER      = 'X-Djoyalty-Timestamp'

# Data sync
SYNC_CONFLICT_RESOLUTION = 'server_wins'  # 'server_wins' | 'client_wins' | 'manual'
SYNC_MAX_DRIFT_SECONDS   = 300            # 5 min acceptable clock drift

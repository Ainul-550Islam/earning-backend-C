# api/payment_gateways/integration_system/integ_constants.py
# All constants used across the integration system

# ── Integration event types ───────────────────────────────────────────────────
class IntegEvent:
    # Payment lifecycle
    DEPOSIT_INITIATED   = 'deposit.initiated'
    DEPOSIT_COMPLETED   = 'deposit.completed'
    DEPOSIT_FAILED      = 'deposit.failed'
    DEPOSIT_EXPIRED     = 'deposit.expired'
    DEPOSIT_REFUNDED    = 'deposit.refunded'

    WITHDRAWAL_REQUESTED  = 'withdrawal.requested'
    WITHDRAWAL_APPROVED   = 'withdrawal.approved'
    WITHDRAWAL_PROCESSED  = 'withdrawal.processed'
    WITHDRAWAL_FAILED     = 'withdrawal.failed'
    WITHDRAWAL_REJECTED   = 'withdrawal.rejected'

    # Conversion lifecycle
    CONVERSION_RECEIVED   = 'conversion.received'
    CONVERSION_APPROVED   = 'conversion.approved'
    CONVERSION_REJECTED   = 'conversion.rejected'
    CONVERSION_REVERSED   = 'conversion.reversed'

    # Gateway health
    GATEWAY_UP            = 'gateway.up'
    GATEWAY_DOWN          = 'gateway.down'
    GATEWAY_DEGRADED      = 'gateway.degraded'

    # Fraud
    FRAUD_DETECTED        = 'fraud.detected'
    FRAUD_BLOCKED         = 'fraud.blocked'

    # Publisher
    PUBLISHER_APPROVED    = 'publisher.approved'
    PUBLISHER_SUSPENDED   = 'publisher.suspended'
    REFERRAL_CREDITED     = 'referral.credited'

    # SmartLink
    SMARTLINK_CLICKED     = 'smartlink.clicked'
    SMARTLINK_CONVERTED   = 'smartlink.converted'

    # System
    WEBHOOK_RECEIVED      = 'webhook.received'
    WEBHOOK_FAILED        = 'webhook.failed'
    RECONCILIATION_DONE   = 'reconciliation.done'
    RATE_UPDATED          = 'rate.updated'


# ── Integration module names ───────────────────────────────────────────────────
class IntegModule:
    WALLET           = 'api.wallet'
    FRAUD_DETECTION  = 'api.fraud_detection'
    NOTIFICATIONS    = 'api.notifications'
    POSTBACK_ENGINE  = 'api.postback_engine'
    SMARTLINK        = 'api.smartlink'
    OFFERWALL        = 'api.offerwall'
    ANALYTICS        = 'api.analytics'
    REFERRAL         = 'api.referral'
    SUPPORT          = 'api.support'
    USERS            = 'api.users'
    KYC              = 'api.kyc'
    GAMIFICATION     = 'api.gamification'
    AI_ENGINE        = 'api.ai_engine'
    BEHAVIOR_ANALYTICS = 'api.behavior_analytics'
    PAYOUT_QUEUE     = 'api.payout_queue'

    # Our own sub-modules
    PG_TRACKING      = 'api.payment_gateways.tracking'
    PG_OFFERS        = 'api.payment_gateways.offers'
    PG_FRAUD         = 'api.payment_gateways.fraud'


# ── Priority levels ────────────────────────────────────────────────────────────
class Priority:
    CRITICAL  = 0   # Process immediately, block on failure
    HIGH      = 1   # Process within 5 seconds
    NORMAL    = 2   # Process within 30 seconds
    LOW       = 3   # Process within 5 minutes
    ASYNC     = 4   # Fire-and-forget, background


# ── Status codes ───────────────────────────────────────────────────────────────
class IntegStatus:
    PENDING    = 'pending'
    PROCESSING = 'processing'
    SUCCESS    = 'success'
    FAILED     = 'failed'
    RETRYING   = 'retrying'
    SKIPPED    = 'skipped'
    TIMEOUT    = 'timeout'


# ── Retry config ───────────────────────────────────────────────────────────────
RETRY_CONFIG = {
    Priority.CRITICAL: {'max_retries': 5,  'delay_seconds': 1},
    Priority.HIGH:     {'max_retries': 3,  'delay_seconds': 5},
    Priority.NORMAL:   {'max_retries': 3,  'delay_seconds': 30},
    Priority.LOW:      {'max_retries': 2,  'delay_seconds': 300},
    Priority.ASYNC:    {'max_retries': 1,  'delay_seconds': 60},
}

# ── Message queue settings ─────────────────────────────────────────────────────
QUEUE_NAMES = {
    'deposits':     'pg_deposits',
    'withdrawals':  'pg_withdrawals',
    'conversions':  'pg_conversions',
    'webhooks':     'pg_webhooks',
    'notifications':'pg_notifications',
    'fraud':        'pg_fraud',
    'default':      'pg_default',
}

MAX_QUEUE_SIZE = 10_000     # Per queue
BATCH_SIZE     = 100        # Events per batch processing
CACHE_TTL      = 300        # 5 minutes default cache

# ── Data bridge field mappings ─────────────────────────────────────────────────
WALLET_FIELD_MAP = {
    'deposit':    'credit',
    'withdrawal': 'debit',
    'earning':    'credit',
    'refund':     'credit',
    'fee':        'debit',
}

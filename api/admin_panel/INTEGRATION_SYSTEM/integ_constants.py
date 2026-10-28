# api/admin_panel/INTEGRATION_SYSTEM/integ_constants.py
"""
Integration System Constants.
All 50 app names, event types, bridge types, queue names, timeouts.
"""

# ==================== ALL 50 INTEGRATED APPS ====================
INTEGRATION_APPS = [
    'ad_networks',
    'admin_panel',
    'advertiser_portal',
    'ai_engine',
    'alerts',
    'analytics',
    'audit_logs',
    'auto_mod',
    'behavior_analytics',
    'cache',
    'cms',
    'dashboard_assets',
    'disaster_recovery',
    'djoyalty',
    'dr_integration',
    'engagement',
    'fraud_detection',
    'gamification',
    'inventory',
    'kyc',
    'localization',
    'marketplace',
    'messaging',
    'monetization_tools',
    'notifications',
    'offer_inventory',
    'offer_routing',
    'offerwall',
    'gateways',
    'payout_queue',
    'postback',
    'postback_engine',
    'promotions',
    'proxy_intelligence',
    'publisher_tools',
    'rate_limit',
    'referral',
    'security',
    'smartlink',
    'subscription',
    'support',
    'tasks',
    'tenants',
    'users',
    'version_control',
    'wallet',
    'webhooks',
]

# ==================== EVENT TYPES ====================
INTEGRATION_EVENTS = {
    # User lifecycle
    'USER_REGISTERED':          'user.registered',
    'USER_BANNED':              'user.banned',
    'USER_UNBANNED':            'user.unbanned',
    'USER_VERIFIED':            'user.verified',
    'USER_PROFILE_UPDATED':     'user.profile_updated',
    'USER_LOGIN':               'user.login',
    'USER_LOGOUT':              'user.logout',
    'USER_DELETED':             'user.deleted',

    # Wallet & Payments
    'WALLET_CREDITED':          'wallet.credited',
    'WALLET_DEBITED':           'wallet.debited',
    'WALLET_FROZEN':            'wallet.frozen',
    'WITHDRAWAL_REQUESTED':     'wallet.withdrawal_requested',
    'WITHDRAWAL_APPROVED':      'wallet.withdrawal_approved',
    'WITHDRAWAL_REJECTED':      'wallet.withdrawal_rejected',
    'WITHDRAWAL_PAID':          'wallet.withdrawal_paid',

    # Offers & Conversions
    'OFFER_CREATED':            'offer.created',
    'OFFER_APPROVED':           'offer.approved',
    'OFFER_PAUSED':             'offer.paused',
    'OFFER_COMPLETED':          'offer.completed',
    'CONVERSION_RECEIVED':      'conversion.received',
    'CONVERSION_APPROVED':      'conversion.approved',
    'CONVERSION_REJECTED':      'conversion.rejected',
    'POSTBACK_FIRED':           'postback.fired',
    'POSTBACK_FAILED':          'postback.failed',

    # Fraud & Security
    'FRAUD_DETECTED':           'fraud.detected',
    'IP_BLOCKED':               'fraud.ip_blocked',
    'VPN_DETECTED':             'fraud.vpn_detected',
    'MULTI_ACCOUNT_DETECTED':   'fraud.multi_account',
    'FRAUD_RULE_TRIGGERED':     'fraud.rule_triggered',

    # KYC
    'KYC_SUBMITTED':            'kyc.submitted',
    'KYC_APPROVED':             'kyc.approved',
    'KYC_REJECTED':             'kyc.rejected',

    # Gamification & Loyalty
    'POINTS_EARNED':            'loyalty.points_earned',
    'POINTS_REDEEMED':          'loyalty.points_redeemed',
    'BADGE_AWARDED':            'loyalty.badge_awarded',
    'TIER_UPGRADED':            'loyalty.tier_upgraded',
    'ACHIEVEMENT_UNLOCKED':     'loyalty.achievement_unlocked',

    # Advertiser & Publisher
    'ADVERTISER_REGISTERED':    'advertiser.registered',
    'ADVERTISER_APPROVED':      'advertiser.approved',
    'PUBLISHER_REGISTERED':     'publisher.registered',
    'PUBLISHER_APPROVED':       'publisher.approved',
    'CAMPAIGN_STARTED':         'campaign.started',
    'CAMPAIGN_PAUSED':          'campaign.paused',
    'CAMPAIGN_BUDGET_LOW':      'campaign.budget_low',

    # System
    'SYSTEM_HEALTH_CHANGED':    'system.health_changed',
    'MAINTENANCE_STARTED':      'system.maintenance_started',
    'MAINTENANCE_ENDED':        'system.maintenance_ended',
    'CONFIG_UPDATED':           'system.config_updated',
    'FEATURE_FLAG_CHANGED':     'system.feature_flag_changed',
    'RATE_LIMIT_EXCEEDED':      'system.rate_limit_exceeded',

    # AI & ML
    'MODEL_RETRAINED':          'ai.model_retrained',
    'ANOMALY_DETECTED':         'ai.anomaly_detected',
    'CHURN_RISK_HIGH':          'ai.churn_risk_high',

    # Notifications
    'NOTIFICATION_SENT':        'notification.sent',
    'BROADCAST_SENT':           'notification.broadcast_sent',
    'ALERT_TRIGGERED':          'alert.triggered',
    'ALERT_RESOLVED':           'alert.resolved',
}

# ==================== BRIDGE TYPES ====================
SUPPORTED_BRIDGES = [
    'wallet_bridge',
    'user_bridge',
    'fraud_bridge',
    'offer_bridge',
    'notification_bridge',
    'audit_bridge',
    'kyc_bridge',
    'loyalty_bridge',
    'smartlink_bridge',
    'postback_bridge',
    'analytics_bridge',
    'ai_bridge',
]

# ==================== QUEUE NAMES ====================
QUEUE_NAMES = {
    'HIGH_PRIORITY':    'admin_panel.high_priority',
    'STANDARD':         'admin_panel.standard',
    'BULK':             'admin_panel.bulk',
    'ASYNC':            'admin_panel.async',
    'DEAD_LETTER':      'admin_panel.dead_letter',
    'RETRY':            'admin_panel.retry',
}

# ==================== TIMEOUTS (seconds) ====================
TIMEOUTS = {
    'INTEGRATION_CALL':     5,
    'EVENT_PUBLISH':        2,
    'HEALTH_CHECK':         10,
    'SYNC_OPERATION':       30,
    'BULK_OPERATION':       120,
    'WEBHOOK_DELIVERY':     10,
    'CACHE_TTL_SHORT':      60,
    'CACHE_TTL_MEDIUM':     300,
    'CACHE_TTL_LONG':       3600,
    'CACHE_TTL_DAY':        86400,
}

# ==================== RETRY CONFIG ====================
RETRY_CONFIG = {
    'MAX_RETRIES':          5,
    'INITIAL_DELAY':        1,       # seconds
    'BACKOFF_FACTOR':       2,       # exponential backoff
    'MAX_DELAY':            60,      # max seconds between retries
    'JITTER':               True,    # add random jitter
}

# ==================== HEALTH STATUS ====================
HEALTH_STATUSES = {
    'HEALTHY':      'healthy',
    'DEGRADED':     'degraded',
    'DOWN':         'down',
    'UNKNOWN':      'unknown',
    'RECOVERING':   'recovering',
}

# ==================== DATA BRIDGE MODES ====================
DATA_BRIDGE_MODES = {
    'SYNC':         'sync',        # Immediate sync
    'ASYNC':        'async',       # Background sync
    'BATCH':        'batch',       # Bulk batch sync
    'STREAM':       'stream',      # Real-time stream
    'LAZY':         'lazy',        # On-demand sync
}

# ==================== CONFLICT RESOLUTION STRATEGIES ====================
CONFLICT_STRATEGIES = {
    'LAST_WRITE_WINS':      'last_write_wins',
    'FIRST_WRITE_WINS':     'first_write_wins',
    'MERGE':                'merge',
    'ADMIN_DECIDES':        'admin_decides',
    'SOURCE_WINS':          'source_wins',
    'TARGET_WINS':          'target_wins',
}

# ==================== INTEGRATION VERSION ====================
INTEGRATION_VERSION = '1.0.0'
MIN_COMPATIBLE_VERSION = '0.9.0'
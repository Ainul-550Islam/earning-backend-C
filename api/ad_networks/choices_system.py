# api/ad_networks/choices.py
# System-Level Choice Definitions Only

from django.utils.translation import gettext_lazy as _

# ============================================================================
# NETWORK SYSTEM CHOICES
# ============================================================================

NETWORK_TYPES = (
    ('offerwall', _('Offerwall')),
    ('survey', _('Survey')),
    ('video', _('Video/Ads')),
    ('gaming', _('Gaming')),
    ('app_install', _('App Install')),
    ('cashback', _('Cashback')),
    ('cpi_cpa', _('CPI/CPA')),
    ('cpe', _('CPE')),
    ('other', _('Other')),
)

# ============================================================================
# OFFER SYSTEM CHOICES
# ============================================================================

OFFER_STATUS = (
    ('active', _('Active')),
    ('paused', _('Paused')),
    ('expired', _('Expired')),
    ('draft', _('Draft')),
)

OFFER_TYPES = (
    ('cpi', _('CPI - Cost Per Install')),
    ('cpa', _('CPA - Cost Per Action')),
    ('cps', _('CPS - Cost Per Sale')),
    ('cpl', _('CPL - Cost Per Lead')),
    ('cpm', _('CPM - Cost Per Mille')),
    ('cpc', _('CPC - Cost Per Click')),
    ('cpv', _('CPV - Cost Per View')),
    ('fixed', _('Fixed Reward')),
)

OFFER_DIFFICULTY = (
    ('easy', _('Easy')),
    ('medium', _('Medium')),
    ('hard', _('Hard')),
)

DEVICE_TYPES = (
    ('android', _('Android')),
    ('ios', _('iOS')),
    ('web', _('Web')),
    ('desktop', _('Desktop')),
)

PLATFORMS = (
    ('android', _('Android')),
    ('ios', _('iOS')),
    ('windows', _('Windows')),
    ('macos', _('macOS')),
    ('linux', _('Linux')),
    ('web', _('Web')),
)

# ============================================================================
# ENGAGEMENT SYSTEM CHOICES
# ============================================================================

ENGAGEMENT_STATUS = (
    ('clicked', _('Clicked')),
    ('started', _('Started')),
    ('in_progress', _('In Progress')),
    ('completed', _('Completed')),
    ('approved', _('Approved')),
    ('rejected', _('Rejected')),
    ('expired', _('Expired')),
    ('rewarded', _('Rewarded')),
)

# ============================================================================
# CONVERSION SYSTEM CHOICES
# ============================================================================

CONVERSION_STATUS = (
    ('pending', _('Pending')),
    ('confirmed', _('Confirmed')),
    ('rejected', _('Rejected')),
    ('chargeback', _('Chargeback')),
)

RISK_LEVELS = (
    ('low', _('Low')),
    ('medium', _('Medium')),
    ('high', _('High')),
    ('critical', _('Critical')),
)

# ============================================================================
# FRAUD DETECTION SYSTEM CHOICES
# ============================================================================

FRAUD_RULE_TYPES = (
    ('ip_based', _('IP Based')),
    ('device_based', _('Device Based')),
    ('behavior_based', _('Behavior Based')),
    ('time_based', _('Time Based')),
    ('volume_based', _('Volume Based')),
)

FRAUD_RULE_ACTIONS = (
    ('block', _('Block')),
    ('flag', _('Flag')),
    ('limit', _('Limit')),
    ('monitor', _('Monitor')),
    ('alert', _('Alert')),
)

FRAUD_SEVERITY = (
    ('low', _('Low')),
    ('medium', _('Medium')),
    ('high', _('High')),
    ('critical', _('Critical')),
)

# ============================================================================
# PAYMENT SYSTEM CHOICES
# ============================================================================

CURRENCIES = (
    ('USD', _('US Dollar')),
    ('EUR', _('Euro')),
    ('GBP', _('British Pound')),
    ('BDT', _('Bangladeshi Taka')),
    ('INR', _('Indian Rupee')),
    ('PKR', _('Pakistani Rupee')),
    ('JPY', _('Japanese Yen')),
    ('CNY', _('Chinese Yuan')),
    ('CAD', _('Canadian Dollar')),
    ('AUD', _('Australian Dollar')),
)

PAYMENT_STATUS = (
    ('pending', _('Pending')),
    ('processing', _('Processing')),
    ('completed', _('Completed')),
    ('failed', _('Failed')),
    ('cancelled', _('Cancelled')),
)

PAYMENT_METHODS = (
    ('bank_transfer', _('Bank Transfer')),
    ('paypal', _('PayPal')),
    ('stripe', _('Stripe')),
    ('crypto', _('Cryptocurrency')),
    ('mobile_money', _('Mobile Money')),
    ('gift_card', _('Gift Card')),
)

# ============================================================================
# WEBHOOK SYSTEM CHOICES
# ============================================================================

WEBHOOK_EVENT_TYPES = (
    ('offer_created', _('Offer Created')),
    ('offer_updated', _('Offer Updated')),
    ('engagement_created', _('Engagement Created')),
    ('engagement_completed', _('Engagement Completed')),
    ('conversion_confirmed', _('Conversion Confirmed')),
    ('payment_processed', _('Payment Processed')),
    ('fraud_detected', _('Fraud Detected')),
)

WEBHOOK_STATUS = (
    ('pending', _('Pending')),
    ('processed', _('Processed')),
    ('failed', _('Failed')),
    ('retrying', _('Retrying')),
)

# ============================================================================
# HEALTH CHECK SYSTEM CHOICES
# ============================================================================

HEALTH_CHECK_TYPES = (
    ('api_connectivity', _('API Connectivity')),
    ('response_time', _('Response Time')),
    ('data_integrity', _('Data Integrity')),
    ('auth_validation', _('Auth Validation')),
    ('rate_limiting', _('Rate Limiting')),
)

HEALTH_STATUS = (
    ('healthy', _('Healthy')),
    ('degraded', _('Degraded')),
    ('unhealthy', _('Unhealthy')),
    ('unknown', _('Unknown')),
)

# ============================================================================
# LOG LEVEL SYSTEM CHOICES
# ============================================================================

LOG_LEVELS = (
    ('debug', _('Debug')),
    ('info', _('Info')),
    ('warning', _('Warning')),
    ('error', _('Error')),
    ('critical', _('Critical')),
)

LOG_CATEGORIES = (
    ('api', _('API')),
    ('sync', _('Synchronization')),
    ('fraud', _('Fraud Detection')),
    ('payment', _('Payment')),
    ('system', _('System')),
    ('security', _('Security')),
)

# ============================================================================
# NOTIFICATION SYSTEM CHOICES
# ============================================================================

NOTIFICATION_TYPES = (
    ('email', _('Email')),
    ('sms', _('SMS')),
    ('push', _('Push Notification')),
    ('in_app', _('In-App')),
    ('webhook', _('Webhook')),
)

NOTIFICATION_PRIORITIES = (
    ('low', _('Low')),
    ('normal', _('Normal')),
    ('high', _('High')),
    ('urgent', _('Urgent')),
)

# ============================================================================
# REPORT SYSTEM CHOICES
# ============================================================================

REPORT_TYPES = (
    ('daily', _('Daily')),
    ('weekly', _('Weekly')),
    ('monthly', _('Monthly')),
    ('quarterly', _('Quarterly')),
    ('yearly', _('Yearly')),
    ('custom', _('Custom')),
)

REPORT_FORMATS = (
    ('json', _('JSON')),
    ('csv', _('CSV')),
    ('xlsx', _('Excel')),
    ('pdf', _('PDF')),
    ('html', _('HTML')),
)

# ============================================================================
# CACHE SYSTEM CHOICES
# ============================================================================

CACHE_KEYS = (
    ('offer_list', _('Offer List')),
    ('user_stats', _('User Statistics')),
    ('network_health', _('Network Health')),
    ('fraud_rules', _('Fraud Rules')),
    ('analytics_data', _('Analytics Data')),
)

CACHE_STRATEGIES = (
    ('write_through', _('Write Through')),
    ('write_behind', _('Write Behind')),
    ('cache_aside', _('Cache Aside')),
    ('read_through', _('Read Through')),
)

# ============================================================================
# TENANT SYSTEM CHOICES
# ============================================================================

TENANT_STATUSES = (
    ('active', _('Active')),
    ('suspended', _('Suspended')),
    ('trial', _('Trial')),
    ('expired', _('Expired')),
)

TENANT_PLANS = (
    ('basic', _('Basic')),
    ('professional', _('Professional')),
    ('enterprise', _('Enterprise')),
    ('custom', _('Custom')),
)

# ============================================================================
# API SYSTEM CHOICES
# ============================================================================

API_VERSIONS = (
    ('v1', _('Version 1')),
    ('v2', _('Version 2')),
    ('v3', _('Version 3')),
)

API_STATUS_CODES = (
    ('success', _('Success')),
    ('client_error', _('Client Error')),
    ('server_error', _('Server Error')),
    ('rate_limited', _('Rate Limited')),
)

# ============================================================================
# EXPORT CHOICES
# ============================================================================

__all__ = [
    # Network choices
    'NETWORK_TYPES',
    
    # Offer choices
    'OFFER_STATUS',
    'OFFER_TYPES',
    'OFFER_DIFFICULTY',
    'DEVICE_TYPES',
    'PLATFORMS',
    
    # Engagement choices
    'ENGAGEMENT_STATUS',
    
    # Conversion choices
    'CONVERSION_STATUS',
    'RISK_LEVELS',
    
    # Fraud detection choices
    'FRAUD_RULE_TYPES',
    'FRAUD_RULE_ACTIONS',
    'FRAUD_SEVERITY',
    
    # Payment choices
    'CURRENCIES',
    'PAYMENT_STATUS',
    'PAYMENT_METHODS',
    
    # Webhook choices
    'WEBHOOK_EVENT_TYPES',
    'WEBHOOK_STATUS',
    
    # Health check choices
    'HEALTH_CHECK_TYPES',
    'HEALTH_STATUS',
    
    # Log choices
    'LOG_LEVELS',
    'LOG_CATEGORIES',
    
    # Notification choices
    'NOTIFICATION_TYPES',
    'NOTIFICATION_PRIORITIES',
    
    # Report choices
    'REPORT_TYPES',
    'REPORT_FORMATS',
    
    # Cache choices
    'CACHE_KEYS',
    'CACHE_STRATEGIES',
    
    # Tenant choices
    'TENANT_STATUSES',
    'TENANT_PLANS',
    
    # API choices
    'API_VERSIONS',
    'API_STATUS_CODES',
]

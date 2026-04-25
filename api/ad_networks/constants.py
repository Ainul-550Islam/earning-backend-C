"""
api/ad_networks/constants.py
Centralized constants for Ad Networks module
SaaS-ready with tenant support and fraud prevention
"""

from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _


# ==================== OFFER CONSTANTS ====================

# Offer limits and validation
MAX_OFFER_TITLE_LENGTH = 255
MAX_OFFER_DESCRIPTION_LENGTH = 2000
MAX_OFFER_INSTRUCTIONS_LENGTH = 1000
MAX_OFFER_URL_LENGTH = 500
MAX_EXTERNAL_ID_LENGTH = 255

# Default values
DEFAULT_CONVERSION_RATE = Decimal('0.05')
DEFAULT_MIN_PAYOUT = Decimal('1.00')
DEFAULT_MAX_PAYOUT = Decimal('1000.00')
DEFAULT_REWARD_AMOUNT = Decimal('0.50')
DEFAULT_COMMISSION_RATE = Decimal('0.00')
DEFAULT_RATING = 0.0
DEFAULT_TRUST_SCORE = 50
DEFAULT_PRIORITY = 0

# Offer limits
MAX_DAILY_OFFER_LIMIT = 50
MAX_USER_DAILY_LIMIT = 10
MAX_USER_LIFETIME_LIMIT = 1
MAX_CONVERSIONS_PER_OFFER = 10000
MAX_CLICK_COUNT_PER_OFFER = 100000

# Time settings (in seconds)
OFFER_CACHE_TTL = 3600  # 1 hour
OFFER_REFRESH_INTERVAL = 3600  # 1 hour
DEFAULT_ESTIMATED_TIME = 5  # minutes
MAX_ESTIMATED_TIME = 1440  # 24 hours
MIN_ESTIMATED_TIME = 1  # minute

# Offer expiration
DEFAULT_EXPIRY_DAYS = 30
MAX_EXPIRY_DAYS = 365
MIN_EXPIRY_DAYS = 1


# ==================== FRAUD DETECTION CONSTANTS ====================

# Fraud detection thresholds
FRAUD_SCORE_THRESHOLD = 70  # Critical threshold for blocking
HIGH_RISK_THRESHOLD = 80
MEDIUM_RISK_THRESHOLD = 50
LOW_RISK_THRESHOLD = 30

# Conversion limits
MAX_CONVERSIONS_PER_USER_PER_HOUR = 10
MAX_CONVERSIONS_PER_USER_PER_DAY = 50
MAX_CONVERSIONS_PER_IP_PER_HOUR = 20
MAX_CONVERSIONS_PER_IP_PER_DAY = 100

# Click tracking limits
MAX_CLICKS_PER_USER_PER_HOUR = 100
MAX_CLICKS_PER_USER_PER_DAY = 500
MAX_CLICKS_PER_IP_PER_HOUR = 200
MAX_CLICKS_PER_IP_PER_DAY = 1000

# Device and browser limits
MAX_CONVERSIONS_PER_DEVICE_PER_DAY = 25
MAX_CONVERSIONS_PER_USER_AGENT_PER_DAY = 30

# Time-based fraud detection
MIN_COMPLETION_TIME_SECONDS = 30
MAX_COMPLETION_TIME_SECONDS = 86400  # 24 hours
SUSPICIOUS_COMPLETION_TIME_SECONDS = 10  # Too fast to be real

# Geographic fraud detection
MAX_CONVERSIONS_PER_COUNTRY_PER_HOUR = 1000
MAX_CONVERSIONS_PER_COUNTRY_PER_DAY = 10000

# IP blacklist settings
IP_BLACKLIST_TTL = 86400  # 24 hours
AUTO_BLACKLIST_THRESHOLD = 5  # Auto-blacklist after 5 fraud attempts


# ==================== NETWORK API CONSTANTS ====================

# API timeout settings
API_TIMEOUT_SECONDS = 30
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY_SECONDS = 1

# Rate limiting
API_RATE_LIMIT_PER_MINUTE = 60
API_RATE_LIMIT_PER_HOUR = 1000
API_RATE_LIMIT_PER_DAY = 10000

# Webhook settings
WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_RETRY_ATTEMPTS = 3
WEBHOOK_RETRY_DELAY_SECONDS = 5

# Postback settings
POSTBACK_TIMEOUT_SECONDS = 15
POSTBACK_RETRY_ATTEMPTS = 5
POSTBACK_RETRY_DELAY_SECONDS = 2
POSTBACK_SUCCESS_TTL = 300  # 5 minutes cache

# API response cache
API_RESPONSE_CACHE_TTL = 300  # 5 minutes
NETWORK_STATUS_CACHE_TTL = 600  # 10 minutes
OFFER_LIST_CACHE_TTL = 1800  # 30 minutes


# ==================== PAYMENT CONSTANTS ====================

# Payment processing
DEFAULT_PAYMENT_DURATION = 30  # days
MIN_PAYMENT_DURATION = 7
MAX_PAYMENT_DURATION = 90

# Payout limits
MIN_PAYOUT_AMOUNT = Decimal('1.00')
MAX_PAYOUT_AMOUNT = Decimal('10000.00')
DEFAULT_COMMISSION_PERCENTAGE = Decimal('10.00')
MAX_COMMISSION_PERCENTAGE = Decimal('50.00')

# Currency settings
DEFAULT_CURRENCY = 'USD'
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'BDT', 'INR', 'CAD', 'AUD']
CURRENCY_PRECISION = {
    'USD': 2,
    'EUR': 2,
    'GBP': 2,
    'BDT': 2,
    'INR': 2,
    'CAD': 2,
    'AUD': 2,
}

# Payment method limits
PAYPAL_MAX_AMOUNT = Decimal('10000.00')
BANK_TRANSFER_MIN_AMOUNT = Decimal('100.00')
CRYPTO_MAX_AMOUNT = Decimal('50000.00')


# ==================== CACHING CONSTANTS ====================

# Cache keys patterns
CACHE_KEY_PATTERNS = {
    'offer_detail': 'offer_{offer_id}_detail',
    'offer_list': 'offer_list_{hash}_{user_id}',
    'user_offers': 'user_{user_id}_offers',
    'user_stats': 'user_{user_id}_stats',
    'network_offers': 'network_{network_id}_offers',
    'category_offers': 'category_{category_id}_offers',
    'trending_offers': 'trending_offers',
    'featured_offers': 'featured_offers',
    'conversion_stats': 'offer_{offer_id}_conversion_stats',
    'engagement_stats': 'user_{user_id}_engagement_stats',
    'fraud_score': 'fraud_score_{ip}_{user_id}',
    'rate_limit': 'rate_limit_{key}',
    'api_response': 'api_response_{endpoint}_{params_hash}',
}

# Cache TTL settings
CACHE_TTL = {
    'offer_detail': 300,  # 5 minutes
    'offer_list': 120,  # 2 minutes
    'user_offers': 180,  # 3 minutes
    'user_stats': 300,  # 5 minutes
    'network_offers': 600,  # 10 minutes
    'category_offers': 900,  # 15 minutes
    'trending_offers': 600,  # 10 minutes
    'featured_offers': 1800,  # 30 minutes
    'conversion_stats': 300,  # 5 minutes
    'engagement_stats': 300,  # 5 minutes
    'fraud_score': 60,  # 1 minute
    'rate_limit': 60,  # 1 minute
    'api_response': 300,  # 5 minutes
}


# ==================== SUPPORTED NETWORKS ====================

# List of 80+ supported network slugs
SUPPORTED_NETWORKS = [
    # Basic Networks (1-6)
    'admob', 'unity', 'ironsource', 'applovin', 'tapjoy', 'vungle',
    
    # Top Offerwalls (7-26)
    'adscend', 'offertoro', 'adgem', 'ayetstudios', 'lootably', 'revenueuniverse',
    'adgate', 'cpalead', 'adworkmedia', 'wannads', 'personaly', 'kiwiwall',
    'monlix', 'notik', 'offerdaddy', 'offertown', 'adlockmedia', 'offerwallpro',
    'wallads', 'wallport', 'walltoro',
    
    # Survey Specialists (27-41)
    'pollfish', 'cpxresearch', 'bitlabs', 'inbrain', 'theoremreach', 'yoursurveys',
    'surveysavvy', 'opinionworld', 'toluna', 'surveymonkey', 'swagbucks',
    'prizerebel', 'grabpoints', 'instagc', 'points2shop',
    
    # Video & Easy Tasks (42-56)
    'loottv', 'hideouttv', 'rewardrack', 'earnhoney', 'rewardxp', 'idleempire',
    'gain', 'grindabuck', 'timebucks', 'clixsense', 'neobux', 'probux',
    'clixwall', 'fyber', 'offerstation',
    
    # Gaming & App Install (57-70)
    'chartboost', 'supersonic', 'appnext', 'digitalturbine', 'glispa', 'adcolony',
    'inmobi', 'mopub', 'pangle', 'mintegral', 'ogury', 'verizonmedia',
    'smaato', 'mobilefuse',
    
    # More Networks (71-80)
    'leadbolt', 'startapp', 'mediabrix', 'nativex', 'heyzap', 'kidoz',
    'pokkt', 'youappi', 'ampiri', 'adincube',
    
    # Future Expansion (81-90)
    'custom1', 'custom2', 'custom3', 'custom4', 'custom5',
    'custom6', 'custom7', 'custom8', 'custom9', 'custom10',
]

# Network configuration templates
NETWORK_CONFIG_TEMPLATES = {
    'adscend': {
        'api_base_url': 'https://api.adscendmedia.com/v1',
        'supports_postback': True,
        'supports_webhook': True,
        'default_payout_range': (Decimal('0.50'), Decimal('5.00')),
        'supported_countries': ['US', 'CA', 'UK', 'AU'],
    },
    'offertoro': {
        'api_base_url': 'https://api.offertoro.com/v1',
        'supports_postback': True,
        'supports_webhook': True,
        'default_payout_range': (Decimal('0.25'), Decimal('3.00')),
        'supported_countries': ['US', 'CA', 'UK', 'AU', 'DE'],
    },
    'adgem': {
        'api_base_url': 'https://api.adgem.com/v1',
        'supports_postback': True,
        'supports_webhook': True,
        'default_payout_range': (Decimal('0.30'), Decimal('4.00')),
        'supported_countries': ['US', 'CA', 'UK', 'AU', 'FR', 'DE'],
    },
    'pollfish': {
        'api_base_url': 'https://api.pollfish.com/v1',
        'supports_postback': True,
        'supports_webhook': True,
        'default_payout_range': (Decimal('0.50'), Decimal('10.00')),
        'supported_countries': ['US', 'CA', 'UK', 'AU', 'DE', 'FR', 'IN'],
    },
    'cpxresearch': {
        'api_base_url': 'https://api.cpx-research.com/v1',
        'supports_postback': True,
        'supports_webhook': True,
        'default_payout_range': (Decimal('0.40'), Decimal('8.00')),
        'supported_countries': ['US', 'CA', 'UK', 'AU', 'DE', 'FR', 'ES', 'IT'],
    },
}


# ==================== POSTBACK URL CONSTANTS ====================

# Postback URL templates
POSTBACK_URL_TEMPLATES = {
    'default': '{base_url}/api/ad_networks/postback/{network_type}/',
    'secure': '{base_url}/api/ad_networks/postback/{network_type}/?key={postback_key}',
    'enhanced': '{base_url}/api/ad_networks/postback/{network_type}/{tenant_id}/?key={postback_key}&user={user_id}',
}

# Postback security settings
POSTBACK_SECURITY_ENABLED = True
POSTBACK_IP_WHITELIST_ENABLED = True
POSTBACK_SIGNATURE_VALIDATION = True
POSTBACK_RATE_LIMIT_PER_IP = 100  # per hour

# Postback retry settings
POSTBACK_RETRY_ENABLED = True
POSTBACK_MAX_RETRIES = 5
POSTBACK_RETRY_DELAY_SECONDS = 2
POSTBACK_RETRY_BACKOFF_MULTIPLIER = 2


# ==================== LOGGING CONSTANTS ====================

# Log levels
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
}

# Log categories
LOG_CATEGORIES = {
    'API_CALL': 'api_call',
    'POSTBACK': 'postback',
    'FRAUD_DETECTION': 'fraud_detection',
    'CONVERSION': 'conversion',
    'OFFER_SYNC': 'offer_sync',
    'USER_ENGAGEMENT': 'user_engagement',
    'PAYMENT': 'payment',
    'ERROR': 'error',
}

# Log retention settings
LOG_RETENTION_DAYS = 90
LOG_ARCHIVE_DAYS = 30
LOG_CLEANUP_BATCH_SIZE = 1000

# Network API logging
NETWORK_API_LOG_ENABLED = True
NETWORK_API_LOG_LEVEL = 'INFO'
NETWORK_API_LOG_INCLUDE_REQUEST_BODY = True
NETWORK_API_LOG_INCLUDE_RESPONSE_BODY = True
NETWORK_API_LOG_MAX_BODY_SIZE = 10000  # bytes


# ==================== TENANT CONSTANTS ====================

# Tenant isolation settings
TENANT_ISOLATION_ENABLED = True
TENANT_DATA_ISOLATION_STRICT = True
TENANT_CACHE_ISOLATION = True

# Tenant limits
MAX_OFFERS_PER_TENANT = 10000
MAX_NETWORKS_PER_TENANT = 100
MAX_CONVERSIONS_PER_TENANT_PER_DAY = 50000
MAX_USERS_PER_TENANT = 10000

# Tenant pricing tiers
TENANT_PRICING_TIERS = {
    'starter': {
        'max_offers': 100,
        'max_networks': 5,
        'max_users': 100,
        'commission_rate': Decimal('15.00'),
    },
    'professional': {
        'max_offers': 1000,
        'max_networks': 20,
        'max_users': 1000,
        'commission_rate': Decimal('10.00'),
    },
    'enterprise': {
        'max_offers': 10000,
        'max_networks': 100,
        'max_users': 10000,
        'commission_rate': Decimal('5.00'),
    },
}


# ==================== VALIDATION CONSTANTS ====================

# URL validation
ALLOWED_URL_SCHEMES = ['http', 'https']
ALLOWED_DOMAINS = []  # Empty means all domains allowed
BLOCKED_DOMAINS = [
    'spam.com',
    'malware.net',
    'phishing.org',
]

# File upload limits
MAX_LOGO_SIZE_MB = 5
MAX_SCREENSHOT_SIZE_MB = 10
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']

# Text validation
MIN_TITLE_LENGTH = 3
MAX_TITLE_LENGTH = 255
MIN_DESCRIPTION_LENGTH = 10
MAX_DESCRIPTION_LENGTH = 2000
MAX_INSTRUCTIONS_LENGTH = 1000

# Numeric validation
MIN_REWARD_AMOUNT = Decimal('0.01')
MAX_REWARD_AMOUNT = Decimal('1000.00')
MIN_RATING = 0.0
MAX_RATING = 5.0
MIN_TRUST_SCORE = 0
MAX_TRUST_SCORE = 100


# ==================== TASK SCHEDULING CONSTANTS ====================

# Celery task schedules (in seconds)
OFFER_SYNC_INTERVAL = 3600  # 1 hour
NETWORK_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
FRAUD_DETECTION_SCAN_INTERVAL = 600  # 10 minutes
STATS_CALCULATION_INTERVAL = 1800  # 30 minutes
LOG_CLEANUP_INTERVAL = 86400  # 24 hours

# Task timeouts
OFFER_SYNC_TIMEOUT = 300  # 5 minutes
NETWORK_HEALTH_CHECK_TIMEOUT = 30  # 30 seconds
FRAUD_DETECTION_TIMEOUT = 120  # 2 minutes
STATS_CALCULATION_TIMEOUT = 600  # 10 minutes

# Task retry settings
TASK_MAX_RETRIES = 3
TASK_RETRY_DELAY_SECONDS = 60
TASK_RETRY_BACKOFF_MULTIPLIER = 2


# ==================== API CONSTANTS ====================

# API versioning
API_VERSION = 'v1'
API_VERSION_HEADER = 'X-API-Version'
API_TENANT_HEADER = 'X-Tenant-ID'

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# Rate limiting
API_RATE_LIMIT_PER_USER = 1000  # per hour
API_RATE_LIMIT_PER_IP = 2000  # per hour
API_RATE_LIMIT_PER_TENANT = 10000  # per hour

# Response formats
DEFAULT_RESPONSE_FORMAT = 'json'
SUPPORTED_RESPONSE_FORMATS = ['json', 'xml']

# API documentation
API_DOCS_ENABLED = True
API_DOCS_URL = '/api/ad_networks/docs/'
API_SWAGGER_UI_ENABLED = True


# ==================== SECURITY CONSTANTS ====================

# JWT settings
JWT_SECRET_KEY = getattr(settings, 'AD_NETWORKS_JWT_SECRET_KEY', settings.SECRET_KEY)
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24
JWT_REFRESH_EXPIRATION_DAYS = 7

# CORS settings
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8080',
    'https://yourdomain.com',
]
CORS_ALLOW_CREDENTIALS = True

# SSL settings
SSL_REQUIRED = True
SSL_STRICT_TRANSPORT_SECURITY = True
SSL_HSTS_MAX_AGE = 31536000  # 1 year

# Security headers
SECURITY_HEADERS_ENABLED = True
X_FRAME_OPTIONS = 'DENY'
X_CONTENT_TYPE_OPTIONS = 'nosniff'
X_XSS_PROTECTION = '1; mode=block'


# ==================== HELPER FUNCTIONS ====================

def get_cache_key(pattern, **kwargs):
    """Generate cache key from pattern"""
    pattern_template = CACHE_KEY_PATTERNS.get(pattern, pattern)
    return pattern_template.format(**kwargs)


def get_network_config(network_type):
    """Get network configuration template"""
    return NETWORK_CONFIG_TEMPLATES.get(network_type, {})


def get_postback_url_template(template_type='default'):
    """Get postback URL template"""
    return POSTBACK_URL_TEMPLATES.get(template_type, POSTBACK_URL_TEMPLATES['default'])


def is_supported_network(network_type):
    """Check if network type is supported"""
    return network_type in SUPPORTED_NETWORKS


def get_tenant_limits(tier='starter'):
    """Get tenant limits based on pricing tier"""
    return TENANT_PRICING_TIERS.get(tier, TENANT_PRICING_TIERS['starter'])


def get_fraud_threshold(risk_level='medium'):
    """Get fraud threshold based on risk level"""
    thresholds = {
        'low': LOW_RISK_THRESHOLD,
        'medium': MEDIUM_RISK_THRESHOLD,
        'high': HIGH_RISK_THRESHOLD,
    }
    return thresholds.get(risk_level, MEDIUM_RISK_THRESHOLD)


def clear_cache_pattern(pattern):
    """Clear cache keys matching pattern"""
    # Implementation would depend on your cache backend
    # This is a placeholder for the function
    pass


def get_log_retention_days():
    """Get log retention days from settings"""
    return getattr(settings, 'AD_NETWORKS_LOG_RETENTION_DAYS', LOG_RETENTION_DAYS)


def is_production():
    """Check if running in production"""
    return getattr(settings, 'DEBUG', False) is False


def get_api_timeout(operation='default'):
    """Get API timeout for specific operation"""
    timeouts = {
        'default': API_TIMEOUT_SECONDS,
        'postback': POSTBACK_TIMEOUT_SECONDS,
        'webhook': WEBHOOK_TIMEOUT_SECONDS,
        'health_check': NETWORK_HEALTH_CHECK_TIMEOUT,
    }
    return timeouts.get(operation, API_TIMEOUT_SECONDS)


# ==================== FILE UPLOAD CONSTANTS ====================

UPLOAD_SETTINGS = {
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_IMAGE_TYPES': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'ALLOWED_DOCUMENT_TYPES': ['pdf', 'doc', 'docx', 'txt'],
    'THUMBNAIL_SIZE': (300, 300),
    'COMPRESS_IMAGES': True,
    'SECURE_FILENAME': True,
}

FILE_SIZE_LIMITS = {
    'image': 5 * 1024 * 1024,  # 5MB
    'document': 10 * 1024 * 1024,  # 10MB
    'video': 50 * 1024 * 1024,  # 50MB
    'audio': 10 * 1024 * 1024,  # 10MB
}

ALLOWED_MIME_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
    'video': ['video/mp4', 'video/avi', 'video/mov'],
    'audio': ['audio/mp3', 'audio/wav', 'audio/ogg'],
}

IMAGE_DIMENSIONS = {
    'thumbnail': (150, 150),
    'small': (300, 300),
    'medium': (600, 600),
    'large': (1200, 1200),
}

STORAGE_CONFIG = {
    'DEFAULT_STORAGE': 'django.core.files.storage.FileSystemStorage',
    'S3_STORAGE': 'storages.backends.s3boto3.S3Boto3Storage',
    'PRIVATE_STORAGE': 'private_storage.storage.PrivateFileSystemStorage',
    'UPLOAD_TO': 'ad_networks/uploads/',
    'PRIVATE_UPLOAD_TO': 'ad_networks/private/',
}

# ==================== NETWORK CONSTANTS ====================

SUPPORTED_NETWORKS = {
    'admob': {
        'name': 'Google AdMob',
        'category': 'mobile',
        'api_version': 'v3',
        'supports_offers': True,
        'supports_postback': True,
    },
    'unity_ads': {
        'name': 'Unity Ads',
        'category': 'mobile',
        'api_version': 'v1',
        'supports_offers': True,
        'supports_postback': True,
    },
    'tapjoy': {
        'name': 'Tapjoy',
        'category': 'mobile',
        'api_version': 'v4',
        'supports_offers': True,
        'supports_postback': True,
    },
    'ironsource': {
        'name': 'IronSource',
        'category': 'mobile',
        'api_version': 'v1',
        'supports_offers': True,
        'supports_postback': True,
    },
    'applovin': {
        'name': 'AppLovin',
        'category': 'mobile',
        'api_version': 'v1',
        'supports_offers': True,
        'supports_postback': True,
    },
}

API_TIMEOUT_SECONDS = 30
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 1.0

# ==================== CACHE TIMEOUTS ====================

CACHE_TIMEOUTS = {
    'offer_list': 300,  # 5 minutes
    'offer_detail': 600,  # 10 minutes
    'network_status': 60,  # 1 minute
    'user_stats': 1800,  # 30 minutes
    'fraud_detection': 3600,  # 1 hour
    'analytics': 3600,  # 1 hour
}

# ==================== REWARD STATUS ====================

RewardStatus = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('paid', 'Paid'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
)

# ==================== VALIDATION CONSTANTS ====================

MIN_PAYOUT_AMOUNT = Decimal('0.50')
MAX_PAYOUT_AMOUNT = Decimal('1000.00')
MIN_OFFER_TITLE_LENGTH = 5
MAX_OFFER_TITLE_LENGTH = 255
MIN_OFFER_DESCRIPTION_LENGTH = 10
MAX_OFFER_DESCRIPTION_LENGTH = 2000

# ==================== SECURITY CONSTANTS ====================

SECURITY_SETTINGS = {
    'MAX_LOGIN_ATTEMPTS': 5,
    'LOGIN_TIMEOUT': 1800,  # 30 minutes
    'SESSION_TIMEOUT': 3600,  # 1 hour
    'CSRF_PROTECTION': True,
    'RATE_LIMIT_PER_MINUTE': 100,
    'RATE_LIMIT_PER_HOUR': 1000,
}

# ==================== WEBHOOK CONSTANTS ====================

WEBHOOK_SETTINGS = {
    'TIMEOUT': 30,
    'MAX_RETRIES': 3,
    'RETRY_DELAY': 5,
    'SIGNATURE_HEADER': 'X-Signature',
    'SIGNATURE_ALGORITHM': 'sha256',
    'MAX_PAYLOAD_SIZE': 1024 * 1024,  # 1MB
}

# ==================== ANALYTICS CONSTANTS ====================

ANALYTICS_SETTINGS = {
    'DEFAULT_TIMEZONE': 'Asia/Dhaka',
    'STATS_RETENTION_DAYS': 365,
    'AGGREGATION_INTERVALS': ['hour', 'day', 'week', 'month'],
    'METRIC_PRECISION': 2,
}

# ==================== NOTIFICATION CONSTANTS ====================

NOTIFICATION_SETTINGS = {
    'EMAIL_ENABLED': True,
    'SMS_ENABLED': False,
    'PUSH_ENABLED': True,
    'WEBHOOK_ENABLED': True,
    'BATCH_SIZE': 100,
    'MAX_RETRIES': 3,
}

# ==================== INTEGRATION CONSTANTS ====================

INTEGRATION_SETTINGS = {
    'ENABLED_NETWORKS': ['admob', 'unity_ads', 'tapjoy'],
    'AUTO_SYNC_INTERVAL': 3600,  # 1 hour
    'MAX_OFFERS_PER_SYNC': 1000,
    'SYNC_TIMEOUT': 300,  # 5 minutes
}


# Wallet transaction types
WALLET_TRANSACTION_TYPES = [
    ('earning', 'Earning'),
    ('reward', 'Reward'),
    ('referral', 'Referral Commission'),
    ('bonus', 'Bonus'),
    ('withdrawal', 'Withdrawal'),
    ('reversal', 'Reversal'),
    ('adjustment', 'Admin Adjustment'),
]

# Webhook settings
WEBHOOK_RETRY_LIMIT = 3
WEBHOOK_TIMEOUT = WEBHOOK_TIMEOUT_SECONDS if 'WEBHOOK_TIMEOUT_SECONDS' in dir() else 30

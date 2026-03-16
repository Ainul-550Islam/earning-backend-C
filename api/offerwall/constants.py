"""
Constants and configuration for offerwall system
"""

# Provider Types
PROVIDER_TAPJOY = 'tapjoy'
PROVIDER_ADGEM = 'adgem'
PROVIDER_ADGATE = 'adgate'
PROVIDER_OFFERWALL = 'offerwall'
PROVIDER_PERSONA = 'persona'
PROVIDER_CPX = 'cpx'
PROVIDER_BITLABS = 'bitlabs'
PROVIDER_POLLFISH = 'pollfish'

# Offer Types
OFFER_TYPE_APP_INSTALL = 'app_install'
OFFER_TYPE_SIGNUP = 'signup'
OFFER_TYPE_SURVEY = 'survey'
OFFER_TYPE_VIDEO = 'video'
OFFER_TYPE_GAME = 'game'
OFFER_TYPE_TRIAL = 'trial'
OFFER_TYPE_PURCHASE = 'purchase'
OFFER_TYPE_SUBSCRIPTION = 'subscription'
OFFER_TYPE_QUIZ = 'quiz'
OFFER_TYPE_DOWNLOAD = 'download'
OFFER_TYPE_CASHBACK = 'cashback'

# Platforms
PLATFORM_ALL = 'all'
PLATFORM_ANDROID = 'android'
PLATFORM_IOS = 'ios'
PLATFORM_WEB = 'web'
PLATFORM_MOBILE = 'mobile'
PLATFORM_DESKTOP = 'desktop'

# Status
STATUS_ACTIVE = 'active'
STATUS_PAUSED = 'paused'
STATUS_COMPLETED = 'completed'
STATUS_EXPIRED = 'expired'
STATUS_DISABLED = 'disabled'

# Conversion Status
CONVERSION_PENDING = 'pending'
CONVERSION_APPROVED = 'approved'
CONVERSION_REJECTED = 'rejected'
CONVERSION_CHARGEBACK = 'chargeback'
CONVERSION_REVERSED = 'reversed'

# Difficulty Levels
DIFFICULTY_EASY = 'easy'
DIFFICULTY_MEDIUM = 'medium'
DIFFICULTY_HARD = 'hard'

# Event Types
EVENT_OFFER_VIEW = 'offer_view'
EVENT_OFFER_CLICK = 'offer_click'
EVENT_OFFER_CONVERSION = 'offer_conversion'
EVENT_OFFER_APPROVED = 'offer_approved'
EVENT_OFFER_REJECTED = 'offer_rejected'

# Webhook Events
WEBHOOK_CONVERSION = 'conversion'
WEBHOOK_CHARGEBACK = 'chargeback'
WEBHOOK_REVERSAL = 'reversal'

# Provider API Endpoints
TAPJOY_API_BASE = 'https://ws.tapjoyads.com/v1'
ADGEM_API_BASE = 'https://api.adgem.com/v1'
ADGATE_API_BASE = 'https://api.adgatemedia.com/v3'
OFFERWALL_API_BASE = 'https://www.offertoro.com/api'

# Default Configuration
DEFAULT_REVENUE_SHARE = 70.0  # 70% to users, 30% platform fee
DEFAULT_RATE_LIMIT_MINUTE = 60
DEFAULT_RATE_LIMIT_HOUR = 3600
DEFAULT_SYNC_INTERVAL = 60  # minutes
DEFAULT_MIN_PAYOUT = 0.01

# Limits
MAX_USER_COMPLETIONS_PER_DAY = 100
MAX_OFFER_CLICKS_PER_HOUR = 50
MAX_DAILY_EARNINGS = 1000.00

# Quality Score Weights
QUALITY_WEIGHT_COMPLETION_RATE = 0.30
QUALITY_WEIGHT_CTR = 0.20
QUALITY_WEIGHT_REVENUE = 0.20
QUALITY_WEIGHT_RECENCY = 0.10
QUALITY_WEIGHT_FRAUD = 0.20

# Fraud Detection Thresholds
FRAUD_THRESHOLD_HIGH = 70
FRAUD_THRESHOLD_MEDIUM = 40
FRAUD_THRESHOLD_LOW = 20

# Conversion Time Limits
CONVERSION_TIMEOUT_HOURS = 72
PENDING_CONVERSION_REVIEW_HOURS = 24

# Cache Keys
CACHE_KEY_OFFER_LIST = 'offers:list:{}'
CACHE_KEY_OFFER_DETAIL = 'offers:detail:{}'
CACHE_KEY_USER_OFFERS = 'offers:user:{}:available'
CACHE_KEY_PROVIDER_STATUS = 'providers:status:{}'
CACHE_KEY_CATEGORY_OFFERS = 'offers:category:{}'

# Cache TTL (seconds)
CACHE_TTL_OFFER_LIST = 300  # 5 minutes
CACHE_TTL_OFFER_DETAIL = 600  # 10 minutes
CACHE_TTL_USER_OFFERS = 180  # 3 minutes
CACHE_TTL_PROVIDER_STATUS = 900  # 15 minutes

# Postback Parameters
POSTBACK_PARAMS = {
    'user_id': '{user_id}',
    'offer_id': '{offer_id}',
    'payout': '{payout}',
    'currency': '{currency}',
    'transaction_id': '{transaction_id}',
    'ip': '{ip_address}',
    'timestamp': '{timestamp}',
    'signature': '{signature}',
}

# Supported Countries (ISO 2-letter codes)
TIER_1_COUNTRIES = [
    'US', 'CA', 'GB', 'AU', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE',
    'NO', 'DK', 'FI', 'CH', 'AT', 'BE', 'IE', 'NZ', 'SG', 'JP'
]

TIER_2_COUNTRIES = [
    'IN', 'BR', 'MX', 'AR', 'CL', 'CO', 'PE', 'PH', 'TH', 'MY',
    'ID', 'VN', 'PK', 'BD', 'NG', 'ZA', 'EG', 'TR', 'SA', 'AE'
]

# Device Types
DEVICE_TYPE_MOBILE = 'mobile'
DEVICE_TYPE_TABLET = 'tablet'
DEVICE_TYPE_DESKTOP = 'desktop'

# Browser Types
BROWSER_CHROME = 'chrome'
BROWSER_FIREFOX = 'firefox'
BROWSER_SAFARI = 'safari'
BROWSER_EDGE = 'edge'
BROWSER_OPERA = 'opera'

# Operating Systems
OS_ANDROID = 'android'
OS_IOS = 'ios'
OS_WINDOWS = 'windows'
OS_MACOS = 'macos'
OS_LINUX = 'linux'

# Error Messages
ERROR_OFFER_NOT_FOUND = 'Offer not found'
ERROR_OFFER_INACTIVE = 'Offer is not active'
ERROR_OFFER_NOT_AVAILABLE = 'Offer is not available for your account'
ERROR_OFFER_LIMIT_REACHED = 'You have reached the limit for this offer'
ERROR_DAILY_LIMIT_REACHED = 'Daily earning limit reached'
ERROR_INVALID_PROVIDER = 'Invalid provider configuration'
ERROR_PROVIDER_UNAVAILABLE = 'Provider service is unavailable'
ERROR_INVALID_POSTBACK = 'Invalid postback signature'
ERROR_DUPLICATE_CONVERSION = 'Duplicate conversion detected'
ERROR_FRAUD_DETECTED = 'Fraudulent activity detected'

# Success Messages
SUCCESS_OFFER_CLICKED = 'Offer clicked successfully'
SUCCESS_CONVERSION_RECORDED = 'Conversion recorded successfully'
SUCCESS_REWARD_CREDITED = 'Reward credited to your account'
SUCCESS_OFFER_SYNCED = 'Offers synced successfully'

# Notification Messages
NOTIFICATION_OFFER_COMPLETED = 'You completed an offer!'
NOTIFICATION_REWARD_CREDITED = 'Reward of {} {} has been credited'
NOTIFICATION_CONVERSION_PENDING = 'Your conversion is pending verification'
NOTIFICATION_CONVERSION_APPROVED = 'Your conversion has been approved!'
NOTIFICATION_CONVERSION_REJECTED = 'Your conversion was rejected: {}'

# API Response Codes
CODE_SUCCESS = 200
CODE_CREATED = 201
CODE_BAD_REQUEST = 400
CODE_UNAUTHORIZED = 401
CODE_FORBIDDEN = 403
CODE_NOT_FOUND = 404
CODE_CONFLICT = 409
CODE_SERVER_ERROR = 500
CODE_SERVICE_UNAVAILABLE = 503

# Logging
LOG_OFFER_VIEWED = 'Offer viewed: {} by user {}'
LOG_OFFER_CLICKED = 'Offer clicked: {} by user {}'
LOG_CONVERSION_RECEIVED = 'Conversion received: {} for offer {}'
LOG_CONVERSION_APPROVED = 'Conversion approved: {} for user {}'
LOG_CONVERSION_REJECTED = 'Conversion rejected: {} - Reason: {}'
LOG_FRAUD_DETECTED = 'Fraud detected: {} for user {}'
LOG_PROVIDER_SYNC = 'Syncing offers from provider: {}'
LOG_PROVIDER_ERROR = 'Provider error: {} - {}'

# Metrics
METRIC_OFFER_VIEWS = 'offer_views'
METRIC_OFFER_CLICKS = 'offer_clicks'
METRIC_OFFER_CONVERSIONS = 'offer_conversions'
METRIC_REVENUE = 'total_revenue'
METRIC_PAYOUT = 'total_payout'
METRIC_CONVERSION_RATE = 'conversion_rate'
METRIC_CTR = 'click_through_rate'
METRIC_QUALITY_SCORE = 'quality_score'

# Default Timeouts (seconds)
API_TIMEOUT_DEFAULT = 30
API_TIMEOUT_SYNC = 60
API_TIMEOUT_POSTBACK = 15

# Retry Configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_STATUS_CODES = [408, 429, 500, 502, 503, 504]

# Webhook Security
WEBHOOK_SIGNATURE_ALGORITHM = 'sha256'
WEBHOOK_SIGNATURE_HEADER = 'X-Signature'
WEBHOOK_TIMESTAMP_HEADER = 'X-Timestamp'
WEBHOOK_MAX_AGE_SECONDS = 300  # 5 minutes

# Validation Rules
MIN_OFFER_TITLE_LENGTH = 10
MAX_OFFER_TITLE_LENGTH = 300
MIN_OFFER_DESCRIPTION_LENGTH = 20
MAX_OFFER_DESCRIPTION_LENGTH = 5000
MIN_PAYOUT_AMOUNT = 0.01
MAX_PAYOUT_AMOUNT = 10000.00
MIN_USER_AGE = 13
MAX_USER_AGE = 120

# Feature Flags
FEATURE_AUTO_APPROVE_CONVERSIONS = False
FEATURE_FRAUD_DETECTION = True
FEATURE_BONUS_REWARDS = True
FEATURE_REFERRAL_BONUS = True
FEATURE_DAILY_LIMITS = True
FEATURE_GEO_TARGETING = True
FEATURE_DEVICE_TARGETING = True
FEATURE_A_B_TESTING = False

# A/B Testing
AB_TEST_VARIANTS = ['control', 'variant_a', 'variant_b']
AB_TEST_SPLIT_RATIO = [50, 25, 25]  # Percentage for each variant

# Performance Monitoring
PERFORMANCE_SLOW_QUERY_THRESHOLD = 1.0  # seconds
PERFORMANCE_ALERT_THRESHOLD = 5.0  # seconds
PERFORMANCE_LOG_SAMPLING_RATE = 0.1  # 10% sampling

# Rate Limiting
RATE_LIMIT_OFFER_VIEW = '1000/hour'
RATE_LIMIT_OFFER_CLICK = '100/hour'
RATE_LIMIT_API_CALL = '500/hour'
RATE_LIMIT_WEBHOOK = '10000/hour'
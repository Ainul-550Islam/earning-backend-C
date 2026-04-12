"""
Constants for Advertiser Portal

This module contains all constant values used throughout the application,
including configuration values, limits, and default settings.
"""

from typing import Dict, List, Tuple
from decimal import Decimal

# Application Constants
APP_NAME = "Advertiser Portal"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "High-end Advertising Management System"

# Status Constants
class StatusConstants:
    """Status-related constants."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# Campaign Constants
class CampaignConstants:
    """Campaign-related constants."""
    
    # Campaign objectives
    OBJECTIVES = {
        'awareness': 'Brand Awareness',
        'traffic': 'Website Traffic',
        'engagement': 'Engagement',
        'leads': 'Lead Generation',
        'sales': 'Sales/Conversions',
        'app_promotion': 'App Promotion',
        'store_visits': 'Store Visits',
        'brand_safety': 'Brand Safety'
    }
    
    # Bidding strategies
    BIDDING_STRATEGIES = {
        'manual_cpc': 'Manual CPC',
        'enhanced_cpc': 'Enhanced CPC',
        'target_cpa': 'Target CPA',
        'target_roas': 'Target ROAS',
        'maximize_clicks': 'Maximize Clicks',
        'maximize_conversions': 'Maximize Conversions',
        'target_impression_share': 'Target Impression Share'
    }
    
    # Budget limits
    MIN_DAILY_BUDGET = Decimal('1.00')
    MAX_DAILY_BUDGET = Decimal('100000.00')
    MIN_TOTAL_BUDGET = Decimal('10.00')
    MAX_TOTAL_BUDGET = Decimal('10000000.00')
    
    # Campaign limits
    MAX_CAMPAIGNS_PER_ADVERTISER = 100
    MAX_CREATIVES_PER_CAMPAIGN = 50
    MAX_TARGETING_RULES_PER_CAMPAIGN = 20
    
    # Duration limits
    MIN_CAMPAIGN_DURATION_DAYS = 1
    MAX_CAMPAIGN_DURATION_DAYS = 365
    
    # Performance thresholds
    LOW_CTR_THRESHOLD = 1.0  # Percentage
    HIGH_CTR_THRESHOLD = 5.0  # Percentage
    LOW_CONVERSION_RATE_THRESHOLD = 1.0  # Percentage
    HIGH_CONVERSION_RATE_THRESHOLD = 5.0  # Percentage

# Creative Constants
class CreativeConstants:
    """Creative-related constants."""
    
    # Creative types
    TYPES = {
        'banner': 'Banner Ad',
        'video': 'Video Ad',
        'native': 'Native Ad',
        'playable': 'Playable Ad',
        'interactive': 'Interactive Ad',
        'rich_media': 'Rich Media Ad',
        'html5': 'HTML5 Ad',
        'dynamic': 'Dynamic Creative'
    }
    
    # File size limits (in bytes)
    MAX_FILE_SIZES = {
        'banner': 150 * 1024,      # 150KB
        'video': 50 * 1024 * 1024, # 50MB
        'native': 100 * 1024,      # 100KB
        'playable': 5 * 1024 * 1024,  # 5MB
        'interactive': 2 * 1024 * 1024,  # 2MB
        'rich_media': 2 * 1024 * 1024,  # 2MB
        'html5': 500 * 1024,       # 500KB
        'dynamic': 100 * 1024     # 100KB
    }
    
    # Allowed MIME types
    ALLOWED_MIME_TYPES = {
        'banner': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
        'video': ['video/mp4', 'video/webm', 'video/quicktime'],
        'native': ['image/jpeg', 'image/png', 'image/gif'],
        'playable': ['application/zip', 'application/x-zip-compressed'],
        'interactive': ['application/zip', 'application/x-zip-compressed', 'text/html'],
        'rich_media': ['application/zip', 'application/x-zip-compressed', 'text/html'],
        'html5': ['text/html', 'application/javascript', 'text/css'],
        'dynamic': ['application/json', 'text/html']
    }
    
    # Standard dimensions
    STANDARD_DIMENSIONS = {
        'banner': [
            (300, 250),   # Medium Rectangle
            (728, 90),    # Leaderboard
            (160, 600),   # Wide Skyscraper
            (300, 600),   # Large Rectangle
            (320, 50),    # Mobile Leaderboard
            (320, 480),   # Mobile Rectangle
        ],
        'video': [
            (1920, 1080), # Full HD
            (1280, 720),  # HD
            (854, 480),   # 480p
            (640, 360),   # 360p
        ]
    }
    
    # Text length limits
    MAX_TITLE_LENGTH = 255
    MAX_DESCRIPTION_LENGTH = 500
    MAX_CALL_TO_ACTION_LENGTH = 100

# Targeting Constants
class TargetingConstants:
    """Targeting-related constants."""
    
    # Device types
    DEVICE_TYPES = {
        'desktop': 'Desktop',
        'mobile': 'Mobile',
        'tablet': 'Tablet',
        'connected_tv': 'Connected TV'
    }
    
    # OS families
    OS_FAMILIES = {
        'windows': 'Windows',
        'macos': 'macOS',
        'linux': 'Linux',
        'ios': 'iOS',
        'android': 'Android',
        'other': 'Other'
    }
    
    # Browsers
    BROWSERS = {
        'chrome': 'Chrome',
        'firefox': 'Firefox',
        'safari': 'Safari',
        'edge': 'Edge',
        'opera': 'Opera',
        'ie': 'Internet Explorer'
    }
    
    # Age ranges
    MIN_AGE = 13
    MAX_AGE = 65
    AGE_RANGES = [
        (13, 17),
        (18, 24),
        (25, 34),
        (35, 44),
        (45, 54),
        (55, 64),
        (65, 100)
    ]
    
    # Genders
    GENDERS = {
        'male': 'Male',
        'female': 'Female',
        'other': 'Other',
        'unknown': 'Unknown'
    }
    
    # Geo targeting limits
    MAX_COUNTRIES = 50
    MAX_REGIONS = 100
    MAX_CITIES = 500
    MAX_POSTAL_CODES = 1000
    MAX_COORDINATE_RADIUS = 1000  # kilometers
    
    # Interest categories
    INTEREST_CATEGORIES = [
        'technology', 'sports', 'entertainment', 'news', 'business',
        'health', 'education', 'travel', 'food', 'fashion',
        'automotive', 'real_estate', 'finance', 'shopping', 'gaming'
    ]
    
    # Keyword limits
    MAX_KEYWORDS = 1000
    MAX_EXCLUDE_KEYWORDS = 500
    MAX_KEYWORD_LENGTH = 100

# Analytics Constants
class AnalyticsConstants:
    """Analytics-related constants."""
    
    # Metrics
    METRICS = {
        'impressions': 'Impressions',
        'clicks': 'Clicks',
        'conversions': 'Conversions',
        'ctr': 'Click-Through Rate',
        'cpc': 'Cost Per Click',
        'cpm': 'Cost Per Mille',
        'cpa': 'Cost Per Action',
        'roas': 'Return On Ad Spend',
        'roi': 'Return On Investment',
        'conversion_rate': 'Conversion Rate',
        'cost': 'Cost',
        'revenue': 'Revenue'
    }
    
    # Dimensions
    DIMENSIONS = {
        'date': 'Date',
        'campaign': 'Campaign',
        'advertiser': 'Advertiser',
        'creative': 'Creative',
        'device': 'Device',
        'country': 'Country',
        'region': 'Region',
        'city': 'City',
        'browser': 'Browser',
        'os': 'Operating System'
    }
    
    # Date ranges
    DATE_RANGES = {
        'today': 'Today',
        'yesterday': 'Yesterday',
        'last_7_days': 'Last 7 Days',
        'last_30_days': 'Last 30 Days',
        'this_month': 'This Month',
        'last_month': 'Last Month',
        'this_quarter': 'This Quarter',
        'last_quarter': 'Last Quarter',
        'this_year': 'This Year',
        'last_year': 'Last Year'
    }
    
    # Statistical significance
    STATISTICAL_SIGNIFICANCE_THRESHOLD = 0.05
    MIN_SAMPLE_SIZE = 100
    
    # Anomaly detection
    ANOMALY_DETECTION_THRESHOLD = 2.0  # Standard deviations
    MIN_DATA_POINTS_FOR_ANOMALY_DETECTION = 10

# Billing Constants
class BillingConstants:
    """Billing-related constants."""
    
    # Payment methods
    PAYMENT_METHODS = {
        'credit_card': 'Credit Card',
        'debit_card': 'Debit Card',
        'bank_transfer': 'Bank Transfer',
        'paypal': 'PayPal',
        'wire_transfer': 'Wire Transfer',
        'crypto': 'Cryptocurrency'
    }
    
    # Billing cycles
    BILLING_CYCLES = {
        'prepaid': 'Prepaid',
        'postpaid': 'Postpaid',
        'monthly': 'Monthly',
        'quarterly': 'Quarterly',
        'annually': 'Annually'
    }
    
    # Currency
    DEFAULT_CURRENCY = 'USD'
    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD']
    
    # Payment limits
    MIN_PAYMENT_AMOUNT = Decimal('10.00')
    MAX_PAYMENT_AMOUNT = Decimal('1000000.00')
    
    # Invoice settings
    INVOICE_NUMBER_PREFIX = "INV"
    PAYMENT_TERMS_DAYS = 30
    LATE_FEE_RATE = Decimal('0.02')  # 2% per day
    
    # Tax rates by country (simplified)
    TAX_RATES = {
        'US': Decimal('0.00'),  # No federal sales tax
        'GB': Decimal('0.20'),  # 20% VAT
        'DE': Decimal('0.19'),  # 19% VAT
        'FR': Decimal('0.20'),  # 20% VAT
        'CA': Decimal('0.05'),  # 5% GST
        'AU': Decimal('0.10'),  # 10% GST
    }
    
    # Credit limits
    DEFAULT_CREDIT_LIMIT = Decimal('1000.00')
    MAX_CREDIT_LIMIT = Decimal('100000.00')

# Fraud Detection Constants
class FraudConstants:
    """Fraud detection-related constants."""
    
    # Fraud types
    FRAUD_TYPES = {
        'click_fraud': 'Click Fraud',
        'impression_fraud': 'Impression Fraud',
        'conversion_fraud': 'Conversion Fraud',
        'bot_traffic': 'Bot Traffic',
        'proxy_traffic': 'Proxy Traffic',
        'invalid_geo': 'Invalid Geographic Location',
        'suspicious_pattern': 'Suspicious Pattern'
    }
    
    # Risk thresholds
    RISK_THRESHOLDS = {
        'low': 20,
        'medium': 50,
        'high': 80
    }
    
    # Detection rules
    MAX_CLICKS_PER_IP_PER_HOUR = 100
    MAX_CLICKS_PER_IP_PER_DAY = 500
    MAX_CONVERSIONS_PER_IP_PER_DAY = 50
    
    # Time windows
    FRAUD_DETECTION_WINDOW_MINUTES = 60
    BLOCK_DURATION_HOURS = 24
    
    # Scoring
    HIGH_RISK_SCORE = 80
    MEDIUM_RISK_SCORE = 50
    LOW_RISK_SCORE = 20

# Cache Constants
class CacheConstants:
    """Cache-related constants."""
    
    # Cache keys
    CACHE_KEYS = {
        'advertiser_stats': 'advertiser_stats_{advertiser_id}',
        'campaign_performance': 'campaign_performance_{campaign_id}',
        'creative_performance': 'creative_performance_{creative_id}',
        'targeting_estimate': 'targeting_estimate_{targeting_id}',
        'user_permissions': 'user_permissions_{user_id}',
        'rate_limit': 'rate_limit_{service}_{user_id}'
    }
    
    # Cache timeouts (in seconds)
    TIMEOUTS = {
        'short': 60,           # 1 minute
        'medium': 300,         # 5 minutes
        'long': 3600,          # 1 hour
        'daily': 86400,        # 24 hours
        'weekly': 604800,      # 7 days
        'monthly': 2592000     # 30 days
    }
    
    # Cache prefixes
    PREFIXES = {
        'advertiser': 'adv',
        'campaign': 'cam',
        'creative': 'cre',
        'targeting': 'tar',
        'analytics': 'ana',
        'billing': 'bil',
        'fraud': 'fraud'
    }

# API Constants
class APIConstants:
    """API-related constants."""
    
    # API versions
    CURRENT_API_VERSION = 'v1'
    SUPPORTED_API_VERSIONS = ['v1']
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = 1000  # requests per hour
    PREMIUM_RATE_LIMIT = 5000  # requests per hour
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Response codes
    RESPONSE_CODES = {
        'success': 200,
        'created': 201,
        'accepted': 202,
        'no_content': 204,
        'bad_request': 400,
        'unauthorized': 401,
        'forbidden': 403,
        'not_found': 404,
        'method_not_allowed': 405,
        'conflict': 409,
        'rate_limited': 429,
        'server_error': 500
    }
    
    # Error codes
    ERROR_CODES = {
        'validation_error': 'VALIDATION_ERROR',
        'authentication_error': 'AUTHENTICATION_ERROR',
        'authorization_error': 'AUTHORIZATION_ERROR',
        'not_found_error': 'NOT_FOUND_ERROR',
        'conflict_error': 'CONFLICT_ERROR',
        'rate_limit_error': 'RATE_LIMIT_ERROR',
        'server_error': 'SERVER_ERROR'
    }

# Email Constants
class EmailConstants:
    """Email-related constants."""
    
    # Email types
    EMAIL_TYPES = {
        'verification': 'Email Verification',
        'welcome': 'Welcome Email',
        'campaign_approved': 'Campaign Approved',
        'campaign_rejected': 'Campaign Rejected',
        'budget_alert': 'Budget Alert',
        'invoice': 'Invoice',
        'payment_confirmation': 'Payment Confirmation',
        'password_reset': 'Password Reset',
        'suspension_notice': 'Account Suspension'
    }
    
    # From addresses
    FROM_ADDRESSES = {
        'noreply': 'noreply@advertiserportal.com',
        'support': 'support@advertiserportal.com',
        'billing': 'billing@advertiserportal.com',
        'security': 'security@advertiserportal.com'
    }
    
    # Templates
    TEMPLATES = {
        'verification': 'emails/verification.html',
        'welcome': 'emails/welcome.html',
        'campaign_approved': 'emails/campaign_approved.html',
        'campaign_rejected': 'emails/campaign_rejected.html',
        'budget_alert': 'emails/budget_alert.html',
        'invoice': 'emails/invoice.html',
        'payment_confirmation': 'emails/payment_confirmation.html',
        'password_reset': 'emails/password_reset.html',
        'suspension_notice': 'emails/suspension_notice.html'
    }

# Integration Constants
class IntegrationConstants:
    """Third-party integration constants."""
    
    # Google Ads
    GOOGLE_ADS = {
        'api_version': 'v12',
        'developer_token': '',  # To be configured
        'client_customer_id': '',  # To be configured
        'refresh_token': '',  # To be configured
    }
    
    # Facebook Ads
    FACEBOOK_ADS = {
        'api_version': 'v18.0',
        'app_id': '',  # To be configured
        'app_secret': '',  # To be configured
        'access_token': '',  # To be configured
    }
    
    # Google Analytics
    GOOGLE_ANALYTICS = {
        'tracking_id': '',  # To be configured
        'measurement_id': '',  # To be configured
        'api_secret': '',  # To be configured
    }
    
    # Payment gateways
    PAYMENT_GATEWAYS = {
        'stripe': {
            'publishable_key': '',  # To be configured
            'secret_key': '',  # To be configured
            'webhook_secret': '',  # To be configured
        },
        'paypal': {
            'client_id': '',  # To be configured
            'client_secret': '',  # To be configured
            'webhook_id': '',  # To be configured
        }
    }

# Logging Constants
class LoggingConstants:
    """Logging-related constants."""
    
    # Log levels
    LEVELS = {
        'debug': 'DEBUG',
        'info': 'INFO',
        'warning': 'WARNING',
        'error': 'ERROR',
        'critical': 'CRITICAL'
    }
    
    # Log categories
    CATEGORIES = {
        'api': 'API',
        'billing': 'BILLING',
        'campaign': 'CAMPAIGN',
        'creative': 'CREATIVE',
        'fraud': 'FRAUD',
        'security': 'SECURITY',
        'performance': 'PERFORMANCE'
    }
    
    # Audit actions
    AUDIT_ACTIONS = {
        'create': 'CREATE',
        'update': 'UPDATE',
        'delete': 'DELETE',
        'activate': 'ACTIVATE',
        'deactivate': 'DEACTIVATE',
        'approve': 'APPROVE',
        'reject': 'REJECT',
        'suspend': 'SUSPEND',
        'login': 'LOGIN',
        'logout': 'LOGOUT'
    }

# Feature Flags
class FeatureFlags:
    """Feature flag constants."""
    
    FLAGS = {
        'advanced_targeting': True,
        'real_time_bidding': True,
        'machine_learning_optimization': False,
        'multi_currency_billing': False,
        'api_v2': False,
        'beta_features': False,
        'advanced_analytics': True,
        'fraud_detection': True,
        'a_b_testing': True,
        'custom_reports': True
    }

# Configuration Constants
class ConfigConstants:
    """Configuration constants."""
    
    # Environment
    ENVIRONMENTS = {
        'development': 'development',
        'staging': 'staging',
        'production': 'production'
    }
    
    # Database
    DATABASE_CONNECTIONS = {
        'default': 'default',
        'analytics': 'analytics',
        'cache': 'cache'
    }
    
    # Security
    SECURITY = {
        'password_min_length': 8,
        'password_require_uppercase': True,
        'password_require_lowercase': True,
        'password_require_digits': True,
        'password_require_special': True,
        'session_timeout_minutes': 30,
        'max_login_attempts': 5,
        'lockout_duration_minutes': 15
    }
    
    # File storage
    STORAGE = {
        'max_file_size_mb': 50,
        'allowed_image_formats': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
        'allowed_video_formats': ['mp4', 'webm', 'mov'],
        'allowed_document_formats': ['pdf', 'doc', 'docx'],
        'storage_backend': 's3',  # or 'local'
    }

# Validation Constants
class ValidationConstants:
    """Validation-related constants."""
    
    # Regular expressions
    REGEX_PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?1?\d{9,15}$',
        'url': r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        'company_name': r'^[a-zA-Z0-9\s\-\.\,&\']+$',
        'api_key': r'^[a-zA-Z0-9_\-]{32,}$'
    }
    
    # Field lengths
    FIELD_LENGTHS = {
        'company_name': {'min': 2, 'max': 255},
        'industry': {'min': 2, 'max': 100},
        'email': {'max': 254},
        'phone': {'max': 20},
        'campaign_name': {'min': 2, 'max': 255},
        'creative_name': {'min': 2, 'max': 255},
        'description': {'max': 1000},
        'api_key': {'min': 32, 'max': 255}
    }
    
    # Numeric ranges
    NUMERIC_RANGES = {
        'daily_budget': {'min': 1.00, 'max': 100000.00},
        'total_budget': {'min': 10.00, 'max': 10000000.00},
        'age': {'min': 13, 'max': 65},
        'percentage': {'min': 0.0, 'max': 100.0},
        'rating': {'min': 0.0, 'max': 5.0}
    }

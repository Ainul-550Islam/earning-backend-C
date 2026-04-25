"""
Tenant Constants - System Configuration and Default Values

This module contains all constant values, configuration defaults,
and system-wide settings for the tenant management system.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import re

# System Configuration
TENANT_SYSTEM_VERSION = "2.0.0"
TENANT_API_VERSION = "v1"
TENANT_MIN_DJANGO_VERSION = "4.2"
TENANT_MIN_PYTHON_VERSION = "3.8"

# Database Configuration
TENANT_DB_MAX_CONNECTIONS = getattr(settings, 'TENANT_DB_MAX_CONNECTIONS', 100)
TENANT_DB_CONNECTION_TIMEOUT = getattr(settings, 'TENANT_DB_CONNECTION_TIMEOUT', 30)
TENANT_DB_QUERY_TIMEOUT = getattr(settings, 'TENANT_DB_QUERY_TIMEOUT', 60)

# Cache Configuration
TENANT_CACHE_TIMEOUT = getattr(settings, 'TENANT_CACHE_TIMEOUT', 300)  # 5 minutes
TENANT_SETTINGS_CACHE_TIMEOUT = getattr(settings, 'TENANT_SETTINGS_CACHE_TIMEOUT', 600)  # 10 minutes
TENANT_BILLING_CACHE_TIMEOUT = getattr(settings, 'TENANT_BILLING_CACHE_TIMEOUT', 300)  # 5 minutes
TENANT_FEATURES_CACHE_TIMEOUT = getattr(settings, 'TENANT_FEATURES_CACHE_TIMEOUT', 300)  # 5 minutes
TENANT_USER_COUNT_CACHE_TIMEOUT = getattr(settings, 'TENANT_USER_COUNT_CACHE_TIMEOUT', 300)  # 5 minutes

# Security Configuration
TENANT_MAX_LOGIN_ATTEMPTS = getattr(settings, 'TENANT_MAX_LOGIN_ATTEMPTS', 5)
TENANT_LOGIN_LOCKOUT_DURATION = getattr(settings, 'TENANT_LOGIN_LOCKOUT_DURATION', 300)  # 5 minutes
TENANT_PASSWORD_MIN_LENGTH = getattr(settings, 'TENANT_PASSWORD_MIN_LENGTH', 8)
TENANT_PASSWORD_MAX_LENGTH = getattr(settings, 'TENANT_PASSWORD_MAX_LENGTH', 128)
TENANT_SESSION_TIMEOUT_MINUTES = getattr(settings, 'TENANT_SESSION_TIMEOUT_MINUTES', 1440)  # 24 hours

# API Configuration
TENANT_API_RATE_LIMIT_REQUESTS = getattr(settings, 'TENANT_API_RATE_LIMIT_REQUESTS', 1000)
TENANT_API_RATE_LIMIT_WINDOW = getattr(settings, 'TENANT_API_RATE_LIMIT_WINDOW', 3600)  # 1 hour
TENANT_API_PAGE_SIZE_DEFAULT = getattr(settings, 'TENANT_API_PAGE_SIZE_DEFAULT', 20)
TENANT_API_PAGE_SIZE_MAX = getattr(settings, 'TENANT_API_PAGE_SIZE_MAX', 100)

# File Upload Configuration
TENANT_MAX_FILE_SIZE_MB = getattr(settings, 'TENANT_MAX_FILE_SIZE_MB', 100)
TENANT_ALLOWED_FILE_EXTENSIONS = getattr(settings, 'TENANT_ALLOWED_FILE_EXTENSIONS', [
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'zip', 'rar', '7z', 'tar', 'gz',
    'mp4', 'avi', 'mov', 'wmv', 'flv',
    'mp3', 'wav', 'ogg', 'aac',
])
TENANT_UPLOAD_PATH = getattr(settings, 'TENANT_UPLOAD_PATH', 'tenants/uploads/')

# Email Configuration
TENANT_EMAIL_FROM_ADDRESS = getattr(settings, 'TENANT_EMAIL_FROM_ADDRESS', settings.DEFAULT_FROM_EMAIL)
TENANT_EMAIL_REPLY_TO = getattr(settings, 'TENANT_EMAIL_REPLY_TO', settings.DEFAULT_FROM_EMAIL)
TENANT_SUPPORT_EMAIL = getattr(settings, 'TENANT_SUPPORT_EMAIL', 'support@example.com')
TENANT_BILLING_EMAIL = getattr(settings, 'TENANT_BILLING_EMAIL', 'billing@example.com')

# Billing Configuration
TENANT_DEFAULT_TRIAL_DAYS = getattr(settings, 'TENANT_DEFAULT_TRIAL_DAYS', 14)
TENANT_MIN_WITHDRAWAL_AMOUNT = Decimal(getattr(settings, 'TENANT_MIN_WITHDRAWAL_AMOUNT', '5.00'))
TENANT_MAX_WITHDRAWAL_AMOUNT = Decimal(getattr(settings, 'TENANT_MAX_WITHDRAWAL_AMOUNT', '10000.00'))
TENANT_DEFAULT_WITHDRAWAL_FEE_PERCENT = Decimal(getattr(settings, 'TENANT_DEFAULT_WITHDRAWAL_FEE_PERCENT', '0.00'))
TENANT_DAILY_WITHDRAWAL_LIMIT = Decimal(getattr(settings, 'TENANT_DAILY_WITHDRAWAL_LIMIT', '1000.00'))

# Plan Configuration
TENANT_DEFAULT_PLAN = getattr(settings, 'TENANT_DEFAULT_PLAN', 'basic')
TENANT_MAX_USERS_PER_PLAN = getattr(settings, 'TENANT_MAX_USERS_PER_PLAN', {
    'basic': 100,
    'pro': 500,
    'enterprise': 10000,
    'custom': 0,  # Unlimited
})

TENANT_FEATURES_PER_PLAN = getattr(settings, 'TENANT_FEATURES_PER_PLAN', {
    'basic': ['referral', 'offerwall'],
    'pro': ['referral', 'offerwall', 'kyc', 'leaderboard'],
    'enterprise': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics'],
    'custom': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics', 'api_access'],
})

# Notification Configuration
TENANT_NOTIFICATION_CHANNELS = getattr(settings, 'TENANT_NOTIFICATION_CHANNELS', ['email'])
TENANT_BATCH_EMAIL_SIZE = getattr(settings, 'TENANT_BATCH_EMAIL_SIZE', 100)
TENANT_EMAIL_RETRY_ATTEMPTS = getattr(settings, 'TENANT_EMAIL_RETRY_ATTEMPTS', 3)

# Audit Configuration
TENANT_AUDIT_LOG_RETENTION_DAYS = getattr(settings, 'TENANT_AUDIT_LOG_RETENTION_DAYS', 365)
TENANT_AUDIT_LOG_BATCH_SIZE = getattr(settings, 'TENANT_AUDIT_LOG_BATCH_SIZE', 1000)
TENANT_AUDIT_LOG_ARCHIVE_DAYS = getattr(settings, 'TENANT_AUDIT_LOG_ARCHIVE_DAYS', 90)

# Backup Configuration
TENANT_BACKUP_RETENTION_DAYS = getattr(settings, 'TENANT_BACKUP_RETENTION_DAYS', 30)
TENANT_BACKUP_SCHEDULE = getattr(settings, 'TENANT_BACKUP_SCHEDULE', '0 2 * * *')  # Daily at 2 AM
TENANT_BACKUP_ENCRYPTION = getattr(settings, 'TENANT_BACKUP_ENCRYPTION', True)

# Webhook Configuration
TENANT_WEBHOOK_TIMEOUT_SECONDS = getattr(settings, 'TENANT_WEBHOOK_TIMEOUT_SECONDS', 30)
TENANT_WEBHOOK_RETRY_ATTEMPTS = getattr(settings, 'TENANT_WEBHOOK_RETRY_ATTEMPTS', 3)
TENANT_WEBHOOK_RETRY_DELAY = getattr(settings, 'TENANT_WEBHOOK_RETRY_DELAY', 60)  # seconds

# Maintenance Configuration
TENANT_MAINTENANCE_MODE = getattr(settings, 'TENANT_MAINTENANCE_MODE', False)
TENANT_MAINTENANCE_MESSAGE = getattr(settings, 'TENANT_MAINTENANCE_MESSAGE', 
    _('System is currently under maintenance. Please try again later.'))

# Performance Configuration
TENANT_PERFORMANCE_MONITORING = getattr(settings, 'TENANT_PERFORMANCE_MONITORING', True)
TENANT_SLOW_QUERY_THRESHOLD = getattr(settings, 'TENANT_SLOW_QUERY_THRESHOLD', 1000)  # milliseconds
TENANT_MEMORY_USAGE_THRESHOLD = getattr(settings, 'TENANT_MEMORY_USAGE_THRESHOLD', 80)  # percentage

# Integration Configuration
TENANT_STRIPE_WEBHOOK_SECRET = getattr(settings, 'TENANT_STRIPE_WEBHOOK_SECRET', '')
TENANT_PAYPAL_WEBHOOK_URL = getattr(settings, 'TENANT_PAYPAL_WEBHOOK_URL', '')
TENANT_GOOGLE_ANALYTICS_TRACKING_ID = getattr(settings, 'TENANT_GOOGLE_ANALYTICS_TRACKING_ID', '')

# Validation Patterns
TENANT_SLUG_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$')
TENANT_DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$')
TENANT_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
TENANT_PHONE_PATTERN = re.compile(r'^\+?[\d\s\-\(\)]+$')
TENANT_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')
TENANT_UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')

# Reserved Words and Patterns
TENANT_RESERVED_SLUGS = [
    'www', 'mail', 'ftp', 'admin', 'api', 'app', 'www', 'test', 'dev',
    'staging', 'production', 'demo', 'example', 'sample', 'default',
    'system', 'root', 'administrator', 'guest', 'anonymous',
]

TENANT_RESERVED_DOMAINS = [
    'localhost', 'example.com', 'test.com', 'demo.com',
    '127.0.0.1', '0.0.0.0', '255.255.255.255',
]

# Error Messages
TENANT_ERROR_MESSAGES = {
    'tenant_not_found': _('Tenant not found.'),
    'access_denied': _('Access denied. You do not have permission to perform this action.'),
    'invalid_plan': _('Invalid subscription plan.'),
    'user_limit_reached': _('User limit has been reached for this tenant.'),
    'trial_expired': _('Trial period has expired.'),
    'subscription_inactive': _('Subscription is not active.'),
    'invalid_credentials': _('Invalid credentials provided.'),
    'rate_limit_exceeded': _('Rate limit exceeded. Please try again later.'),
    'file_too_large': _('File size exceeds maximum allowed limit.'),
    'invalid_file_type': _('File type not allowed.'),
    'maintenance_mode': _('System is currently under maintenance.'),
    'feature_disabled': _('This feature is disabled for your plan.'),
    'billing_issue': _('There is an issue with your billing. Please update your payment method.'),
    'suspended': _('Your account has been suspended. Please contact support.'),
    'domain_taken': _('This domain is already taken.'),
    'slug_taken': _('This slug is already taken.'),
    'invalid_email': _('Please provide a valid email address.'),
    'weak_password': _('Password does not meet security requirements.'),
    'session_expired': _('Your session has expired. Please log in again.'),
}

# Success Messages
TENANT_SUCCESS_MESSAGES = {
    'tenant_created': _('Tenant created successfully.'),
    'tenant_updated': _('Tenant updated successfully.'),
    'tenant_deleted': _('Tenant deleted successfully.'),
    'settings_updated': _('Settings updated successfully.'),
    'feature_toggled': _('Feature status updated successfully.'),
    'api_key_regenerated': _('API key regenerated successfully.'),
    'webhook_secret_regenerated': _('Webhook secret regenerated successfully.'),
    'file_uploaded': _('File uploaded successfully.'),
    'invoice_paid': _('Invoice marked as paid successfully.'),
    'trial_extended': _('Trial period extended successfully.'),
    'subscription_activated': _('Subscription activated successfully.'),
    'user_added': _('User added successfully.'),
    'user_removed': _('User removed successfully.'),
    'password_changed': _('Password changed successfully.'),
    'email_verified': _('Email verified successfully.'),
    'payment_processed': _('Payment processed successfully.'),
}

# Warning Messages
TENANT_WARNING_MESSAGES = {
    'trial_expiring': _('Your trial period is expiring soon.'),
    'user_limit_warning': _('You are approaching your user limit.'),
    'storage_limit_warning': _('You are approaching your storage limit.'),
    'payment_due': _('Payment is due soon.'),
    'overdue_payment': _('Your payment is overdue.'),
    'security_warning': _('Security issue detected. Please review your account.'),
    'api_usage_high': _('API usage is unusually high.'),
    'backup_failed': _('Backup process failed.'),
    'sync_failed': _('Data synchronization failed.'),
}

# Info Messages
TENANT_INFO_MESSAGES = {
    'welcome': _('Welcome to the platform!'),
    'trial_started': _('Your trial period has started.'),
    'subscription_renewed': _('Your subscription has been renewed.'),
    'payment_received': _('Payment received successfully.'),
    'feature_enabled': _('Feature has been enabled.'),
    'feature_disabled': _('Feature has been disabled.'),
    'settings_saved': _('Settings have been saved.'),
    'profile_updated': _('Profile has been updated.'),
    'email_sent': _('Email has been sent.'),
    'backup_completed': _('Backup completed successfully.'),
    'sync_completed': _('Data synchronization completed successfully.'),
}

# Default Settings
TENANT_DEFAULT_SETTINGS = {
    'app_name': 'EarningApp',
    'enable_referral': True,
    'enable_offerwall': True,
    'enable_kyc': True,
    'enable_leaderboard': True,
    'enable_chat': False,
    'enable_push_notifications': True,
    'enable_analytics': True,
    'enable_api_access': True,
    'min_withdrawal': Decimal('5.00'),
    'max_withdrawal': Decimal('10000.00'),
    'withdrawal_fee_percent': Decimal('0.00'),
    'withdrawal_fee_fixed': Decimal('0.00'),
    'daily_withdrawal_limit': Decimal('1000.00'),
    'referral_bonus_amount': Decimal('1.00'),
    'referral_bonus_type': 'fixed',
    'max_referral_levels': 3,
    'referral_percentages': [50, 30, 20],
    'require_email_verification': True,
    'require_phone_verification': False,
    'enable_two_factor_auth': False,
    'password_min_length': 8,
    'session_timeout_minutes': 1440,
    'api_rate_limit': '1000/hour',
    'login_rate_limit': '5/minute',
}

# Default Billing Settings
TENANT_DEFAULT_BILLING_SETTINGS = {
    'status': 'trial',
    'billing_cycle': 'monthly',
    'monthly_price': Decimal('0.00'),
    'setup_fee': Decimal('0.00'),
    'currency': 'USD',
    'trial_ends_at': None,  # Will be set based on trial days
    'subscription_starts_at': None,
    'subscription_ends_at': None,
    'last_payment_at': None,
    'next_payment_at': None,
    'cancelled_at': None,
    'current_period_start': None,
    'current_period_end': None,
}

# Feature Configuration
TENANT_FEATURE_CONFIG = {
    'referral': {
        'name': _('Referral System'),
        'description': _('Enable user referral program with rewards'),
        'plans': ['basic', 'pro', 'enterprise', 'custom'],
        'dependencies': [],
        'settings': {
            'referral_bonus_amount': Decimal('1.00'),
            'referral_bonus_type': 'fixed',
            'max_referral_levels': 3,
            'referral_percentages': [50, 30, 20],
        },
    },
    'offerwall': {
        'name': _('Offerwall'),
        'description': _('Enable third-party offer integration'),
        'plans': ['basic', 'pro', 'enterprise', 'custom'],
        'dependencies': [],
        'settings': {},
    },
    'kyc': {
        'name': _('KYC Verification'),
        'description': _('Enable Know Your Customer verification'),
        'plans': ['pro', 'enterprise', 'custom'],
        'dependencies': [],
        'settings': {
            'require_phone_verification': False,
            'enable_two_factor_auth': False,
        },
    },
    'leaderboard': {
        'name': _('Leaderboard'),
        'description': _('Enable user ranking and competition'),
        'plans': ['pro', 'enterprise', 'custom'],
        'dependencies': [],
        'settings': {},
    },
    'chat': {
        'name': _('Chat System'),
        'description': _('Enable real-time chat functionality'),
        'plans': ['enterprise', 'custom'],
        'dependencies': ['push_notifications'],
        'settings': {},
    },
    'push_notifications': {
        'name': _('Push Notifications'),
        'description': _('Enable mobile push notifications'),
        'plans': ['enterprise', 'custom'],
        'dependencies': [],
        'settings': {
            'firebase_server_key': None,
        },
    },
    'analytics': {
        'name': _('Analytics Dashboard'),
        'description': _('Enable comprehensive analytics and reporting'),
        'plans': ['enterprise', 'custom'],
        'dependencies': [],
        'settings': {},
    },
    'api_access': {
        'name': _('API Access'),
        'description': _('Enable advanced API access and webhooks'),
        'plans': ['custom'],
        'dependencies': [],
        'settings': {
            'api_rate_limit': 'unlimited',
        },
    },
}

# Integration Constants
TENANT_INTEGRATIONS = {
    'stripe': {
        'name': _('Stripe'),
        'description': _('Payment processing via Stripe'),
        'enabled': True,
        'webhook_events': [
            'invoice.payment_succeeded',
            'invoice.payment_failed',
            'customer.subscription.created',
            'customer.subscription.deleted',
            'customer.subscription.updated',
        ],
        'settings': {
            'secret_key': '',
            'publishable_key': '',
            'webhook_secret': '',
        },
    },
    'paypal': {
        'name': _('PayPal'),
        'description': _('Payment processing via PayPal'),
        'enabled': False,
        'webhook_events': [
            'PAYMENT.SALE.COMPLETED',
            'PAYMENT.SALE.DENIED',
            'BILLING.SUBSCRIPTION.CREATED',
            'BILLING.SUBSCRIPTION.CANCELLED',
        ],
        'settings': {
            'client_id': '',
            'client_secret': '',
            'webhook_url': '',
        },
    },
    'google_analytics': {
        'name': _('Google Analytics'),
        'description': _('Analytics tracking via Google Analytics'),
        'enabled': False,
        'settings': {
            'tracking_id': '',
        },
    },
    'firebase': {
        'name': _('Firebase'),
        'description': _('Push notifications and real-time database'),
        'enabled': False,
        'settings': {
            'server_key': '',
            'database_url': '',
        },
    },
}

# Validation Constants
TENANT_VALIDATION_RULES = {
    'name': {
        'min_length': 2,
        'max_length': 255,
        'required': True,
        'pattern': r'^[a-zA-Z0-9\s\-_\.]+$',
        'error_message': _('Tenant name can only contain letters, numbers, spaces, hyphens, underscores, and dots.'),
    },
    'slug': {
        'min_length': 3,
        'max_length': 50,
        'required': True,
        'pattern': r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]$',
        'error_message': _('Slug can only contain letters, numbers, and hyphens, and cannot start or end with a hyphen.'),
    },
    'domain': {
        'min_length': 3,
        'max_length': 255,
        'required': False,
        'pattern': r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$',
        'error_message': _('Domain must be a valid domain name.'),
    },
    'admin_email': {
        'required': True,
        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'error_message': _('Please provide a valid email address.'),
    },
    'contact_phone': {
        'required': False,
        'pattern': r'^\+?[\d\s\-\(\)]+$',
        'error_message': _('Please provide a valid phone number.'),
    },
    'max_users': {
        'min_value': 1,
        'max_value': 1000000,
        'required': True,
        'error_message': _('Max users must be between 1 and 1,000,000.'),
    },
    'primary_color': {
        'required': False,
        'pattern': r'^#[0-9A-Fa-f]{6}$',
        'error_message': _('Color must be a valid hex color code (e.g., #FF0000).'),
    },
    'secondary_color': {
        'required': False,
        'pattern': r'^#[0-9A-Fa-f]{6}$',
        'error_message': _('Color must be a valid hex color code (e.g., #FF0000).'),
    },
}

# Pagination Constants
TENANT_PAGINATION_DEFAULTS = {
    'page_size': 20,
    'page_size_query_param': 'page_size',
    'page_query_param': 'page',
    'max_page_size': 100,
}

# Export Constants
TENANT_EXPORT_FORMATS = ['csv', 'xlsx', 'json', 'pdf']
TENANT_EXPORT_MAX_RECORDS = 10000
TENANT_EXPORT_TIMEOUT = 300  # 5 minutes

# Import Constants
TENANT_IMPORT_FORMATS = ['csv', 'xlsx', 'json']
TENANT_IMPORT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
TENANT_IMPORT_BATCH_SIZE = 1000

# Logging Constants
TENANT_LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
}

TENANT_LOG_FORMATS = {
    'detailed': '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d',
    'simple': '%(asctime)s - %(levelname)s - %(message)s',
    'json': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(name)s"}',
}

# Monitoring Constants
TENANT_METRICS = {
    'user_count': 'tenant_user_count',
    'active_sessions': 'tenant_active_sessions',
    'api_requests': 'tenant_api_requests',
    'storage_usage': 'tenant_storage_usage',
    'billing_status': 'tenant_billing_status',
    'feature_usage': 'tenant_feature_usage',
}

TENANT_ALERT_THRESHOLDS = {
    'user_usage_percent': 90,
    'storage_usage_percent': 90,
    'api_requests_per_minute': 1000,
    'error_rate_percent': 5,
    'response_time_ms': 2000,
}

# Security Constants
TENANT_SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
}

TENANT_ENCRYPTION_ALGORITHMS = {
    'password': 'pbkdf2_sha256',
    'api_key': 'aes-256-gcm',
    'sensitive_data': 'aes-256-cbc',
}

# Development Constants
TENANT_DEBUG_SETTINGS = {
    'enable_debug_toolbar': True,
    'enable_sql_debug': True,
    'enable_request_logging': True,
    'enable_performance_profiling': True,
}

# Production Constants
TENANT_PRODUCTION_SETTINGS = {
    'enable_debug_toolbar': False,
    'enable_sql_debug': False,
    'enable_request_logging': True,
    'enable_performance_profiling': False,
}

# Testing Constants
TENANT_TEST_SETTINGS = {
    'test_database': 'test_tenants',
    'test_cache_backend': 'django.core.cache.backends.dummy.DummyCache',
    'test_email_backend': 'django.core.mail.backends.locmem.EmailBackend',
    'test_file_storage': 'django.core.files.storage.FileSystemStorage',
}

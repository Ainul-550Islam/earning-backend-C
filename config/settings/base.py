from pathlib import Path
import environ
import os
from datetime import timedelta
from celery.schedules import crontab

# ==================== BASE DIR ====================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ==================== ENV ====================
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-fx-=99r4pivad601*#wz5i25gc)+&j-q^#ls9($2)f&yea74gm')
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

# ==================== INSTALLED APPS ====================
INSTALLED_APPS = [
    # Django core apps (MUST BE FIRST)
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'social_django',
    'drf_spectacular',
    'django.contrib.sites',

    # Third-party apps
    'ckeditor',
    'ckeditor_uploader',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'admob_ssv',

    # Core
    'core',

    # API Apps
    'api',
    'api.users.apps.UsersConfig',
    'api.security',
    'api.admin_panel',
    'api.payment_gateways',
    'api.ad_networks',
    'api.offerwall',
    'api.fraud_detection',
    'api.analytics',
    'api.referral',
    'api.engagement',
    'api.notifications',
    'api.cms',
    'api.support',
    'api.alerts',
    'api.djoyalty',
    'api.wallet.apps.WalletConfig',
    'api.kyc',
    'api.cache',
    'api.tasks',
    'api.rate_limit',
    'api.localization',
    'api.audit_logs',
    'api.tests',
    'api.backup',
    'api.promotions',
    'api.subscription.apps.SubscriptionConfig',
    'api.gamification.apps.GamificationConfig',
    'api.auto_mod.apps.AutoModConfig',
    'api.version_control.apps.VersionControlConfig',
    'api.behavior_analytics.apps.BehaviorAnalyticsConfig',
    'api.postback.apps.PostbackConfig',
    'api.inventory.apps.InventoryConfig',
    'api.messaging',
    'api.payout_queue.apps.PayoutQueueConfig',
    'api.tenants.apps.TenantsConfig',
    'api.webhooks.apps.WebhooksConfig',
    'api.marketplace',
    'api.postback_engine',
    'api.monetization_tools',
    'api.publisher_tools',
    'api.proxy_intelligence',
    'api.advertiser_portal',
    'api.offer_inventory',
    'api.smartlink', 
    'api.disaster_recovery.apps.DisasterRecoveryConfig',
    'api.dr_integration',
    'api.ai_engine',
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'api.dr_integration.middleware.DRAuditMiddleware',
    'api.users.security_middleware.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'api.admin_panel.endpoint_toggle.EndpointToggleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'api.smartlink.middleware.SmartLinkRedirectMiddleware',
    'api.smartlink.middleware.SmartLinkPerformanceMiddleware',
    'api.fraud_detection.middleware.FraudDetectionMiddleware',
    'api.security.middleware.SecurityAuditMiddleware',
    'api.rate_limit.middleware.RateLimitMiddleware',
    'api.rate_limit.middleware.EarningTaskRateLimitMiddleware',
    'api.payment_gateways.middleware.WebhookIPWhitelistMiddleware',
    'api.wallet.middleware.SafeIPMiddleware',
    'api.wallet.middleware.CircuitBreakerMiddleware',
    'api.tenants.middleware.TenantMiddleware',
    'api.wallet.middleware.DatabaseErrorMiddleware',
    'api.wallet.middleware.SecurityLogMiddleware',
    'api.wallet.middleware.RequestTimerMiddleware',
    'api.wallet.middleware.APIErrorMiddleware',
    'api.localization.middleware.ContentCompressionMiddleware',
    'api.localization.middleware.CORSMiddleware',
    'api.localization.middleware.RequestLoggingMiddleware',
    'api.localization.middleware.PerformanceMiddleware',
    'api.localization.middleware.RateLimitMiddleware',
    'api.localization.middleware.LanguageMiddleware',
    'api.localization.middleware.TimezoneMiddleware',
    'api.localization.middleware.CurrencyMiddleware',
    'api.localization.middleware.DeviceDetectionMiddleware',
    'api.localization.middleware.TranslationMiddleware',
    'api.localization.middleware.CacheHeadersMiddleware',
    'api.localization.middleware.SecurityHeadersMiddleware',
    'api.localization.middleware.MaintenanceModeMiddleware',
    'api.audit_logs.middleware.AuditLogMiddleware',
    'api.cache.middleware.RequestCacheMiddleware',
    'api.cache.middleware.PageCacheMiddleware',
    'api.cache.middleware.CacheControlMiddleware',

]

# ==================== URL / WSGI ====================
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# ==================== DATABASE ====================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='earning_db'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='12345'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'CONN_MAX_AGE': 0,
    }
}

# ==================== AUTH ====================
AUTH_USER_MODEL = 'users.User'

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    # 'UNAUTHENTICATED_USER': None, 
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ==================== REST FRAMEWORK THROTTLE ====================

# ==================== SOCIAL AUTH ====================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'api.users.google_backend.CustomGoogleOAuth2',
]
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['email', 'profile']
SOCIAL_AUTH_URL_NAMESPACE = 'social'

# ==================== REDIS ====================
import os as _os
REDIS_URL = _os.environ.get('REDIS_URL') or env('REDIS_URL', default=None)
print(f'[SETTINGS DEBUG] REDIS_URL={REDIS_URL}')

if not REDIS_URL:
    REDIS_HOST = env('REDIS_HOST', default='localhost')
    REDIS_PORT = env.int('REDIS_PORT', default=6379)
    REDIS_DB = env.int('REDIS_DB', default=0)
    REDIS_PASSWORD = env('REDIS_PASSWORD', default=None)

    if REDIS_PASSWORD:
        REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    else:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# ==================== CACHE ====================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# # Development এ cache override
# if DEBUG:
#     CACHES = {
#         'default': {
#             'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
#             "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
#             "LOCATION": "unique-snowflake",
#         }
#     }

# ==================== CELERY ====================
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_ENABLE_UTC = False
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TRACK_STARTED = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_CONCURRENCY = 4


CELERY_BEAT_SCHEDULE = {
    'process-pending-alerts-every-5-minutes': {
        'task': 'alerts.tasks.process_pending_alerts',
        'schedule': 300.0,
        'options': {'queue': 'alerts'}
    },
    'send-notifications-every-1-minute': {
        'task': 'alerts.tasks.send_notifications',
        'schedule': 60.0,
        'options': {'queue': 'notifications'}
    },
    'cleanup-old-data-daily': {
        'task': 'alerts.tasks.cleanup_old_data',
        'schedule': 86400.0,
        'options': {'queue': 'maintenance'}
    },
    'cleanup-expired-blacklist-daily': {
        'task': 'api.tasks.cleanup_expired_blacklist_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'maintenance'}
    },
    'monitor-suspicious-activity': {
        'task': 'api.tasks.monitor_suspicious_activity_task',
        'schedule': crontab(minute=0),
        'options': {'queue': 'monitoring'}
    },

    # Ainul Enterprise Engine - Webhook Dispatch Engine
    'webhook-reap-exhausted-logs-hourly': {
        'task': 'ainul.webhooks.reap_exhausted_logs',
        'schedule': crontab(minute=0),
        'options': {'queue': 'webhooks_periodic'},
    },
    'webhook-auto-suspend-bad-endpoints-daily': {
        'task': 'ainul.webhooks.auto_suspend_endpoints',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'webhooks_periodic'},
    },
}

CELERY_TASK_ROUTES = {
    'alerts.tasks.process_pending_alerts': {'queue': 'alerts'},
    'alerts.tasks.send_notifications': {'queue': 'notifications'},
    'alerts.tasks.cleanup_old_data': {'queue': 'maintenance'},
    # Ainul Enterprise Engine - Webhook Dispatch Engine
    'ainul.webhooks.retry_failed_dispatch': {'queue': 'webhooks'},
    'ainul.webhooks.dispatch_event': {'queue': 'webhooks'},
    'ainul.webhooks.reap_exhausted_logs': {'queue': 'webhooks_periodic'},
    'ainul.webhooks.auto_suspend_endpoints': {'queue': 'webhooks_periodic'},
}

# ==================== STATIC / MEDIA ====================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

MAX_UPLOAD_SIZE = 5242880  # 5MB
ALLOWED_UPLOAD_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']

# ==================== TEMPLATES ====================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ==================== CKEDITOR ====================
CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/"
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 300,
        'width': '100%',
    },
}

# ==================== CHANNELS ====================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# ==================== PAYMENT GATEWAYS ====================
BKASH_APP_KEY = env('BKASH_APP_KEY', default='your_bkash_app_key')
BKASH_APP_SECRET = env('BKASH_APP_SECRET', default='your_bkash_app_secret')
BKASH_USERNAME = env('BKASH_USERNAME', default='your_bkash_username')
BKASH_PASSWORD = env('BKASH_PASSWORD', default='your_bkash_password')
BKASH_WEBHOOK_SECRET = env('BKASH_WEBHOOK_SECRET', default='your_bkash_webhook_secret')
BKASH_BASE_URL = env('BKASH_BASE_URL', default='https://checkout.pay.bka.sh/v1.2.0-beta')

NAGAD_MERCHANT_ID = env('NAGAD_MERCHANT_ID', default='your_merchant_id')
NAGAD_MERCHANT_NUMBER = env('NAGAD_MERCHANT_NUMBER', default='your_merchant_number')
NAGAD_BASE_URL = env('NAGAD_BASE_URL', default='http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api/dfs')

STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='sk_test_...')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='pk_test_...')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='whsec_...')

WEBHOOK_ALLOWED_IPS = {
    'bkash': ['103.108.140.0/24', '103.108.141.0/24'],
    'stripe': ['3.18.12.0/22', '3.130.192.0/22'],
    'nagad': ['202.4.105.0/24'],
}

# ==================== VPN / FRAUD ====================
PROXYCHECK_API_KEY = env('PROXYCHECK_API_KEY', default='')
IPQUALITYSCORE_API_KEY = env('IPQUALITYSCORE_API_KEY', default='')
FRAUD_CHECK_ENABLED = True
BOT_DETECTION_ENABLED = True
ALLOW_DUPLICATE_CONVERSIONS = False
MAX_CONVERSIONS_PER_HOUR = 15
IP_REPUTATION_CACHE_TIME = 3600
STRICT_TIMING_CHECK_SECONDS = 3
RELAXED_TIMING_CHECK_SECONDS = 10

# ==================== RATE LIMIT ====================
RATE_LIMIT_SETTINGS = {
    'ENABLE_RATE_LIMIT': True,
    'DEFAULT_LIMITS': {
        'anonymous': '100/hour',
        'authenticated': '1000/hour',
        'premium': '5000/hour',
    },
    'EXCLUDE_PATHS': ['/admin/', '/static/', '/media/', '/health/'],
    'EXCLUDE_METHODS': ['OPTIONS'],
    'STORAGE_BACKEND': 'redis',
    'REDIS_PREFIX': 'rate_limit',
    'ENABLE_LOGGING': True,
    'LOG_RETENTION_DAYS': 30,
}

EARNING_RATE_LIMITS = {
    'TASK_DAILY_LIMIT': 10,
    'TASK_DAILY_LIMIT_PREMIUM': 50,
    'OFFER_HOURLY_LIMIT': 20,
    'REFERRAL_DAILY_LIMIT': 50,
    'WITHDRAWAL_DAILY_LIMIT': 3,
    'MINIMUM_TASK_INTERVAL': 30,
}

RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 60

# ==================== CACHE TIMEOUTS ====================
CACHE_TIMEOUTS = {
    'USER_PROFILE': 300,
    'USER_STATS': 60,
    'TASK_LIST': 30,
    'OFFER_LIST': 60,
    'LEADERBOARD': 300,
}

# ==================== CORS ====================
CSRF_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000', 'https://earning-backend-c-production.up.railway.app', 'https://earning-frontend-v2.vercel.app']
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000', 'http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8080', 'http://127.0.0.1:8080', 'http://192.168.0.178:8080'])
CORS_ALLOWED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

# ==================== MISC ====================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SITE_ID = 1
SITE_NAME = env('SITE_NAME', default='Earning App')
SITE_URL = env('SITE_URL', default='https://yourdomain.com')
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=30)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='alerts@yourdomain.com')

LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_AGE = 31536000
MAINTENANCE_MODE = False
MAINTENANCE_ALLOWED_IPS = ['127.0.0.1']
SLOW_REQUEST_THRESHOLD = 1.0

TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN', default='')
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='')

CMS_PERMISSIONS = {
    'can_manage_content': 'cms.manage_content',
    'can_manage_banners': 'cms.manage_banners',
    'can_manage_faqs': 'cms.manage_faqs',
    'can_manage_settings': 'cms.manage_settings',
}

ADMIN_SITE_HEADER = "Earning App Admin"
ADMIN_SITE_TITLE = "Admin Panel"
ADMIN_INDEX_TITLE = "Welcome to Admin"

SILENCED_SYSTEM_CHECKS = ['urls.W005', 'models.W001']

# ==================== LOGGING ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/debug.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'wallet': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'api.payment_gateways': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}


LOGIN_URL = '/api/auth/login/'

# WebSocket / Channels
ASGI_APPLICATION = 'config.settings.asgi.application'

# Fix UUID JSON serialization for psycopg2
try:
    import psycopg2.extras, psycopg2.extensions, json, uuid
    from decimal import Decimal
    from datetime import datetime, date
    class GlobalSafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, uuid.UUID): return str(obj)
            if isinstance(obj, (datetime, date)): return obj.isoformat()
            if isinstance(obj, Decimal): return float(obj)
            if hasattr(obj, 'pk'): return obj.pk
            return str(obj)
    psycopg2.extensions.register_adapter(dict, lambda d: psycopg2.extras.Json(d, dumps=lambda o: json.dumps(o, cls=GlobalSafeEncoder)))
    psycopg2.extensions.register_adapter(list, lambda l: psycopg2.extras.Json(l, dumps=lambda o: json.dumps(o, cls=GlobalSafeEncoder)))
except Exception:
    pass

# Force HTTPS for social auth
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

# Social Auth Pipeline
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)
SOCIAL_AUTH_LOGIN_REDIRECT_URL = 'https://earning-frontend-v2.vercel.app/dashboard'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = 'https://earning-frontend-v2.vercel.app/dashboard'
SOCIAL_AUTH_LOGIN_ERROR_URL = 'https://earning-frontend-v2.vercel.app/login'

# OAuth State Fix
SOCIAL_AUTH_FIELDS_STORED_IN_SESSION = ['state']
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True

# Fix clock skew for OAuth
import time
SOCIAL_AUTH_GOOGLE_OAUTH2_IGNORE_DEFAULT_SCOPE = False
USE_TZ = True
TIME_ZONE = 'UTC'

# Railway Proxy Fix
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Use Redis for sessions (fix OAuth state)
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Explicitly set OAuth redirect URI
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'

# Override Google backend
SOCIAL_AUTH_GOOGLE_OAUTH2_BACKEND_CLASS = 'api.users.google_backend.CustomGoogleOAuth2'

# Force Google account selection screen
SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {'prompt': 'select_account'}

# DRF Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Earning Platform API',
    'DESCRIPTION': 'API documentation',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'POSTPROCESSING_HOOKS': [],
    'DISABLE_ERRORS_AND_WARNINGS': True,
    'IGNORE_SCHEMA_GENERATION_ERRORS': True,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_GENERATE_CHOICE_DESCRIPTION': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
    },
}


# ==================== TENANT ====================
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Tenant"


CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",  # এটি না থাকলে SaaS লগইন হবে না
]

# আপনার ব্যাকএন্ড যদি /api/ দিয়ে শুরু হয়, তবে এটিও নিশ্চিত করুন
APPEND_SLASH = True


# DR System path
DR_SYSTEM_PATH = os.environ.get('DR_SYSTEM_PATH', '/app/disaster_recovery')

# Notifications (Slack, PagerDuty, Datadog)
DR_NOTIFICATION_CONFIG = {
    'slack_webhook_url': os.environ.get('DR_SLACK_WEBHOOK_URL', ''),
    'pagerduty_api_key': os.environ.get('DR_PAGERDUTY_API_KEY', ''),
    'pagerduty_integration_key': os.environ.get('DR_PAGERDUTY_INTEGRATION_KEY', ''),
    'datadog_api_key': os.environ.get('DR_DATADOG_API_KEY', ''),
}

# Backup storage
DR_LOCAL_BACKUP_PATH = os.environ.get('DR_LOCAL_BACKUP_PATH', '/var/backups/api')
DR_BACKUP_BACKENDS = ['local', 's3']

DR_STORAGE_CONFIGS = [
    {'name': 'local', 'provider': 'local', 'base_path': DR_LOCAL_BACKUP_PATH},
    {
        'name': 's3-backups',
        'provider': 'aws_s3',
        'bucket': os.environ.get('BACKUP_S3_BUCKET', ''),
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'access_key_id': os.environ.get('AWS_ACCESS_KEY_ID', ''),
        'secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    },
]

# Audit log files
DR_AUDIT_CONFIG = {
    'log_file': '/var/log/api/dr_audit.jsonl',
    'security_log_file': '/var/log/api/dr_security_audit.jsonl',
}

# Health check components
DR_HEALTH_CHECK_COMPONENTS = [
    {'name': 'database', 'type': 'database', 'url': os.environ.get('DATABASE_URL', '')},
    {'name': 'redis', 'type': 'tcp', 'host': 'localhost', 'port': 6379},
    {'name': 'api', 'type': 'http', 'url': 'http://localhost:8000/health/'},
]

# GDAL/GEOS settings
GDAL_LIBRARY_PATH = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\venv\Lib\site-packages\osgeo\gdal.dll'
GEOS_LIBRARY_PATH = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\venv\Lib\site-packages\osgeo\geos_c.dll'

# Status page components (তোমার app অনুযায়ী)
DR_STATUS_PAGE_COMPONENTS = [
    {'name': 'api',             'display_name': 'API Server',      'group': 'Application'},
    {'name': 'database',        'display_name': 'Database',         'group': 'Infrastructure'},
    {'name': 'offerwall',       'display_name': 'Offerwall',        'group': 'Application'},
    {'name': 'payment_gateway', 'display_name': 'Payment Gateway',  'group': 'External'},
    {'name': 'marketplace',     'display_name': 'Marketplace',      'group': 'Application'},
    {'name': 'ai_engine',       'display_name': 'AI Engine',        'group': 'Application'},
]

# Key management
DR_KEY_CONFIG = {
    'key_store_path': '/etc/api/dr_keys',
    'rotation_days': 90,
}

# On-call (optional)
DR_ON_CALL_ROSTER = [
    {
        'name': os.environ.get('ON_CALL_PRIMARY_NAME', 'Primary On-Call'),
        'email': os.environ.get('ON_CALL_PRIMARY_EMAIL', ''),
        'slack_id': os.environ.get('ON_CALL_PRIMARY_SLACK', ''),
    }
]

# Celery Beat — DR tasks (তোমার existing CELERY_BEAT_SCHEDULE এ merge করো)
DR_CELERY_BEAT_SCHEDULE = {
    'dr-incremental-backup-4h': {
        'task': 'dr_integration.auto_backup',
        'schedule': 4 * 60 * 60,
        'kwargs': {'backup_type': 'incremental'},
    },
    'dr-full-backup-weekly': {
        'task': 'dr_integration.auto_backup',
        'schedule': 7 * 24 * 60 * 60,
        'kwargs': {'backup_type': 'full'},
    },
    'dr-sync-status-5m': {
        'task': 'dr_integration.sync_dr_status',
        'schedule': 5 * 60,
    },
    'dr-verify-backups-daily': {
        'task': 'dr_integration.verify_recent_backups',
        'schedule': 24 * 60 * 60,
    },
    'dr-health-check-2m': {
        'task': 'dr_integration.health_check',
        'schedule': 2 * 60,
    },
    'dr-collect-metrics-1m': {
        'task': 'dr_integration.collect_and_push_metrics',
        'schedule': 60,
    },
}
GDAL_LIBRARY_PATH = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\venv\Lib\site-packages\osgeo\gdal.dll'
GEOS_LIBRARY_PATH = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\venv\Lib\site-packages\osgeo\geos_c.dll'
MIGRATION_MODULES = {'advertiser_portal': 'api.advertiser_portal.django_migrations'}

# ==================== LOCALIZATION SETTINGS ====================

# ── Translation Providers ────────────────────────────────────────
TRANSLATION_PROVIDERS = {
    'deepl': {
        'enabled': False,
        'priority': 1,
        'api_key': '',
    },
    'google': {
        'enabled': False,
        'priority': 2,
        'api_key': '',
        'project_id': '',
    },
    'azure': {
        'enabled': False,
        'priority': 3,
        'api_key': '',
        'region': 'eastus',
    },
    'amazon': {
        'enabled': False,
        'priority': 4,
        'api_key': '',
        'access_key': '',
        'region': 'us-east-1',
    },
    'openai': {
        'enabled': False,
        'priority': 5,
        'api_key': '',
        'model': 'gpt-4o-mini',
        'temperature': 0.2,
    },
}

# ── GeoIP ────────────────────────────────────────────────────────
MAXMIND_LICENSE_KEY = ''
GEOIP_PATH = '/var/lib/localization/GeoLite2-City.mmdb'
LOCALIZATION_DETECT_FROM_IP = True

# ── Localization App Settings ────────────────────────────────────
LOCALIZATION_ALERT_EMAIL = True
LOG_MISSING_TRANSLATIONS = True
USER_PREF_CACHE_TTL = 3600
API_CACHE_TIMEOUT = 3600
CACHE_24_HOURS = 86400
MAX_TRANSLATION_TEXT_LENGTH = 5000
LANGUAGE_PACK_CDN_URL = '/api/localization/public/translations'

# ── Localization API Keys ────────────────────────────────────────
LOCALIZATION_API_KEYS = []

# ── Localization Rate Limits ─────────────────────────────────────
LOCALIZATION_RATE_LIMITS = {
    'translate': '100/hour',
    'public_translations': '1000/hour',
    'currency_convert': '500/hour',
    'geoip': '200/hour',
}

# ── Localization Celery Beat (merged into main schedule) ─────────
CELERY_BEAT_SCHEDULE.update({
    'update-exchange-rates': {
        'task': 'api.localization.tasks.exchange_rate_tasks.update_rates',
        'schedule': crontab(minute=0),
        'options': {'expires': 3500},
    },
    'clean-translation-cache': {
        'task': 'api.localization.tasks.translation_cache_tasks.clean_expired_cache',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    'rebuild-popular-cache': {
        'task': 'api.localization.tasks.translation_cache_tasks.rebuild_popular_cache',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'auto-translate-missing': {
        'task': 'api.localization.tasks.auto_translation_tasks.auto_translate_missing',
        'schedule': crontab(minute=0, hour=2),
        'kwargs': {'limit': 200},
    },
    'translation-qa-check': {
        'task': 'api.localization.tasks.translation_qa_tasks.run_qa_check',
        'schedule': crontab(minute=0, hour=3),
    },
    'update-coverage': {
        'task': 'api.localization.tasks.coverage_report_tasks.update_coverage',
        'schedule': crontab(minute=0, hour=4),
    },
    'alert-missing-translations': {
        'task': 'api.localization.tasks.missing_translation_tasks.alert_missing_translations',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    'aggregate-daily-insights': {
        'task': 'api.localization.tasks.insight_tasks.aggregate_daily_insights',
        'schedule': crontab(minute=0, hour=0),
    },
    'cleanup-localization': {
        'task': 'api.localization.tasks.cleanup_tasks.cleanup_all',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),
    },
    'update-geoip-db': {
        'task': 'api.localization.tasks.geoip_update_tasks.update_geoip_db',
        'schedule': crontab(minute=0, hour=6, day_of_week=0),
    },
    'check-provider-health': {
        'task': 'api.localization.tasks.provider_health_tasks.check_provider_health',
        'schedule': crontab(minute='*/30'),
    },
    'index-translation-memory': {
        'task': 'api.localization.tasks.translation_memory_tasks.index_approved_translations',
        'schedule': crontab(minute=0, hour=7, day_of_week=1),
    },
    'build-language-packs': {
        'task': 'api.localization.tasks.language_pack_tasks.build_all_packs',
        'schedule': crontab(minute=0, hour=5),
    },
})

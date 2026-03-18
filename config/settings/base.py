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
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'api.fraud_detection.middleware.FraudDetectionMiddleware',
    'api.security.middleware.SecurityAuditMiddleware',
    'api.rate_limit.middleware.RateLimitMiddleware',
    'api.rate_limit.middleware.EarningTaskRateLimitMiddleware',
    'api.payment_gateways.middleware.WebhookIPWhitelistMiddleware',
    'api.wallet.middleware.SafeIPMiddleware',
    'api.wallet.middleware.CircuitBreakerMiddleware',
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
    }
}

# ==================== AUTH ====================
AUTH_USER_MODEL = 'users.User'

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
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
    'social_core.backends.google.GoogleOAuth2',
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
}

CELERY_TASK_ROUTES = {
    'alerts.tasks.process_pending_alerts': {'queue': 'alerts'},
    'alerts.tasks.send_notifications': {'queue': 'notifications'},
    'alerts.tasks.cleanup_old_data': {'queue': 'maintenance'},
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
CSRF_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000']
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000', 'http://localhost:5173', 'http://127.0.0.1:5173'])
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








# from pathlib import Path
# import environ
# import os
# from datetime import timedelta
# import django
# from celery.schedules import crontab
# from django.urls import reverse_lazy

# # ১. BASE_DIR আপডেট
# BASE_DIR = Path(__file__).resolve().parent.parent.parent

# # ২. env অবজেক্ট তৈরি এবং .env ফাইল লোড করা
# env = environ.Env(
#     DEBUG=(bool, False)
# )
# environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# # ৩. ভেরিয়েবলগুলো কল করা
# SECRET_KEY = env('SECRET_KEY', default='django-insecure-fx-=99r4pivad601*#wz5i25gc)+&j-q^#ls9($2)f&yea74gm')
# DEBUG = env.bool('DEBUG', default=True)
# ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

# # ২. অ্যাপগুলোর পাথ (ad_networks comment out করা হয়েছে - duplicate এড়াতে)
# INSTALLED_APPS = [
#     # "unfold",
#     # "unfold.contrib.filters",
#     # "unfold.contrib.forms",
#     # "unfold.contrib.inlines",
#     # "django.forms",
#     'ckeditor',
#     'ckeditor_uploader',
    
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',
#     'social_django',

#     'rest_framework',
#     'rest_framework.authtoken',
#     'django_filters',
#     'corsheaders',
#     'django_celery_beat',
#     'django_celery_results',
#     'rest_framework_simplejwt',
#     'rest_framework_simplejwt.token_blacklist',
#     'admob_ssv',

#     # Custom Core App
#     'core',
#     'django.contrib.sites',

#     # API Apps (Dotted notation mandatory)
#     'api',
#     'api.users',            # ১. User management
#     'api.security',
#     'api.admin_panel',      # ২. Admin dashboard
#     'api.payment_gateways', # ৩. Payment integrations
#     'api.ad_networks',      # ❌ Comment out - offerwall দিয়ে replace করা হয়েছে
#     'api.offerwall',        # ✅ Offerwall (replaces ad_networks)
#     'api.fraud_detection',  # ৫. Fraud prevention
#     'api.analytics',        # ৬. Analytics & reports
#     'api.referral',
#     'api.engagement',
#     'api.notifications',
#     'api.cms',              # ১০. Content management
#     'api.support',
#     'api.alerts',
#     'api.djoyalty',
#     'api.wallet',
#     'api.kyc',
#     'api.cache',            # ৭. Caching system
#     'api.tasks',            # ৮. Celery background tasks
#     'api.rate_limit',       # ৯. API rate limiting  
#     'api.localization',     # ১১. Multi-language
#     'api.audit_logs',       # ১২. Audit logging
#     'api.tests',            # ১৩. Automated tests
#     'api.backup',
    

# ]

# # ✅ সঠিক MIDDLEWARE (duplicate সরানো হয়েছে)
# MIDDLEWARE = [
#     'corsheaders.middleware.CorsMiddleware',
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'api.security.middleware.SecurityAuditMiddleware',
#     'api.rate_limit.middleware.RateLimitMiddleware',
#     'api.rate_limit.middleware.EarningTaskRateLimitMiddleware',
#     'api.payment_gateways.middleware.WebhookIPWhitelistMiddleware',
#     # আপনার custom middleware (এই顺序 গুরুত্বপূর্ণ)
#     'api.wallet.middleware.SafeIPMiddleware',
#     'api.wallet.middleware.CircuitBreakerMiddleware',
#     'api.wallet.middleware.DatabaseErrorMiddleware',
#     'api.wallet.middleware.SecurityLogMiddleware',
#     'api.wallet.middleware.RequestTimerMiddleware',
#     'api.wallet.middleware.APIErrorMiddleware',
#     'api.localization.middleware.ContentCompressionMiddleware',
#     'api.localization.middleware.CORSMiddleware',
#     'api.localization.middleware.RequestLoggingMiddleware',
#     'api.localization.middleware.PerformanceMiddleware',
#     'api.localization.middleware.RateLimitMiddleware',
#     'api.localization.middleware.LanguageMiddleware',
#     'api.localization.middleware.TimezoneMiddleware',
#     'api.localization.middleware.CurrencyMiddleware',
#     'api.localization.middleware.DeviceDetectionMiddleware',
#     'api.localization.middleware.TranslationMiddleware',
#     'api.localization.middleware.CacheHeadersMiddleware',
#     'api.localization.middleware.SecurityHeadersMiddleware',
#     'api.localization.middleware.MaintenanceModeMiddleware',
#     'api.audit_logs.middleware.AuditLogMiddleware'
# ]
# # Logging configuration
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'formatters': {
#         'verbose': {
#             'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
#             'style': '{',
#         },
#     },
#     'handlers': {
#         'console': {
#             'class': 'logging.StreamHandler',
#             'formatter': 'verbose',
#         },
#         'file': {
#             'class': 'logging.FileHandler',
#             'filename': 'debug.log',
#             'formatter': 'verbose',
#         },
#     },
#     'root': {
#         'handlers': ['console'],
#         'level': 'INFO',
#     },
#     'loggers': {
#         'wallet': {
#             'handlers': ['console', 'file'],
#             'level': 'DEBUG' if DEBUG else 'INFO',
#             'propagate': False,
#         },
#     },
# }


# # ৩. ROOT URL এবং WSGI পাথ আপডেট
# ROOT_URLCONF = 'config.urls'
# WSGI_APPLICATION = 'config.wsgi.application'


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME'),
#         'USER': os.getenv('DB_USER'),
#         'PASSWORD': os.getenv('DB_PASSWORD'),
#         'HOST': os.getenv('DB_HOST'),
#         'PORT': os.getenv('DB_PORT'),
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'earning_db',
#         'USER': 'postgres',
#         'PASSWORD': '12345',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# # ৪. Static এবং Media পাথ
# STATIC_URL = 'static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# # File upload settings
# MAX_UPLOAD_SIZE = 5242880  # 5MB
# ALLOWED_UPLOAD_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']

# # Task proof storage
# TASK_PROOF_STORAGE = {
#     'PATH': 'task_proofs/',
#     'MAX_SIZE': 5 * 1024 * 1024,  # 5MB
#     'ALLOWED_TYPES': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
# }

# # AUTH_USER_MODEL = 'api.User'
# AUTH_USER_MODEL = 'users.User'
 

# # ৬. REST Framework এবং JWT সেটিংস
# REST_FRAMEWORK = {
#     'DEFAULT_AUTHENTICATION_CLASSES': [
#         'rest_framework_simplejwt.authentication.JWTAuthentication',
#     ],
#     'DEFAULT_PERMISSION_CLASSES': [
#         'rest_framework.permissions.AllowAny',
#     ],
# }

# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
#     'ROTATE_REFRESH_TOKENS': True,
#     'BLACKLIST_AFTER_ROTATION': True,
#     'AUTH_HEADER_TYPES': ('Bearer',),
# }

# # Redis configuration
# REDIS_HOST = env('REDIS_HOST', default='localhost')
# REDIS_PORT = env.int('REDIS_PORT', default=6379)
# REDIS_DB = env.int('REDIS_DB', default=0)
# REDIS_PASSWORD = env('REDIS_PASSWORD', default=None)

# # Build Redis URL
# if REDIS_PASSWORD:
#     REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
# else:
#     REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


# # Cache configuration
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': REDIS_URL,
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         }
#     }
# }

# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [os.path.join(BASE_DIR, 'templates')],#api/admin_panel/
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.debug',
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#             'debug': True,
#         },
#     },
# ]

# # Rate Limit Settings
# RATE_LIMIT_SETTINGS = {
#     'ENABLE_RATE_LIMIT': True,
#     'DEFAULT_LIMITS': {
#         'anonymous': '100/hour',
#         'authenticated': '1000/hour',
#         'premium': '5000/hour',
#     },
#     'EXCLUDE_PATHS': [
#         '/admin/',
#         '/static/',
#         '/media/',
#         '/health/',
#         '/api/rate-limit/health/',
#     ],
#     'EXCLUDE_METHODS': ['OPTIONS'],
#     'STORAGE_BACKEND': 'redis',
#     'REDIS_PREFIX': 'rate_limit',
#     'ENABLE_LOGGING': True,
#     'LOG_RETENTION_DAYS': 30,
# }

# # Earning app specific rate limits
# EARNING_RATE_LIMITS = {
#     'TASK_DAILY_LIMIT': 10,
#     'TASK_DAILY_LIMIT_PREMIUM': 50,
#     'OFFER_HOURLY_LIMIT': 20,
#     'REFERRAL_DAILY_LIMIT': 50,
#     'WITHDRAWAL_DAILY_LIMIT': 3,
#     'MINIMUM_TASK_INTERVAL': 30,
# }

# # Cache timeouts
# CACHE_TIMEOUTS = {
#     'USER_PROFILE': 300,  
#     'USER_STATS': 60,     
#     'TASK_LIST': 30,      
#     'OFFER_LIST': 60,     
#     'LEADERBOARD': 300,   
# }



# # VPN Detection API Keys (Optional - Free tiers available)
# PROXYCHECK_API_KEY = 'your_key_here'  # Optional
# IPQUALITYSCORE_API_KEY = 'your_key_here'  # Optional
# VPNAPI_KEY = 'your_key_here'  # Optional


# # settings.py
# # Fraud Detection Settings
# FRAUD_CHECK_ENABLED = True
# BOT_DETECTION_ENABLED = True
# ALLOW_DUPLICATE_CONVERSIONS = False
# MAX_CONVERSIONS_PER_HOUR = 15

# # Third-party IP Reputation Service
# IP_REPUTATION_SERVICE = 'ipqualityscore'  # Options: 'ipqualityscore', 'maxmind', 'abuseipdb'
# IP_REPUTATION_API_KEY = 'your_api_key_here'  # Get from service provider
# IP_REPUTATION_CACHE_TIME = 3600  # 1 hour in seconds

# # Timing Check Settings
# STRICT_TIMING_CHECK_SECONDS = 3  # Strict check for 0-3 seconds
# RELAXED_TIMING_CHECK_SECONDS = 10  # Relaxed check for 3-10 seconds



# # settings.py
# CELERY_BEAT_SCHEDULE = {
#     # Blacklist Maintenance (3:00 AM daily)
#     'cleanup-expired-blacklist-daily': {
#         'task': 'api.tasks.cleanup_expired_blacklist_task',
#         'schedule': crontab(hour=3, minute=0),
#         'args': (1000,),
#         'options': {
#             'queue': 'maintenance',
#             'priority': 5,
#         }
#     },
    
#     # Pattern Analysis (4:00 AM daily)
#     'analyze-blacklist-patterns-daily': {
#         'task': 'api.tasks.analyze_blacklist_patterns_task',
#         'schedule': crontab(hour=4, minute=0),
#         'args': (),
#         'options': {
#             'queue': 'maintenance',
#             'priority': 4,
#         }
#     },
    
#     # Weekly Report (Monday 9:00 AM)
#     'send-weekly-blacklist-report': {
#         'task': 'api.tasks.send_weekly_blacklist_report_task',
#         'schedule': crontab(hour=9, minute=0, day_of_week=1),
#         'args': (),
#         'options': {
#             'queue': 'reports',
#             'priority': 3,
#         }
#     },
    
#     # Fraud Analytics Dashboard (Every 6 hours)
#     'generate-fraud-analytics-dashboard': {
#         'task': 'api.tasks.generate_fraud_analytics_dashboard_task',
#         'schedule': crontab(hour='*/6', minute=0),
#         'args': (),
#         'options': {
#             'queue': 'reports',
#             'priority': 4,
#         }
#     },
    
#     # Cache Warmup (Every 6 hours)
#     'warmup-blacklist-cache': {
#         'task': 'api.tasks.warmup_blacklist_cache_task',
#         'schedule': crontab(hour='*/6', minute=30),
#         'args': (2000,),
#         'options': {
#             'queue': 'cache',
#             'priority': 4,
#         }
#     },
    
#     # External IP Reputation Sync (4:30 AM daily)
#     'sync-external-ip-reputation': {
#         'task': 'api.tasks.sync_external_ip_reputation_task',
#         'schedule': crontab(hour=4, minute=30),
#         'args': (),
#         'options': {
#             'queue': 'data_sync',
#             'priority': 4,
#         }
#     },
    
#     # Suspicious Activity Monitoring (Every hour)
#     'monitor-suspicious-activity': {
#         'task': 'api.tasks.monitor_suspicious_activity_task',
#         'schedule': crontab(minute=0),
#         'args': (),
#         'options': {
#             'queue': 'monitoring',
#             'priority': 6,
#         }
#     },
    
#     # Task Health Check (Every 30 minutes)
#     'check-task-health': {
#         'task': 'api.tasks.check_task_health_task',
#         'schedule': crontab(minute='*/30'),
#         'args': (),
#         'options': {
#             'queue': 'monitoring',
#             'priority': 7,
#         }
#     },
    
#     # Stale Cache Cleanup (Every hour at :15)
#     'cleanup-stale-cache': {
#         'task': 'api.tasks.cleanup_stale_cache_task',
#         'schedule': crontab(minute=15),
#         'args': (),
#         'options': {
#             'queue': 'cache',
#             'priority': 3,
#         }
#     },
# }




# # settings.py-তে যোগ করুন:
# # Telegram Bot Configuration (ঐচ্ছিক)
# TELEGRAM_BOT_TOKEN = 'your_bot_token_here'

# # SMS Configuration (ঐচ্ছিক)
# TWILIO_ACCOUNT_SID = 'your_account_sid'
# TWILIO_AUTH_TOKEN = 'your_auth_token'
# TWILIO_PHONE_NUMBER = '+1234567890'

# # Site Configuration
# SITE_NAME = 'Your Site Name'
# SITE_URL = 'https://yourdomain.com'
# DEFAULT_FROM_EMAIL = 'alerts@yourdomain.com'

# # Redis Configuration (ঐচ্ছিক)
# REDIS_URL = 'redis://localhost:6379/0'


# CMS_PERMISSIONS = {
#     'can_manage_content': 'cms.manage_content',
#     'can_manage_banners': 'cms.manage_banners',
#     'can_manage_faqs': 'cms.manage_faqs',
#     'can_manage_settings': 'cms.manage_settings',
# }



# # ============ CELERY CONFIGURATION ============
# CELERY_BROKER_URL = 'redis://localhost:6379/0'  # Redis URL
# CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
# CELERY_ACCEPT_CONTENT = ['application/json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_RESULT_SERIALIZER = 'json'
# CELERY_TIMEZONE = 'Asia/Dhaka'  # Bangladesh timezone
# CELERY_ENABLE_UTC = False

# # Celery Beat Configuration
# CELERY_BEAT_SCHEDULE = {
#     # Alert Processing Tasks
#     'process-pending-alerts-every-5-minutes': {
#         'task': 'alerts.tasks.process_pending_alerts',
#         'schedule': 300.0,  # 5 minutes = 300 seconds
#         'options': {'queue': 'alerts'}
#     },
#     'send-notifications-every-1-minute': {
#         'task': 'alerts.tasks.send_notifications',
#         'schedule': 60.0,  # 1 minute
#         'options': {'queue': 'notifications'}
#     },
#     'escalate-alerts-every-30-minutes': {
#         'task': 'alerts.tasks.escalate_alerts',
#         'schedule': 1800.0,  # 30 minutes
#         'options': {'queue': 'alerts'}
#     },
    
#     # System Health Tasks
#     'check-system-health-every-5-minutes': {
#         'task': 'alerts.tasks.check_system_health',
#         'schedule': 300.0,  # 5 minutes
#         'options': {'queue': 'health'}
#     },
    
#     # Analytics Tasks
#     'generate-daily-analytics-at-midnight': {
#         'task': 'alerts.tasks.generate_daily_analytics',
#         'schedule': 86400.0,  # 24 hours
#         'options': {'queue': 'analytics'}
#     },
    
#     # Group Alerts Tasks
#     'send-group-alerts-every-10-minutes': {
#         'task': 'alerts.tasks.send_group_alerts',
#         'schedule': 600.0,  # 10 minutes
#         'options': {'queue': 'alerts'}
#     },
    
#     # Maintenance Tasks
#     'cleanup-old-data-daily': {
#         'task': 'alerts.tasks.cleanup_old_data',
#         'schedule': 86400.0,  # 24 hours
#         'options': {'queue': 'maintenance'}
#     },
#     'update-alert-group-caches-every-hour': {
#         'task': 'alerts.tasks.update_alert_group_caches',
#         'schedule': 3600.0,  # 1 hour
#         'options': {'queue': 'maintenance'}
#     },
#     'expire-suppressions-every-hour': {
#         'task': 'alerts.tasks.expire_suppressions',
#         'schedule': 3600.0,  # 1 hour
#         'options': {'queue': 'maintenance'}
#     },
    
#     # Real-time Updates Tasks
#     'check-for-real-time-updates-every-30-seconds': {
#         'task': 'alerts.tasks.check_real_time_updates',
#         'schedule': 30.0,  # 30 seconds
#         'options': {'queue': 'realtime'}
#     },
# }

# # Task Queues Configuration
# CELERY_TASK_ROUTES = {
#     'alerts.tasks.process_pending_alerts': {'queue': 'alerts'},
#     'alerts.tasks.send_notifications': {'queue': 'notifications'},
#     'alerts.tasks.escalate_alerts': {'queue': 'alerts'},
#     'alerts.tasks.check_system_health': {'queue': 'health'},
#     'alerts.tasks.generate_daily_analytics': {'queue': 'analytics'},
#     'alerts.tasks.send_group_alerts': {'queue': 'alerts'},
#     'alerts.tasks.cleanup_old_data': {'queue': 'maintenance'},
#     'alerts.tasks.update_alert_group_caches': {'queue': 'maintenance'},
#     'alerts.tasks.expire_suppressions': {'queue': 'maintenance'},
#     'alerts.tasks.check_real_time_updates': {'queue': 'realtime'},
# }

# # Celery Task Settings
# CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
# CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
# CELERY_TASK_ACKS_LATE = True
# CELERY_TASK_TRACK_STARTED = True
# CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# CELERY_WORKER_CONCURRENCY = 4

# # Custom admin settings
# ADMIN_SITE_HEADER = "CMS Admin Panel"
# ADMIN_SITE_TITLE = "Content Management System"
# ADMIN_INDEX_TITLE = "Welcome to CMS Administration"


# SITE_ID = 1  # Django sites framework-এর জন্য




# # settings.py

# # bKash Configuration
# BKASH_APP_KEY = 'your_bkash_app_key'
# BKASH_APP_SECRET = 'your_bkash_app_secret'
# BKASH_USERNAME = 'your_bkash_username'
# BKASH_PASSWORD = 'your_bkash_password'
# BKASH_WEBHOOK_SECRET = 'your_bkash_webhook_secret'
# BKASH_BASE_URL = 'https://checkout.pay.bka.sh/v1.2.0-beta'  # Sandbox
# # BKASH_BASE_URL = 'https://checkout.pay.bka.sh/v1.2.0-beta'  # Production

# # Stripe Configuration
# STRIPE_SECRET_KEY = 'sk_test_...'  # or sk_live_...
# STRIPE_PUBLISHABLE_KEY = 'pk_test_...'  # or pk_live_...
# STRIPE_WEBHOOK_SECRET = 'whsec_...'

# # Nagad Configuration
# NAGAD_MERCHANT_ID = 'your_merchant_id'
# NAGAD_MERCHANT_NUMBER = 'your_merchant_number'
# NAGAD_PUBLIC_KEY = 'your_public_key'
# NAGAD_PRIVATE_KEY = 'your_private_key'
# NAGAD_SECRET_KEY = 'your_secret_key'
# NAGAD_BASE_URL = 'http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api/dfs'  # Sandbox
# # NAGAD_BASE_URL = 'https://api.mynagad.com/api/dfs'  # Production

# # Webhook IP whitelisting (optional)
# WEBHOOK_ALLOWED_IPS = {
#     'bkash': ['103.108.140.0/24', '103.108.141.0/24'],
#     'stripe': ['3.18.12.0/22', '3.130.192.0/22', '3.19.124.0/22'],
#     'nagad': ['202.4.105.0/24'],  # Update with actual Nagad IPs
# }

# # Logging configuration
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'file': {
#             'level': 'INFO',
#             'class': 'logging.FileHandler',
#             'filename': 'logs/payment_webhooks.log',
#         },
#         'console': {
#             'class': 'logging.StreamHandler',
#         },
#     },
#     'loggers': {
#         'api.payment_gateways.webhooks': {
#             'handlers': ['file', 'console'],
#             'level': 'INFO',
#             'propagate': True,
#         },
#     },
# }

# SILENCED_SYSTEM_CHECKS = ["urls.W005"]



# # SECRET_KEY = 'নতুন random key'

# # SECURE_HSTS_SECONDS = 31536000
# # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# # SECURE_HSTS_PRELOAD = True

# # # SECURE_SSL_REDIRECT = True
# # SESSION_COOKIE_SECURE = True
# # CSRF_COOKIE_SECURE = True

# # CKEditor Upload Path (এরর ফিক্স করার জন্য এটি মাস্ট)
# CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/"

# # (ঐচ্ছিক) CKEditor কে আরও সুন্দর করার জন্য এই সেটিংস ব্যবহার করতে পারেন
# CKEDITOR_CONFIGS = {
#     'default': {
#         'toolbar': 'full',
#         'height': 300,
#         'width': '100%',
#     },
# }


# # Language settings
# LANGUAGE_COOKIE_NAME = 'django_language'
# LANGUAGE_COOKIE_AGE = 31536000  # 1 year
# LOG_MISSING_TRANSLATIONS = True

# # Rate limiting
# RATE_LIMIT_ENABLED = True
# RATE_LIMIT_REQUESTS = 100
# RATE_LIMIT_PERIOD = 60  # seconds

# # CORS settings
# CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'https://example.com']
# CORS_ALLOWED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

# # Maintenance mode
# MAINTENANCE_MODE = False
# MAINTENANCE_ALLOWED_IPS = ['127.0.0.1']
# MAINTENANCE_ALLOWED_PATHS = ['/admin/', '/api/health/', '/static/']

# # Performance monitoring
# SLOW_REQUEST_THRESHOLD = 1.0  # seconds

# # Compression
# COMPRESS_MIN_LENGTH = 500  # bytes

# SILENCED_SYSTEM_CHECKS = ['models.W001']


# # Channels configuration
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels.layers.InMemoryChannelLayer',  # টেস্টের জন্য
#     },
# }


# # Celery configuration for testing
# CELERY_TASK_ALWAYS_EAGER = True
# CELERY_TASK_EAGER_PROPAGATES = True
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

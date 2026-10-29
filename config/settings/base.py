import os
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

# ==================== BASE DIR ====================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ==================== ENV ====================
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ==================== INSTALLED APPS ====================
INSTALLED_APPS = [
    # Django core apps (MUST BE FIRST)
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "social_django",
    "drf_spectacular",
    "django.contrib.sites",
    # Third-party apps
    "ckeditor",
    "ckeditor_uploader",
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "admob_ssv",
    # ✅ ADDED: Django Channels — required for inventory WebSocket consumers
    # (consumers.py → InventoryWebSocketConsumer, EventStreamConsumer, RealTimeConsumer)
    "channels",
    # Core
    "core",
    # API Apps
    "api",
    "api.users.apps.UsersConfig",
    "api.security",
    "api.admin_panel",
    "api.payment_gateways",
    "api.tenants.apps.TenantsConfig",
    "api.ad_networks",
    "api.offerwall",
    "api.fraud_detection",
    "api.analytics",
    "api.referral",
    "api.engagement",
    "api.notifications",
    "api.cms",
    "api.support",
    "api.alerts",
    "api.djoyalty",
    "api.wallet.apps.WalletConfig",
    "api.kyc",
    "api.cache",
    "api.tasks",
    "api.rate_limit",
    "api.localization",
    "api.audit_logs",
    "api.tests",
    "api.backup",
    "api.promotions",
    "api.subscription.apps.SubscriptionConfig",
    "api.gamification.apps.GamificationConfig",
    "api.auto_mod.apps.AutoModConfig",
    "api.version_control.apps.VersionControlConfig",
    "api.behavior_analytics.apps.BehaviorAnalyticsConfig",
    "api.postback.apps.PostbackConfig",
    "api.inventory.apps.InventoryConfig",
    "api.messaging",
    "api.payout_queue.apps.PayoutQueueConfig",
    "api.webhooks.apps.WebhooksConfig",
    "api.marketplace",
    "api.postback_engine",
    "api.monetization_tools",
    "api.publisher_tools",
    "api.proxy_intelligence",
    "api.advertiser_portal",
    "api.offer_inventory",
    "api.smartlink",
    "api.disaster_recovery.apps.DisasterRecoveryConfig",
    "api.dr_integration",
    "api.ai_engine",
    "api.offer_routing",
    "api.feature_flags",
    "api.realtime_dashboard",
    "api.telemetry_observability.apps.TelemetryObservabilityConfig",
    
  
]

# ==================== MIDDLEWARE ====================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "api.dr_integration.middleware.DRAuditMiddleware",
    "api.users.security_middleware.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "api.admin_panel.endpoint_toggle.EndpointToggleMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.smartlink.middleware.SmartLinkRedirectMiddleware",
    "api.smartlink.middleware.SmartLinkPerformanceMiddleware",
    "api.fraud_detection.middleware.FraudDetectionMiddleware",
    "api.security.middleware.SecurityAuditMiddleware",
    "api.rate_limit.middleware.RateLimitMiddleware",
    "api.rate_limit.middleware.EarningTaskRateLimitMiddleware",
    "api.payment_gateways.middleware.WebhookSignatureMiddleware",
    "api.wallet.middleware.SafeIPMiddleware",
    "api.wallet.middleware.CircuitBreakerMiddleware",
    "api.tenants.middleware.TenantMiddleware",
    "api.wallet.middleware.DatabaseErrorMiddleware",
    "api.wallet.middleware.SecurityLogMiddleware",
    "api.wallet.middleware.RequestTimerMiddleware",
    "api.wallet.middleware.APIErrorMiddleware",
    "api.localization.middleware.ContentCompressionMiddleware",
    "api.localization.middleware.CORSMiddleware",
    "api.localization.middleware.RequestLoggingMiddleware",
    "api.localization.middleware.PerformanceMiddleware",
    "api.localization.middleware.RateLimitMiddleware",
    "api.localization.middleware.LanguageMiddleware",
    "api.localization.middleware.TimezoneMiddleware",
    "api.localization.middleware.CurrencyMiddleware",
    "api.localization.middleware.DeviceDetectionMiddleware",
    "api.localization.middleware.TranslationMiddleware",
    "api.localization.middleware.CacheHeadersMiddleware",
    "api.localization.middleware.SecurityHeadersMiddleware",
    "api.localization.middleware.MaintenanceModeMiddleware",
    "api.audit_logs.middleware.AuditLogMiddleware",
    "api.cache.middleware.RequestCacheMiddleware",
    "api.cache.middleware.PageCacheMiddleware",
    "api.cache.middleware.CacheControlMiddleware",
    "api.gamification.middleware.ActiveContestCycleMiddleware",
    "api.gamification.middleware.GamificationTrackingMiddleware",
    "api.gamification.middleware.GamificationSecurityMiddleware",
    'api.telemetry_observability.middleware.TelemetryMiddleware',
]

# ==================== URL / WSGI / ASGI ====================
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ✅ FIXED: was 'config.settings.asgi.application' (wrong path)
ASGI_APPLICATION = "config.asgi.application"

# ==================== DATABASE ====================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="earning_db"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default="12345"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "DISABLE_SERVER_SIDE_CURSORS": True,
        "CONN_MAX_AGE": 0,
        "TEST": {
            "NAME": env("TEST_DB_NAME", default="test_earning_db"),
        },
    }
}

# ==================== AUTH ====================
AUTH_USER_MODEL = "users.User"

# ✅ ADDED: Password validators (was completely missing)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ✅ ADDED: ADMINS — required by inventory._validate_configuration()
# Without this, every Django startup logs a warning and inventory health check fails.
ADMINS = [
    (env("ADMIN_NAME", default="Platform Admin"), env("ADMIN_EMAIL", default="")),
]

# ==================== INTERNATIONALIZATION ====================
# ✅ ADDED: Entire i18n block was missing
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ==================== REST FRAMEWORK ====================
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    # ✅ ADDED: Exception handler, pagination, filter backend
    "EXCEPTION_HANDLER": "api.realtime_dashboard.exceptions.custom_exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # ✅ ADDED: missing JWT fields
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# ==================== SOCIAL AUTH ====================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "api.users.google_backend.CustomGoogleOAuth2",
]
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", "")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET", ""
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ["email", "profile"]
SOCIAL_AUTH_URL_NAMESPACE = "social"

# ==================== REDIS ====================
import os as _os

REDIS_URL = _os.environ.get("REDIS_URL") or env("REDIS_URL", default=None)

if not REDIS_URL:
    REDIS_HOST = env("REDIS_HOST", default="localhost")
    REDIS_PORT = env.int("REDIS_PORT", default=6379)
    REDIS_DB = env.int("REDIS_DB", default=0)
    REDIS_PASSWORD = env("REDIS_PASSWORD", default=None)

    if REDIS_PASSWORD:
        REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    else:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# ==================== CACHE ====================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # ✅ ADDED: missing Redis connection options
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "IGNORE_EXCEPTIONS": True,  # Don't crash if Redis is down
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "earnify",
        "TIMEOUT": 300,  # default TTL: 5 minutes
    }
}

# ==================== CELERY ====================
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Dhaka"
CELERY_ENABLE_UTC = False
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TRACK_STARTED = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_CONCURRENCY = 4
# ── Gamification beat wiring — apps.py._wire_beat_schedule() uses this ───────
CELERY_APP = env("CELERY_APP", default="config.celery:app")


# ✅ ADDED: Missing Celery result expiry & broker transport options
CELERY_RESULT_EXPIRES = timedelta(days=7)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": 3600,
    "max_retries": 3,
}

CELERY_BEAT_SCHEDULE = {
    "process-pending-alerts-every-5-minutes": {
        "task": "alerts.tasks.process_pending_alerts",
        "schedule": 300.0,
        "options": {"queue": "alerts"},
    },
    "send-notifications-every-1-minute": {
        "task": "alerts.tasks.send_notifications",
        "schedule": 60.0,
        "options": {"queue": "notifications"},
    },
    "cleanup-old-data-daily": {
        "task": "alerts.tasks.cleanup_old_data",
        "schedule": 86400.0,
        "options": {"queue": "maintenance"},
    },
    "cleanup-expired-blacklist-daily": {
        "task": "api.tasks.cleanup_expired_blacklist_task",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "maintenance"},
    },
    "monitor-suspicious-activity": {
        "task": "api.tasks.monitor_suspicious_activity_task",
        "schedule": crontab(minute=0),
        "options": {"queue": "monitoring"},
    },
    "webhook-reap-exhausted-logs-hourly": {
        "task": "ainul.webhooks.reap_exhausted_logs",
        "schedule": crontab(minute=0),
        "options": {"queue": "webhooks_periodic"},
    },
    "webhook-auto-suspend-bad-endpoints-daily": {
        "task": "ainul.webhooks.auto_suspend_endpoints",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "webhooks_periodic"},
    },
}

CELERY_TASK_ROUTES = {
    "alerts.tasks.process_pending_alerts": {"queue": "alerts"},
    "alerts.tasks.send_notifications": {"queue": "notifications"},
    "alerts.tasks.cleanup_old_data": {"queue": "maintenance"},
    "ainul.webhooks.retry_failed_dispatch": {"queue": "webhooks"},
    "ainul.webhooks.dispatch_event": {"queue": "webhooks"},
    "ainul.webhooks.reap_exhausted_logs": {"queue": "webhooks_periodic"},
    "ainul.webhooks.auto_suspend_endpoints": {"queue": "webhooks_periodic"},
    # ✅ ADDED: DR task routes were defined but never routed
    "dr_integration.auto_backup": {"queue": "maintenance"},
    "dr_integration.sync_dr_status": {"queue": "monitoring"},
    "dr_integration.verify_recent_backups": {"queue": "maintenance"},
    "dr_integration.health_check": {"queue": "monitoring"},
    "dr_integration.collect_and_push_metrics": {"queue": "monitoring"},
}

# ==================== STATIC / MEDIA ====================
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

MAX_UPLOAD_SIZE = 5242880  # 5MB
ALLOWED_UPLOAD_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp"]

# ✅ ADDED: Django file upload limits (was completely missing)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB - in-memory threshold
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB - max POST body
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
FILE_UPLOAD_PERMISSIONS = 0o644

# ==================== TEMPLATES ====================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # ✅ ADDED: social_django context processors were missing
                # (required since social_django is in INSTALLED_APPS)
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                # ── Gamification context processor ────────────────────────
                "api.gamification.context_processors.active_contest_cycle",
            ],
        },
    },
]

# ==================== CKEDITOR ====================
CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/"
CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "full",
        "height": 300,
        "width": "100%",
    },
}

# ==================== CHANNELS ====================
# ✅ FIXED: InMemoryChannelLayer doesn't work across multiple workers/processes.
# Use Redis for production. Falls back to InMemory if REDIS_URL not set.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
        },
    }
}

# ==================== SESSIONS & COOKIES ====================
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ✅ ADDED: Session/cookie lifetime settings were missing
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days
CSRF_COOKIE_HTTPONLY = False  # JS needs to read CSRF token
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://earning-backend-c-production.up.railway.app",
    "https://earning-frontend-v2.vercel.app",
]

# ==================== SECURITY HEADERS ====================
# ✅ ADDED: Security headers block was completely missing
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Enable these in production (set via env to allow DEBUG override)
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS", default=0
)  # set to 31536000 in prod
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# ==================== PAYMENT GATEWAYS ====================
BKASH_APP_KEY = env("BKASH_APP_KEY", default="your_bkash_app_key")
BKASH_APP_SECRET = env("BKASH_APP_SECRET", default="your_bkash_app_secret")
BKASH_USERNAME = env("BKASH_USERNAME", default="your_bkash_username")
BKASH_PASSWORD = env("BKASH_PASSWORD", default="your_bkash_password")
BKASH_WEBHOOK_SECRET = env("BKASH_WEBHOOK_SECRET", default="your_bkash_webhook_secret")
BKASH_BASE_URL = env(
    "BKASH_BASE_URL", default="https://checkout.pay.bka.sh/v1.2.0-beta"
)

NAGAD_MERCHANT_ID = env("NAGAD_MERCHANT_ID", default="your_merchant_id")
NAGAD_MERCHANT_NUMBER = env("NAGAD_MERCHANT_NUMBER", default="your_merchant_number")
NAGAD_BASE_URL = env(
    "NAGAD_BASE_URL",
    default="http://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api/dfs",
)

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="sk_test_...")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="pk_test_...")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="whsec_...")

WEBHOOK_ALLOWED_IPS = {
    "bkash": ["103.108.140.0/24", "103.108.141.0/24"],
    "stripe": ["3.18.12.0/22", "3.130.192.0/22"],
    "nagad": ["202.4.105.0/24"],
}

# ==================== ADMOB SSV ====================
# ✅ ADDED: admob_ssv is in INSTALLED_APPS but had zero config
ADMOB_SSV_SECRET_KEYS = {
    # Add your AdMob SSV public key IDs here
    # 'key_id': 'public_key_pem_string',
}
ADMOB_SSV_REWARD_CALLBACK = env(
    "ADMOB_SSV_REWARD_CALLBACK", default="api.ad_networks.callbacks.admob_reward"
)

# ==================== VPN / FRAUD ====================
PROXYCHECK_API_KEY = env("PROXYCHECK_API_KEY", default="")
IPQUALITYSCORE_API_KEY = env("IPQUALITYSCORE_API_KEY", default="")
FRAUD_CHECK_ENABLED = True
BOT_DETECTION_ENABLED = True
ALLOW_DUPLICATE_CONVERSIONS = False
MAX_CONVERSIONS_PER_HOUR = 15
IP_REPUTATION_CACHE_TIME = 3600
STRICT_TIMING_CHECK_SECONDS = 3
RELAXED_TIMING_CHECK_SECONDS = 10
FRAUD_ENCRYPTION_KEY = env(
    "FRAUD_ENCRYPTION_KEY", default="fraudencryptkey12345678901234567"
)

# ==================== RATE LIMIT ====================
RATE_LIMIT_SETTINGS = {
    "ENABLE_RATE_LIMIT": True,
    "DEFAULT_LIMITS": {
        "anonymous": "100/hour",
        "authenticated": "1000/hour",
        "premium": "5000/hour",
    },
    "EXCLUDE_PATHS": ["/admin/", "/static/", "/media/", "/health/"],
    "EXCLUDE_METHODS": ["OPTIONS"],
    "STORAGE_BACKEND": "redis",
    "REDIS_PREFIX": "rate_limit",
    "ENABLE_LOGGING": True,
    "LOG_RETENTION_DAYS": 30,
}

EARNING_RATE_LIMITS = {
    "TASK_DAILY_LIMIT": 10,
    "TASK_DAILY_LIMIT_PREMIUM": 50,
    "OFFER_HOURLY_LIMIT": 20,
    "REFERRAL_DAILY_LIMIT": 50,
    "WITHDRAWAL_DAILY_LIMIT": 3,
    "MINIMUM_TASK_INTERVAL": 30,
}

RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 60

# ==================== CACHE TIMEOUTS ====================
CACHE_TIMEOUTS = {
    "USER_PROFILE": 300,
    "USER_STATS": 60,
    "TASK_LIST": 30,
    "OFFER_LIST": 60,
    "LEADERBOARD": 300,
}

# ==================== CORS ====================
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://192.168.0.178:8080",
    ],
)
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",
]

# ==================== MISC ====================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1
SITE_NAME = env("SITE_NAME", default="Earning App")
SITE_URL = env("SITE_URL", default="https://yourdomain.com")
APPEND_SLASH = True

# ==================== EMAIL ====================
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="alerts@yourdomain.com")

# ==================== EXTERNAL SERVICES ====================
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_PHONE_NUMBER = env("TWILIO_PHONE_NUMBER", default="")

# ==================== CMS ====================
CMS_PERMISSIONS = {
    "can_manage_content": "cms.manage_content",
    "can_manage_banners": "cms.manage_banners",
    "can_manage_faqs": "cms.manage_faqs",
    "can_manage_settings": "cms.manage_settings",
}

# ==================== ADMIN ====================
ADMIN_SITE_HEADER = "Earning App Admin"
ADMIN_SITE_TITLE = "Admin Panel"
ADMIN_INDEX_TITLE = "Welcome to Admin"

# ==================== LOCALIZATION MISC ====================
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 31536000
MAINTENANCE_MODE = False
MAINTENANCE_ALLOWED_IPS = ["127.0.0.1"]
SLOW_REQUEST_THRESHOLD = 1.0

# ==================== SILENCED CHECKS ====================
SILENCED_SYSTEM_CHECKS = ["models.W001", "ckeditor.W001"]

# ==================== LOGGING ====================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "logs/debug.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "wallet": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "api.payment_gateways": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        # ✅ ADDED: cache & celery loggers were missing
        "api.cache": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # ✅ ADDED: inventory logger — surfaces apps.py ready() errors,
        # signal connection failures, and INTEGRATION_SYSTEM bootstrap logs
        "api.inventory": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "inventory": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

LOGIN_URL = "/api/auth/login/"

# ==================== SOCIAL AUTH (full config) ====================
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)

SOCIAL_AUTH_LOGIN_REDIRECT_URL = "https://earning-frontend-v2.vercel.app/dashboard"
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = "https://earning-frontend-v2.vercel.app/dashboard"
SOCIAL_AUTH_LOGIN_ERROR_URL = "https://earning-frontend-v2.vercel.app/login"

SOCIAL_AUTH_FIELDS_STORED_IN_SESSION = ["state"]
SOCIAL_AUTH_GOOGLE_OAUTH2_IGNORE_DEFAULT_SCOPE = False
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = "https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/"
SOCIAL_AUTH_GOOGLE_OAUTH2_BACKEND_CLASS = "api.users.google_backend.CustomGoogleOAuth2"
SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {"prompt": "select_account"}

# ==================== DRF SPECTACULAR ====================
SPECTACULAR_SETTINGS = {
    "TITLE": "Earning Platform API",
    "DESCRIPTION": "API documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "POSTPROCESSING_HOOKS": [],
    "DISABLE_ERRORS_AND_WARNINGS": True,
    "IGNORE_SCHEMA_GENERATION_ERRORS": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_GENERATE_CHOICE_DESCRIPTION": False,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
    },
    # ✅ ADDED: JWT auth in Swagger UI was missing
    "SECURITY": [{"BearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

# ==================== TENANT ====================
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Tenant"

# ==================== MIGRATION MODULES ====================
MIGRATION_MODULES = {
    "advertiser_portal": "api.advertiser_portal.django_migrations",
    "ai_engine": "api.ai_engine.django_migrations",
    "marketplace": "api.marketplace.django_migrations",
    # ✅ FIXED: 'authtoken' key is wrong — it must match the app label exactly
    # rest_framework.authtoken uses label 'authtoken', so this is correct:
    "authtoken": "api.authtoken_migrations",
}

# ==================== DISASTER RECOVERY ====================
DR_SYSTEM_PATH = os.environ.get("DR_SYSTEM_PATH", "/app/disaster_recovery")

DR_NOTIFICATION_CONFIG = {
    "slack_webhook_url": os.environ.get("DR_SLACK_WEBHOOK_URL", ""),
    "pagerduty_api_key": os.environ.get("DR_PAGERDUTY_API_KEY", ""),
    "pagerduty_integration_key": os.environ.get("DR_PAGERDUTY_INTEGRATION_KEY", ""),
    "datadog_api_key": os.environ.get("DR_DATADOG_API_KEY", ""),
}

DR_LOCAL_BACKUP_PATH = os.environ.get("DR_LOCAL_BACKUP_PATH", "/var/backups/api")
DR_BACKUP_BACKENDS = ["local", "s3"]

DR_STORAGE_CONFIGS = [
    {"name": "local", "provider": "local", "base_path": DR_LOCAL_BACKUP_PATH},
    {
        "name": "s3-backups",
        "provider": "aws_s3",
        "bucket": os.environ.get("BACKUP_S3_BUCKET", ""),
        "region": os.environ.get("AWS_REGION", "us-east-1"),
        "access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
    },
]

DR_AUDIT_CONFIG = {
    "log_file": "/var/log/api/dr_audit.jsonl",
    "security_log_file": "/var/log/api/dr_security_audit.jsonl",
}

DR_HEALTH_CHECK_COMPONENTS = [
    {"name": "database", "type": "database", "url": os.environ.get("DATABASE_URL", "")},
    {"name": "redis", "type": "tcp", "host": "localhost", "port": 6379},
    {"name": "api", "type": "http", "url": "http://localhost:8000/health/"},
]

DR_STATUS_PAGE_COMPONENTS = [
    {"name": "api", "display_name": "API Server", "group": "Application"},
    {"name": "database", "display_name": "Database", "group": "Infrastructure"},
    {"name": "offerwall", "display_name": "Offerwall", "group": "Application"},
    {"name": "payment_gateway", "display_name": "Payment Gateway", "group": "External"},
    {"name": "marketplace", "display_name": "Marketplace", "group": "Application"},
    {"name": "ai_engine", "display_name": "AI Engine", "group": "Application"},
]

DR_KEY_CONFIG = {
    "key_store_path": "/etc/api/dr_keys",
    "rotation_days": 90,
}

DR_ON_CALL_ROSTER = [
    {
        "name": os.environ.get("ON_CALL_PRIMARY_NAME", "Primary On-Call"),
        "email": os.environ.get("ON_CALL_PRIMARY_EMAIL", ""),
        "slack_id": os.environ.get("ON_CALL_PRIMARY_SLACK", ""),
    }
]

# ✅ FIXED: DR Celery Beat tasks were defined but never merged into CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE.update(
    {
        "dr-incremental-backup-4h": {
            "task": "dr_integration.auto_backup",
            "schedule": 4 * 60 * 60,
            "kwargs": {"backup_type": "incremental"},
        },
        "dr-full-backup-weekly": {
            "task": "dr_integration.auto_backup",
            "schedule": 7 * 24 * 60 * 60,
            "kwargs": {"backup_type": "full"},
        },
        "dr-sync-status-5m": {
            "task": "dr_integration.sync_dr_status",
            "schedule": 5 * 60,
        },
        "dr-verify-backups-daily": {
            "task": "dr_integration.verify_recent_backups",
            "schedule": 24 * 60 * 60,
        },
        "dr-health-check-2m": {
            "task": "dr_integration.health_check",
            "schedule": 2 * 60,
        },
        "dr-collect-metrics-1m": {
            "task": "dr_integration.collect_and_push_metrics",
            "schedule": 60,
        },
    }
)

# ==================== GDAL / GEOS ====================
import sys as _sys
if _sys.platform == 'win32':
    _OSGEO = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\venv\Lib\site-packages\osgeo'
    GDAL_LIBRARY_PATH = _OSGEO + r'\gdal.dll'
    GEOS_LIBRARY_PATH = _OSGEO + r'\geos_c.dll'
    import os as _os
    _os.environ['PATH'] = _OSGEO + ';' + _os.environ.get('PATH', '')
# ✅ FIXED: Cross-platform safe — Windows local dev only, no-op on Linux/Railway
import platform as _platform

if _platform.system() == "Windows":
    _gdal = os.environ.get("GDAL_LIBRARY_PATH", "")
    _geos = os.environ.get("GEOS_LIBRARY_PATH", "")
    if _gdal and os.path.exists(_gdal):
        GDAL_LIBRARY_PATH = _gdal
    if _geos and os.path.exists(_geos):
        GEOS_LIBRARY_PATH = _geos
# On Linux (Railway/Docker): Django auto-detects GDAL/GEOS — no config needed

# ==================== UUID / JSON FIX ====================
try:
    import json
    import uuid
    from datetime import date, datetime
    from decimal import Decimal

    import psycopg2.extensions
    import psycopg2.extras

    class GlobalSafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            if hasattr(obj, "pk"):
                return obj.pk
            return str(obj)

    psycopg2.extensions.register_adapter(
        dict,
        lambda d: psycopg2.extras.Json(
            d, dumps=lambda o: json.dumps(o, cls=GlobalSafeEncoder)
        ),
    )
except Exception:
    pass

# ==================== LOCALIZATION SETTINGS ====================
TRANSLATION_PROVIDERS = {
    "deepl": {"enabled": False, "priority": 1, "api_key": ""},
    "google": {"enabled": False, "priority": 2, "api_key": "", "project_id": ""},
    "azure": {"enabled": False, "priority": 3, "api_key": "", "region": "eastus"},
    "amazon": {
        "enabled": False,
        "priority": 4,
        "api_key": "",
        "access_key": "",
        "region": "us-east-1",
    },
    "openai": {
        "enabled": False,
        "priority": 5,
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
    },
}

MAXMIND_LICENSE_KEY = ""
GEOIP_PATH = "/var/lib/localization/GeoLite2-City.mmdb"
LOCALIZATION_DETECT_FROM_IP = True
LOCALIZATION_ALERT_EMAIL = True
LOG_MISSING_TRANSLATIONS = True
USER_PREF_CACHE_TTL = 3600
API_CACHE_TIMEOUT = 3600
CACHE_24_HOURS = 86400
MAX_TRANSLATION_TEXT_LENGTH = 5000
LANGUAGE_PACK_CDN_URL = "/api/localization/public/translations"
LOCALIZATION_API_KEYS = []
LOCALIZATION_RATE_LIMITS = {
    "translate": "100/hour",
    "public_translations": "1000/hour",
    "currency_convert": "500/hour",
    "geoip": "200/hour",
}

CELERY_BEAT_SCHEDULE.update(
    {
        "update-exchange-rates": {
            "task": "api.localization.tasks.exchange_rate_tasks.update_rates",
            "schedule": crontab(minute=0),
            "options": {"expires": 3500},
        },
        "clean-translation-cache": {
            "task": "api.localization.tasks.translation_cache_tasks.clean_expired_cache",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "rebuild-popular-cache": {
            "task": "api.localization.tasks.translation_cache_tasks.rebuild_popular_cache",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "auto-translate-missing": {
            "task": "api.localization.tasks.auto_translation_tasks.auto_translate_missing",
            "schedule": crontab(minute=0, hour=2),
            "kwargs": {"limit": 200},
        },
        "translation-qa-check": {
            "task": "api.localization.tasks.translation_qa_tasks.run_qa_check",
            "schedule": crontab(minute=0, hour=3),
        },
        "update-coverage": {
            "task": "api.localization.tasks.coverage_report_tasks.update_coverage",
            "schedule": crontab(minute=0, hour=4),
        },
        "alert-missing-translations": {
            "task": "api.localization.tasks.missing_translation_tasks.alert_missing_translations",
            "schedule": crontab(minute=0, hour="*/2"),
        },
        "aggregate-daily-insights": {
            "task": "api.localization.tasks.insight_tasks.aggregate_daily_insights",
            "schedule": crontab(minute=0, hour=0),
        },
        "cleanup-localization": {
            "task": "api.localization.tasks.cleanup_tasks.cleanup_all",
            "schedule": crontab(minute=0, hour=5, day_of_week=0),
        },
        "update-geoip-db": {
            "task": "api.localization.tasks.geoip_update_tasks.update_geoip_db",
            "schedule": crontab(minute=0, hour=6, day_of_week=0),
        },
        "check-provider-health": {
            "task": "api.localization.tasks.provider_health_tasks.check_provider_health",
            "schedule": crontab(minute="*/30"),
        },
        "index-translation-memory": {
            "task": "api.localization.tasks.translation_memory_tasks.index_approved_translations",
            "schedule": crontab(minute=0, hour=7, day_of_week=1),
        },
        "build-language-packs": {
            "task": "api.localization.tasks.language_pack_tasks.build_all_packs",
            "schedule": crontab(minute=0, hour=5),
        },
    }
)

# ==================== CACHE SYSTEM CELERY TASKS ====================
# ✅ ADDED: api/cache/ module tasks — warming, monitoring, analytics, cleanup
CELERY_BEAT_SCHEDULE.update(
    {
        "cache-warm-all-4min": {
            "task": "cache.warm_all",
            "schedule": 240,  # every 4 min (before TTLs expire)
            "options": {"queue": "cache"},
        },
        "cache-warm-priority-on-start": {
            "task": "cache.warm_priority",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6h refresh
            "kwargs": {"max_priority": 1},
            "options": {"queue": "cache"},
        },
        "cache-health-check-1min": {
            "task": "cache.health_check",
            "schedule": 60,
            "options": {"queue": "monitoring"},
        },
        "cache-analytics-report-hourly": {
            "task": "cache.analytics_report",
            "schedule": crontab(minute=5),  # every hour at :05
            "kwargs": {"window_minutes": 60},
            "options": {"queue": "monitoring"},
        },
        "cache-cleanup-daily": {
            "task": "cache.cleanup_expired",
            "schedule": crontab(hour=3, minute=30),  # 3:30 AM daily
            "options": {"queue": "maintenance"},
        },
    }
)

# ✅ ADDED: cache task routes
CELERY_TASK_ROUTES.update(
    {
        "cache.warm_all": {"queue": "cache"},
        "cache.warm_priority": {"queue": "cache"},
        "cache.warm_namespace": {"queue": "cache"},
        "cache.health_check": {"queue": "monitoring"},
        "cache.analytics_report": {"queue": "monitoring"},
        "cache.cleanup_expired": {"queue": "maintenance"},
        "cache.flush_namespace": {"queue": "cache"},
    }
)

# ==================== CACHE MODULE CONFIG ====================
# ✅ ADDED: configuration for the new api/cache/ sub-modules

# Cache Analytics
CACHE_ANALYTICS_MAX_EVENTS = 50_000  # in-memory event buffer
CACHE_ANALYTICS_USE_REDIS = True  # persist counters to Redis

# Cache Warming
CACHE_WARMING_MAX_WORKERS = 6  # parallel warming threads
CACHE_WARMING_ENABLED = True
CACHE_WARMING_ON_STARTUP = True  # warm priority=1 keys on runserver

# Cache Monitoring SLA thresholds
CACHE_MONITOR_THRESHOLDS = {
    "min_hit_rate": 0.70,  # alert if hit rate < 70%
    "max_latency_ms": 10.0,  # alert if ping > 10ms
    "max_memory_mb": 450.0,  # alert if Redis memory > 450MB
    "max_eviction_rate": 100,  # alert if >100 evictions/min
}
CACHE_MONITOR_POLL_INTERVAL = 30  # seconds between health checks
CACHE_MONITOR_SLACK_WEBHOOK = env("CACHE_MONITOR_SLACK_WEBHOOK", default="")

# Cache A/B Testing
CACHE_AB_TESTING_ENABLED = True
CACHE_AB_DEFAULT_SPLIT = 0.5  # 50/50 traffic split

# Multi-Region Cache (leave empty for single-region deployments)
MULTI_REGION_CACHE = [
    # Example — uncomment and fill in when scaling globally:
    # {
    #     'region': 'bd-dhaka',
    #     'redis_url': env('REDIS_URL_BD', default=REDIS_URL),
    #     'priority': 1,
    #     'is_primary': True,
    #     'ip_ranges': ['103.0.0.0/8', '103.108.0.0/16'],
    # },
    # {
    #     'region': 'sg-singapore',
    #     'redis_url': env('REDIS_URL_SG', default=''),
    #     'priority': 2,
    #     'is_primary': False,
    #     'ip_ranges': ['128.199.0.0/16', '188.166.0.0/16'],
    # },
]

# ==================== CACHE URL ROUTING ====================
# In config/urls.py add:
#   path('api/cache/', include('api.cache.urls')),

# ==================== VERSION CONTROL CELERY TASKS ====================
# ✅ ADDED: api.version_control tasks (was completely missing from schedule)
CELERY_BEAT_SCHEDULE.update(
    {
        "vc-dora-daily-snapshot": {
            "task": "version_control.tasks.take_dora_snapshot",
            "schedule": crontab(hour=0, minute=30),
            "options": {"queue": "maintenance"},
        },
        "vc-slo-burn-rate-hourly": {
            "task": "version_control.tasks.evaluate_slo_burn_rates",
            "schedule": crontab(minute=0),
            "options": {"queue": "monitoring"},
        },
        "vc-webhook-retries-1min": {
            "task": "version_control.tasks.process_webhook_retries",
            "schedule": 60,
            "options": {"queue": "webhooks"},
        },
        "vc-gitops-drift-5min": {
            "task": "version_control.tasks.detect_gitops_drift",
            "schedule": 300,
            "options": {"queue": "monitoring"},
        },
        "vc-audit-cleanup-weekly": {
            "task": "version_control.tasks.cleanup_old_audit_logs",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),
            "options": {"queue": "maintenance"},
        },
        "vc-aggregate-metrics-daily": {
            "task": "version_control.tasks.aggregate_usage_metrics",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": "maintenance"},
        },
        "vc-subscription-renewals-daily": {
            "task": "version_control.tasks.process_subscription_renewals",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "maintenance"},
        },
        "vc-trial-expirations-daily": {
            "task": "version_control.tasks.check_trial_expirations",
            "schedule": crontab(hour=7, minute=0),
            "options": {"queue": "maintenance"},
        },
    }
)

# ✅ ADDED: version_control task routes
CELERY_TASK_ROUTES.update(
    {
        "version_control.tasks.take_dora_snapshot": {"queue": "maintenance"},
        "version_control.tasks.evaluate_slo_burn_rates": {"queue": "monitoring"},
        "version_control.tasks.process_webhook_retries": {"queue": "webhooks"},
        "version_control.tasks.detect_gitops_drift": {"queue": "monitoring"},
        "version_control.tasks.cleanup_old_audit_logs": {"queue": "maintenance"},
        "version_control.tasks.aggregate_usage_metrics": {"queue": "maintenance"},
        "version_control.tasks.process_subscription_renewals": {"queue": "maintenance"},
        "version_control.tasks.check_trial_expirations": {"queue": "maintenance"},
    }
)

# ─── FIX 5: version_control SILENCED_SYSTEM_CHECKS already ok ─────────────
# তোমার settings.py তে already আছে:
# SILENCED_SYSTEM_CHECKS = ['urls.W005', 'models.W001']
# এটাই version_control এর namespace warning চুপ করাবে। ✓


# ─── FIX 6: version_control test settings — production conflict নেই ────────
# version_control/settings.py (SQLite) শুধু test runner use করে।
# Main project settings (PostgreSQL) আলাদা।
# Test চালাতে:
#   cd your_project/
#   python manage.py test api.version_control.tests \
#     --settings=api.version_control.settings
# অথবা pytest.ini তে:
#   [pytest]
#   DJANGO_SETTINGS_MODULE = api.version_control.settings


# ==================== INVENTORY ====================
# ✅ ADDED: সম্পূর্ণ inventory settings block।
# apps.py._validate_configuration() এই keys গুলো read করে —
# না থাকলে startup-এ WARNING লগ হয় এবং কিছু feature silently disabled হয়।

# ── Core feature switches ─────────────────────────────────────────────────────
INVENTORY_ENABLE_SIGNALS = True
INVENTORY_ENABLE_CELERY_TASKS = True
INVENTORY_ENABLE_INTEGRITY_CHECKS = True  # SHA-256 hash on every save
INVENTORY_ENABLE_PARTNER_SYNC = True
INVENTORY_ENABLE_ALERT_NOTIFICATIONS = True
INVENTORY_ENABLE_REAL_TIME_ALERTS = True

# ── Integration system ────────────────────────────────────────────────────────
# Controls INTEGRATION_SYSTEM/ package bootstrap in apps.py._initialize_integration_system()
INVENTORY_ENABLE_INTEGRATION_SYSTEM = True
INVENTORY_INTEGRATION_CIRCUIT_BREAKER_ENABLED = True  # wrap external calls
INVENTORY_INTEGRATION_FALLBACK_ENABLED = True  # fallback on failure
INVENTORY_INTEGRATION_MAX_RETRIES = 3
INVENTORY_INTEGRATION_TIMEOUT = 30  # seconds

# ── WebSocket / real-time consumers ──────────────────────────────────────────
# Controls apps.py._initialize_real_time_consumers()
# Requires 'channels' in INSTALLED_APPS (already added above) and
# CHANNEL_LAYERS pointing to Redis (already configured above).
INVENTORY_ENABLE_WEBSOCKET_CONSUMERS = True
INVENTORY_ENABLE_EVENT_STREAM = True
INVENTORY_ENABLE_MESSAGE_QUEUE_CONSUMER = True

# ── Capability signal system ─────────────────────────────────────────────────
# Controls apps.py._connect_capability_signals()
INVENTORY_ENABLE_CAPABILITY_SIGNALS = True
INVENTORY_CAPABILITY_SIGNAL_AUDIT = True  # AuditInterceptor
INVENTORY_CAPABILITY_SIGNAL_METRICS = True  # MetricsProcessor

# ── Pagination ────────────────────────────────────────────────────────────────
# Used by apps.py._validate_configuration() and viewsets.
# If absent, each viewset falls back to its own hardcoded default (20).
INVENTORY_PAGE_SIZE = 20
CODE_PAGE_SIZE = 50
ALERT_PAGE_SIZE = 30
TRANSFER_PAGE_SIZE = 20
PARTNER_PAGE_SIZE = 20
INSIGHT_PAGE_SIZE = 30
CATEGORY_PAGE_SIZE = 50

# ── Data retention ────────────────────────────────────────────────────────────
INVENTORY_ALERT_RETENTION_DAYS = 30
INVENTORY_INSIGHT_RETENTION_DAYS = 365
INVENTORY_AUDIT_RETENTION_DAYS = 180

# ── Bulk operation limits ─────────────────────────────────────────────────────
INVENTORY_MAX_BULK_OPERATIONS = 1000
INVENTORY_BATCH_SIZE = 500
INVENTORY_BULK_TIMEOUT = 300  # seconds

# ── Sync configuration ────────────────────────────────────────────────────────
INVENTORY_DEFAULT_SYNC_FREQUENCY = 60  # minutes
INVENTORY_SYNC_RETRY_ATTEMPTS = 3
INVENTORY_SYNC_TIMEOUT = 30  # seconds

# ── Email alert recipients ────────────────────────────────────────────────────
# Inventory sends low-stock and critical-stock alerts to these addresses.
INVENTORY_ALERT_EMAIL_RECIPIENTS = env.list(
    "INVENTORY_ALERT_EMAIL_RECIPIENTS",
    default=[env("ADMIN_EMAIL", default="")],
)

# ── OpenAI / AI features ──────────────────────────────────────────────────────
# Used by openAI.py → views_openai.py (AIInsightView, AIDemandForecastView, etc.)
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini")
OPENAI_MAX_TOKENS = env.int("OPENAI_MAX_TOKENS", default=2000)
OPENAI_TEMPERATURE = 0.3

# ── Encryption ────────────────────────────────────────────────────────────────
# Used by encryption.py → views_encryption.py (EncryptFieldView, RotateKeysView)
INVENTORY_ENCRYPTION_KEY = env(
    "INVENTORY_ENCRYPTION_KEY",
    default="inventoryencryptkey1234567890123",  # 32 bytes — override in prod
)
INVENTORY_ENCRYPTION_ALGORITHM = "AES-256-GCM"

# ── Celery beat schedules (inventory-specific) ────────────────────────────────
# NOTE: CELERY_TIMEZONE = 'Asia/Dhaka' (set above).
# All crontab times below are in Asia/Dhaka (UTC+6).
# Original CeleryBeatConfig used UTC times — adjusted +6h here.
CELERY_BEAT_SCHEDULE.update(
    {
        # ── Maintenance ───────────────────────────────────────────────────────────
        "inventory-cleanup-expired-codes-hourly": {
            "task": "inventory.tasks.cleanup_expired_codes",
            "schedule": crontab(minute=0),  # every hour :00
            "options": {"queue": "maintenance"},
        },
        "inventory-archive-old-data-daily": {
            "task": "inventory.tasks.archive_old_data",
            "schedule": crontab(hour=9, minute=0),  # 9 AM Dhaka (= 3 AM UTC)
            "options": {"queue": "maintenance"},
        },
        "inventory-backup-inventory-data-daily": {
            "task": "inventory.tasks.backup_inventory_data",
            "schedule": crontab(hour=10, minute=0),  # 10 AM Dhaka (= 4 AM UTC)
            "options": {"queue": "maintenance"},
        },
        "inventory-cleanup-audit-logs-weekly": {
            "task": "inventory.tasks.cleanup_audit_logs",
            "schedule": crontab(hour=11, minute=0, day_of_week=0),  # Sun 11 AM Dhaka
            "options": {"queue": "maintenance"},
        },
        "inventory-optimize-database-weekly": {
            "task": "inventory.tasks.optimize_database",
            "schedule": crontab(hour=8, minute=0, day_of_week=6),  # Sat 8 AM Dhaka
            "options": {"queue": "maintenance"},
        },
        # ── Analytics / Insights ──────────────────────────────────────────────────
        "inventory-update-analytics-cache-hourly": {
            "task": "inventory.tasks.update_analytics_cache",
            "schedule": crontab(minute=15),  # every hour :15
            "options": {"queue": "insights"},
        },
        "inventory-generate-daily-insights-daily": {
            "task": "inventory.tasks.generate_daily_insights",
            "schedule": crontab(hour=8, minute=0),  # 8 AM Dhaka (= 2 AM UTC)
            "options": {"queue": "insights"},
        },
        "inventory-generate-weekly-report-weekly": {
            "task": "inventory.tasks.generate_weekly_report",
            "schedule": crontab(hour=14, minute=0, day_of_week=0),  # Sun 2 PM Dhaka
            "options": {"queue": "insights"},
        },
        "inventory-generate-monthly-summary-monthly": {
            "task": "inventory.tasks.generate_monthly_summary",
            "schedule": crontab(hour=12, minute=0, day_of_month=1),  # 1st 12 PM Dhaka
            "options": {"queue": "insights"},
        },
        "inventory-update-exchange-rates-4h": {
            "task": "inventory.tasks.update_exchange_rates",
            "schedule": crontab(minute=0, hour="*/4"),
            "options": {"queue": "insights"},
        },
        "inventory-update-search-index-2h": {
            "task": "inventory.tasks.update_search_index",
            "schedule": crontab(minute=0, hour="*/2"),
            "options": {"queue": "insights"},
        },
        # ── Notifications ─────────────────────────────────────────────────────────
        "inventory-send-stock-alerts-30min": {
            "task": "inventory.tasks.send_stock_alerts",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "alerts"},
        },
        "inventory-send-daily-digest-daily": {
            "task": "inventory.tasks.send_daily_digest",
            "schedule": crontab(hour=14, minute=0),  # 2 PM Dhaka (= 8 AM UTC)
            "options": {"queue": "alerts"},
        },
        "inventory-generate-monthly-invoices-monthly": {
            "task": "inventory.tasks.generate_monthly_invoices",
            "schedule": crontab(hour=13, minute=0, day_of_month=1),  # 1st 1 PM Dhaka
            "options": {"queue": "alerts"},
        },
        # ── Transfers / Sync ──────────────────────────────────────────────────────
        "inventory-process-pending-transfers-15min": {
            "task": "inventory.tasks.process_pending_transfers",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "transfers"},
        },
        "inventory-sync-partner-inventory-6h": {
            "task": "inventory.tasks.sync_partner_inventory",
            "schedule": crontab(minute=30, hour="*/6"),
            "options": {"queue": "partners"},
        },
        # ── Monitoring ────────────────────────────────────────────────────────────
        "inventory-check-system-health-5min": {
            "task": "inventory.tasks.check_system_health",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "monitoring"},
        },
    }
)

# ── Celery task routes (inventory-specific) ───────────────────────────────────
CELERY_TASK_ROUTES.update(
    {
        # Core tasks (tasks.py)
        "inventory.tasks.*": {"queue": "default"},
        "inventory.tasks.cleanup_expired_codes": {"queue": "maintenance"},
        "inventory.tasks.archive_old_data": {"queue": "maintenance"},
        "inventory.tasks.backup_inventory_data": {"queue": "maintenance"},
        "inventory.tasks.cleanup_audit_logs": {"queue": "maintenance"},
        "inventory.tasks.optimize_database": {"queue": "maintenance"},
        "inventory.tasks.update_analytics_cache": {"queue": "insights"},
        "inventory.tasks.generate_daily_insights": {"queue": "insights"},
        "inventory.tasks.generate_weekly_report": {"queue": "insights"},
        "inventory.tasks.generate_monthly_summary": {"queue": "insights"},
        "inventory.tasks.update_exchange_rates": {"queue": "insights"},
        "inventory.tasks.update_search_index": {"queue": "insights"},
        "inventory.tasks.send_stock_alerts": {"queue": "alerts"},
        "inventory.tasks.send_daily_digest": {"queue": "alerts"},
        "inventory.tasks.generate_monthly_invoices": {"queue": "alerts"},
        "inventory.tasks.process_pending_transfers": {"queue": "transfers"},
        "inventory.tasks.sync_partner_inventory": {"queue": "partners"},
        "inventory.tasks.check_system_health": {"queue": "monitoring"},
        # Capability tasks (tasks_cap.py) — dedicated queues per capability
        "inventory.tasks_cap.process_inventory_bulk_import": {"queue": "inventory"},
        "inventory.tasks_cap.process_stock_check": {"queue": "stock"},
        "inventory.tasks_cap.process_redemption_batch": {"queue": "redemption"},
        "inventory.tasks_cap.process_alert_generation": {"queue": "alerts"},
        "inventory.tasks_cap.process_transfer_workflow": {"queue": "transfers"},
        "inventory.tasks_cap.process_partner_sync": {"queue": "partners"},
    }
)

# ── config/asgi.py — inventory WebSocket routing ──────────────────────────────
# ASGI_APPLICATION is already 'config.asgi.application' above.
# Add the inventory consumers to config/asgi.py like this:
#
#   from channels.routing import ProtocolTypeRouter, URLRouter
#   from channels.auth import AuthMiddlewareStack
#   from channels.security.websocket import AllowedHostsOriginValidator
#   from django.urls import re_path
#   from api.inventory.consumers import (
#       InventoryWebSocketConsumer,
#       EventStreamConsumer,
#       RealTimeConsumer,
#   )
#
#   websocket_urlpatterns = [
#       re_path(r'^ws/inventory/$',          InventoryWebSocketConsumer.as_asgi()),
#       re_path(r'^ws/inventory/stream/$',   EventStreamConsumer.as_asgi()),
#       re_path(r'^ws/inventory/realtime/$', RealTimeConsumer.as_asgi()),
#   ]
#
#   application = ProtocolTypeRouter({
#       'http': get_asgi_application(),
#       'websocket': AllowedHostsOriginValidator(
#           AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
#       ),
#   })
#
# ── config/urls.py — inventory REST endpoints ─────────────────────────────────
# Add this line to config/urls.py urlpatterns:
#   path('api/inventory/', include('api.inventory.urls_all')),
#
# ── Worker command — all inventory queues ─────────────────────────────────────
# celery -A config worker -l info \
#   -Q default,inventory,stock,redemption,alerts,transfers,\
#      partners,insights,export,maintenance,monitoring
#
# ── Beat command ──────────────────────────────────────────────────────────────
# celery -A config beat -l info \
#   --scheduler django_celery_beat.schedulers:DatabaseScheduler


# ==================== GAMIFICATION ====================
# Required by api.gamification._connections.wire_all() and feature_flags.py
GAMIFICATION_FEATURE_FLAGS = {
    "CACHE_TIMEOUT": 300,
    "BACKEND": "redis",
    "DEFAULT_ENABLED": False,
}

# Environment flag — used by reset_contest management command
ENVIRONMENT = env("ENVIRONMENT", default="development")

# ==================== GDAL / GEOS ====================
# ✅ FIXED: Cross-platform safe — Windows local dev only, no-op on Linux/Railway
import platform as _platform

if _platform.system() == "Windows":
    _gdal = os.environ.get("GDAL_LIBRARY_PATH", "")
    _geos = os.environ.get("GEOS_LIBRARY_PATH", "")
    if _gdal and os.path.exists(_gdal):
        GDAL_LIBRARY_PATH = _gdal
    if _geos and os.path.exists(_geos):
        GEOS_LIBRARY_PATH = _geos
# On Linux (Railway/Docker): Django auto-detects GDAL/GEOS — no config needed

# ==================== UUID / JSON FIX ====================
try:
    import json
    import uuid
    from datetime import date, datetime
    from decimal import Decimal

    import psycopg2.extensions
    import psycopg2.extras

    class GlobalSafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            if hasattr(obj, "pk"):
                return obj.pk
            return str(obj)

    psycopg2.extensions.register_adapter(
        dict,
        lambda d: psycopg2.extras.Json(
            d, dumps=lambda o: json.dumps(o, cls=GlobalSafeEncoder)
        ),
    )
except Exception:
    pass


# ==================== GAMIFICATION CELERY BEAT TASKS ====================
# ✅ ADDED: gamification periodic tasks merged into project beat schedule
CELERY_BEAT_SCHEDULE.update(
    {
        # ── Daily maintenance ──────────────────────────────────────────────
        "gamif-reset-daily-challenges": {
            "task": "api.gamification.tasks.reset_daily_challenges",
            "schedule": crontab(hour=0, minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-update-daily-leaderboards": {
            "task": "api.gamification.tasks.update_daily_leaderboards",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-generate-daily-reports": {
            "task": "api.gamification.tasks.generate_daily_reports",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-warm-daily-cache": {
            "task": "api.gamification.tasks.warm_daily_cache",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-cleanup-cache": {
            "task": "api.gamification.tasks.cleanup_cache",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": "gamification"},
        },
        # ── Hourly tasks ───────────────────────────────────────────────────
        "gamif-check-expiring-streaks": {
            "task": "api.gamification.tasks.check_expiring_streaks",
            "schedule": crontab(minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-retry-failed-webhooks": {
            "task": "api.gamification.tasks.retry_failed_webhooks",
            "schedule": crontab(minute=30),
            "options": {"queue": "gamification"},
        },
        "gamif-process-analytics": {
            "task": "api.gamification.tasks.process_analytics_data",
            "schedule": crontab(minute=15),
            "options": {"queue": "gamification"},
        },
        "gamif-system-health-check": {
            "task": "api.gamification.tasks.system_health_check",
            "schedule": crontab(minute=45),
            "options": {"queue": "monitoring"},
        },
        # ── Weekly tasks ───────────────────────────────────────────────────
        "gamif-generate-weekly-reports": {
            "task": "api.gamification.tasks.generate_weekly_reports",
            "schedule": crontab(hour=1, minute=0, day_of_week=1),
            "options": {"queue": "gamification"},
        },
        "gamif-reset-weekly-leaderboards": {
            "task": "api.gamification.tasks.reset_weekly_leaderboards",
            "schedule": crontab(hour=0, minute=0, day_of_week=1),
            "options": {"queue": "gamification"},
        },
        # ── Monthly tasks ──────────────────────────────────────────────────
        "gamif-generate-monthly-reports": {
            "task": "api.gamification.tasks.generate_monthly_reports",
            "schedule": crontab(hour=2, minute=0, day_of_month=1),
            "options": {"queue": "gamification"},
        },
        "gamif-cleanup-expired-data": {
            "task": "api.gamification.tasks.cleanup_expired_data",
            "schedule": crontab(hour=3, minute=0, day_of_month=1),
            "options": {"queue": "gamification"},
        },
        # ── Enhanced model tasks ────────────────────────────────────────────
        "gamif-check-points-expiry": {
            "task": "api.gamification.tasks.check_points_expiry",
            "schedule": crontab(hour=0, minute=30),
            "options": {"queue": "gamification"},
        },
        "gamif-cleanup-expired-freezes": {
            "task": "api.gamification.tasks.cleanup_expired_freezes",
            "schedule": crontab(hour=1, minute=30),
            "options": {"queue": "gamification"},
        },
        "gamif-cleanup-contest-participants": {
            "task": "api.gamification.tasks.cleanup_contest_participants",
            "schedule": crontab(hour=2, minute=30),
            "options": {"queue": "gamification"},
        },
        "gamif-generate-daily-insights": {
            "task": "api.gamification.tasks.generate_daily_insights",
            "schedule": crontab(hour=5, minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-sync-config": {
            "task": "api.gamification.tasks.sync_gamification_config",
            "schedule": crontab(minute=0),
            "options": {"queue": "gamification"},
        },
        "gamif-reconcile-points": {
            "task": "api.gamification.tasks.reconcile_points_transactions",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "gamification"},
        },
    }
)

# ✅ ADDED: Gamification Celery task routes
CELERY_TASK_ROUTES.update(
    {
        "api.gamification.tasks.reset_daily_challenges": {"queue": "gamification"},
        "api.gamification.tasks.update_daily_leaderboards": {"queue": "gamification"},
        "api.gamification.tasks.generate_daily_reports": {"queue": "gamification"},
        "api.gamification.tasks.warm_daily_cache": {"queue": "gamification"},
        "api.gamification.tasks.check_expiring_streaks": {"queue": "gamification"},
        "api.gamification.tasks.retry_failed_webhooks": {"queue": "gamification"},
        "api.gamification.tasks.generate_weekly_reports": {"queue": "gamification"},
        "api.gamification.tasks.reset_weekly_leaderboards": {"queue": "gamification"},
        "api.gamification.tasks.generate_monthly_reports": {"queue": "gamification"},
        "api.gamification.tasks.cleanup_expired_data": {"queue": "gamification"},
        "api.gamification.tasks.cleanup_cache": {"queue": "gamification"},
        "api.gamification.tasks.process_analytics_data": {"queue": "gamification"},
        "api.gamification.tasks.system_health_check": {"queue": "monitoring"},
        "api.gamification.tasks.check_points_expiry": {"queue": "gamification"},
        "api.gamification.tasks.cleanup_expired_freezes": {"queue": "gamification"},
        "api.gamification.tasks.cleanup_contest_participants": {
            "queue": "gamification"
        },
        "api.gamification.tasks.generate_daily_insights": {"queue": "gamification"},
        "api.gamification.tasks.sync_gamification_config": {"queue": "gamification"},
        "api.gamification.tasks.reconcile_points_transactions": {
            "queue": "gamification"
        },
        # on-demand tasks (triggered via viewsets / signals)
        "api.gamification.tasks.update_leaderboard_snapshot": {"queue": "gamification"},
        "api.gamification.tasks.activate_contest_cycle": {"queue": "gamification"},
        "api.gamification.tasks.complete_contest_cycle": {"queue": "gamification"},
        "api.gamification.tasks.distribute_cycle_rewards": {"queue": "gamification"},
        "api.gamification.tasks.award_achievement": {"queue": "gamification"},
        "api.gamification.tasks.send_achievement_notification": {
            "queue": "notifications"
        },
        "api.gamification.tasks.award_badge": {"queue": "gamification"},
        "api.gamification.tasks.send_badge_notification": {"queue": "notifications"},
        "api.gamification.tasks.create_daily_challenge": {"queue": "gamification"},
        "api.gamification.tasks.complete_challenge": {"queue": "gamification"},
        "api.gamification.tasks.update_streak": {"queue": "gamification"},
        "api.gamification.tasks.reset_streak": {"queue": "gamification"},
        "api.gamification.tasks.check_level_up": {"queue": "gamification"},
        "api.gamification.tasks.send_level_up_notification": {"queue": "notifications"},
        "api.gamification.tasks.award_points": {"queue": "gamification"},
        "api.gamification.tasks.cleanup_expired_challenges": {"queue": "gamification"},
        "api.gamification.tasks.reset_expired_streaks": {"queue": "gamification"},
        "api.gamification.tasks.clear_gamification_cache": {"queue": "gamification"},
        "api.gamification.tasks.bulk_award_badges": {"queue": "gamification"},
        "api.gamification.tasks.bulk_update_points": {"queue": "gamification"},
    }
)

# ==================== LOCALIZATION SETTINGS ====================
TRANSLATION_PROVIDERS = {
    "deepl": {"enabled": False, "priority": 1, "api_key": ""},
    "google": {"enabled": False, "priority": 2, "api_key": "", "project_id": ""},
    "azure": {"enabled": False, "priority": 3, "api_key": "", "region": "eastus"},
    "amazon": {
        "enabled": False,
        "priority": 4,
        "api_key": "",
        "access_key": "",
        "region": "us-east-1",
    },
    "openai": {
        "enabled": False,
        "priority": 5,
        "api_key": "",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
    },
}

MAXMIND_LICENSE_KEY = ""
GEOIP_PATH = "/var/lib/localization/GeoLite2-City.mmdb"
LOCALIZATION_DETECT_FROM_IP = True
LOCALIZATION_ALERT_EMAIL = True
LOG_MISSING_TRANSLATIONS = True
USER_PREF_CACHE_TTL = 3600
API_CACHE_TIMEOUT = 3600
CACHE_24_HOURS = 86400
MAX_TRANSLATION_TEXT_LENGTH = 5000
LANGUAGE_PACK_CDN_URL = "/api/localization/public/translations"
LOCALIZATION_API_KEYS = []
LOCALIZATION_RATE_LIMITS = {
    "translate": "100/hour",
    "public_translations": "1000/hour",
    "currency_convert": "500/hour",
    "geoip": "200/hour",
}

CELERY_BEAT_SCHEDULE.update(
    {
        "update-exchange-rates": {
            "task": "api.localization.tasks.exchange_rate_tasks.update_rates",
            "schedule": crontab(minute=0),
            "options": {"expires": 3500},
        },
        "clean-translation-cache": {
            "task": "api.localization.tasks.translation_cache_tasks.clean_expired_cache",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        "rebuild-popular-cache": {
            "task": "api.localization.tasks.translation_cache_tasks.rebuild_popular_cache",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        "auto-translate-missing": {
            "task": "api.localization.tasks.auto_translation_tasks.auto_translate_missing",
            "schedule": crontab(minute=0, hour=2),
            "kwargs": {"limit": 200},
        },
        "translation-qa-check": {
            "task": "api.localization.tasks.translation_qa_tasks.run_qa_check",
            "schedule": crontab(minute=0, hour=3),
        },
        "update-coverage": {
            "task": "api.localization.tasks.coverage_report_tasks.update_coverage",
            "schedule": crontab(minute=0, hour=4),
        },
        "alert-missing-translations": {
            "task": "api.localization.tasks.missing_translation_tasks.alert_missing_translations",
            "schedule": crontab(minute=0, hour="*/2"),
        },
        "aggregate-daily-insights": {
            "task": "api.localization.tasks.insight_tasks.aggregate_daily_insights",
            "schedule": crontab(minute=0, hour=0),
        },
        "cleanup-localization": {
            "task": "api.localization.tasks.cleanup_tasks.cleanup_all",
            "schedule": crontab(minute=0, hour=5, day_of_week=0),
        },
        "update-geoip-db": {
            "task": "api.localization.tasks.geoip_update_tasks.update_geoip_db",
            "schedule": crontab(minute=0, hour=6, day_of_week=0),
        },
        "check-provider-health": {
            "task": "api.localization.tasks.provider_health_tasks.check_provider_health",
            "schedule": crontab(minute="*/30"),
        },
        "index-translation-memory": {
            "task": "api.localization.tasks.translation_memory_tasks.index_approved_translations",
            "schedule": crontab(minute=0, hour=7, day_of_week=1),
        },
        "build-language-packs": {
            "task": "api.localization.tasks.language_pack_tasks.build_all_packs",
            "schedule": crontab(minute=0, hour=5),
        },
    }
)

# ==================== CACHE SYSTEM CELERY TASKS ====================
# ✅ ADDED: api/cache/ module tasks — warming, monitoring, analytics, cleanup
CELERY_BEAT_SCHEDULE.update(
    {
        "cache-warm-all-4min": {
            "task": "cache.warm_all",
            "schedule": 240,  # every 4 min (before TTLs expire)
            "options": {"queue": "cache"},
        },
        "cache-warm-priority-on-start": {
            "task": "cache.warm_priority",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6h refresh
            "kwargs": {"max_priority": 1},
            "options": {"queue": "cache"},
        },
        "cache-health-check-1min": {
            "task": "cache.health_check",
            "schedule": 60,
            "options": {"queue": "monitoring"},
        },
        "cache-analytics-report-hourly": {
            "task": "cache.analytics_report",
            "schedule": crontab(minute=5),  # every hour at :05
            "kwargs": {"window_minutes": 60},
            "options": {"queue": "monitoring"},
        },
        "cache-cleanup-daily": {
            "task": "cache.cleanup_expired",
            "schedule": crontab(hour=3, minute=30),  # 3:30 AM daily
            "options": {"queue": "maintenance"},
        },
    }
)

# ✅ ADDED: cache task routes
CELERY_TASK_ROUTES.update(
    {
        "cache.warm_all": {"queue": "cache"},
        "cache.warm_priority": {"queue": "cache"},
        "cache.warm_namespace": {"queue": "cache"},
        "cache.health_check": {"queue": "monitoring"},
        "cache.analytics_report": {"queue": "monitoring"},
        "cache.cleanup_expired": {"queue": "maintenance"},
        "cache.flush_namespace": {"queue": "cache"},
    }
)

# ==================== CACHE MODULE CONFIG ====================
# ✅ ADDED: configuration for the new api/cache/ sub-modules

# Cache Analytics
CACHE_ANALYTICS_MAX_EVENTS = 50_000  # in-memory event buffer
CACHE_ANALYTICS_USE_REDIS = True  # persist counters to Redis

# Cache Warming
CACHE_WARMING_MAX_WORKERS = 6  # parallel warming threads
CACHE_WARMING_ENABLED = True
CACHE_WARMING_ON_STARTUP = True  # warm priority=1 keys on runserver

# Cache Monitoring SLA thresholds
CACHE_MONITOR_THRESHOLDS = {
    "min_hit_rate": 0.70,  # alert if hit rate < 70%
    "max_latency_ms": 10.0,  # alert if ping > 10ms
    "max_memory_mb": 450.0,  # alert if Redis memory > 450MB
    "max_eviction_rate": 100,  # alert if >100 evictions/min
}
CACHE_MONITOR_POLL_INTERVAL = 30  # seconds between health checks
CACHE_MONITOR_SLACK_WEBHOOK = env("CACHE_MONITOR_SLACK_WEBHOOK", default="")

# Cache A/B Testing
CACHE_AB_TESTING_ENABLED = True
CACHE_AB_DEFAULT_SPLIT = 0.5  # 50/50 traffic split

# Multi-Region Cache (leave empty for single-region deployments)
MULTI_REGION_CACHE = [
    # Example — uncomment and fill in when scaling globally:
    # {
    #     'region': 'bd-dhaka',
    #     'redis_url': env('REDIS_URL_BD', default=REDIS_URL),
    #     'priority': 1,
    #     'is_primary': True,
    #     'ip_ranges': ['103.0.0.0/8', '103.108.0.0/16'],
    # },
    # {
    #     'region': 'sg-singapore',
    #     'redis_url': env('REDIS_URL_SG', default=''),
    #     'priority': 2,
    #     'is_primary': False,
    #     'ip_ranges': ['128.199.0.0/16', '188.166.0.0/16'],
    # },
]

# ==================== CACHE URL ROUTING ====================
# In config/urls.py add:
#   path('api/cache/', include('api.cache.urls')),

# ==================== VERSION CONTROL CELERY TASKS ====================
# ✅ ADDED: api.version_control tasks (was completely missing from schedule)
CELERY_BEAT_SCHEDULE.update(
    {
        "vc-dora-daily-snapshot": {
            "task": "version_control.tasks.take_dora_snapshot",
            "schedule": crontab(hour=0, minute=30),
            "options": {"queue": "maintenance"},
        },
        "vc-slo-burn-rate-hourly": {
            "task": "version_control.tasks.evaluate_slo_burn_rates",
            "schedule": crontab(minute=0),
            "options": {"queue": "monitoring"},
        },
        "vc-webhook-retries-1min": {
            "task": "version_control.tasks.process_webhook_retries",
            "schedule": 60,
            "options": {"queue": "webhooks"},
        },
        "vc-gitops-drift-5min": {
            "task": "version_control.tasks.detect_gitops_drift",
            "schedule": 300,
            "options": {"queue": "monitoring"},
        },
        "vc-audit-cleanup-weekly": {
            "task": "version_control.tasks.cleanup_old_audit_logs",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),
            "options": {"queue": "maintenance"},
        },
        "vc-aggregate-metrics-daily": {
            "task": "version_control.tasks.aggregate_usage_metrics",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": "maintenance"},
        },
        "vc-subscription-renewals-daily": {
            "task": "version_control.tasks.process_subscription_renewals",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "maintenance"},
        },
        "vc-trial-expirations-daily": {
            "task": "version_control.tasks.check_trial_expirations",
            "schedule": crontab(hour=7, minute=0),
            "options": {"queue": "maintenance"},
        },
    }
)

# ✅ ADDED: version_control task routes
CELERY_TASK_ROUTES.update(
    {
        "version_control.tasks.take_dora_snapshot": {"queue": "maintenance"},
        "version_control.tasks.evaluate_slo_burn_rates": {"queue": "monitoring"},
        "version_control.tasks.process_webhook_retries": {"queue": "webhooks"},
        "version_control.tasks.detect_gitops_drift": {"queue": "monitoring"},
        "version_control.tasks.cleanup_old_audit_logs": {"queue": "maintenance"},
        "version_control.tasks.aggregate_usage_metrics": {"queue": "maintenance"},
        "version_control.tasks.process_subscription_renewals": {"queue": "maintenance"},
        "version_control.tasks.check_trial_expirations": {"queue": "maintenance"},
    }
)

# ─── FIX 5: version_control SILENCED_SYSTEM_CHECKS already ok ─────────────
# তোমার settings.py তে already আছে:
# SILENCED_SYSTEM_CHECKS = ['urls.W005', 'models.W001']
# এটাই version_control এর namespace warning চুপ করাবে। ✓


# ─── FIX 6: version_control test settings — production conflict নেই ────────
# version_control/settings.py (SQLite) শুধু test runner use করে।
# Main project settings (PostgreSQL) আলাদা।
# Test চালাতে:
#   cd your_project/
#   python manage.py test api.version_control.tests \
#     --settings=api.version_control.settings
# অথবা pytest.ini তে:
#   [pytest]
#   DJANGO_SETTINGS_MODULE = api.version_control.settings


("channels",)  # INSTALLED_APPS-এ
# inventory settings already defined above in base.py


# 1. Celery Beat
# djoyalty not installed — skipping

# 2. Middleware
# MIDDLEWARE += ["djoyalty.middleware.DjoyaltyTenantMiddleware"]  # djoyalty not installed

# 3. WebSocket (Django Channels)
# asgi.py তে routing.py import করো
#
#
# # settings.py — এই ৩টি লাইন যোগ করুন

# 1. TEMPLATES context_processors-এ:
"api.audit_logs.context_processors.audit_logs_context"

# 2. MIDDLEWARE-এ:
"api.audit_logs.middleware.AuditMiddleware"

# 3. CHANNEL_LAYERS (Redis):
# CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', ...}}  # ← code-snippet comment only


from api.payout_queue.payout_queue_settings import (
    PAYMENT_GATEWAY_CONFIGS,
    PAYOUT_AUDIT_LOG_ENABLED,
    PAYOUT_CELERY_BEAT_ENTRIES,
    PAYOUT_FRAUD_CHECK_ENABLED,
    PAYOUT_FRAUD_RISK_THRESHOLD,
    PAYOUT_KYC_CHECK_ENABLED,
    PAYOUT_LOGGING_ENTRIES,
    PAYOUT_NOTIFICATION_TASK,
    PAYOUT_STATS_CACHE_TTL,
    PAYOUT_THROTTLE_RATES,
    PAYOUT_WALLET_CHECK_ENABLED,
    PAYOUT_WEBHOOK_SECRET,
    PAYOUT_WEBHOOK_TIMEOUT_SECONDS,
    PAYOUT_WEBHOOK_URLS,
)

CELERY_BEAT_SCHEDULE.update(PAYOUT_CELERY_BEAT_ENTRIES)
LOGGING["loggers"].update(PAYOUT_LOGGING_ENTRIES)
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update(
    {
        "payout_burst": PAYOUT_THROTTLE_RATES["burst"],
        "payout_sustained": PAYOUT_THROTTLE_RATES["sustained"],
        "payout_process": PAYOUT_THROTTLE_RATES["process"],
    }
)


# =============================================================================
# version_control — MAIN PROJECT SETTINGS ADDITIONS
# =============================================================================
# File: main_project_settings_additions.py
#
# এই ফাইলটি সরাসরি রান করবেন না।
# আপনার main project এর settings.py তে এই sections গুলো খুঁজে বের করে
# নিচের কোড যোগ করুন।
#
# DO NOT run this file. Copy each section into your main project's settings.py
# at the indicated location.
# =============================================================================


# =============================================================================
# SECTION 1 — INSTALLED_APPS
# =============================================================================
# আপনার INSTALLED_APPS list এ এটি ইতিমধ্যে আছে কিনা চেক করুন।
# Check your INSTALLED_APPS — version_control must appear AFTER its dependencies.
# Correct order:
#
# INSTALLED_APPS = [
#     ...
#     "channels",                    # ← add if not present (pip install channels)
#     "django_celery_beat",          # ← add if not present (pip install django-celery-beat)
#     "django_celery_results",       # ← add if not present (pip install django-celery-results)
#     ...
#     "api.tenants.apps.TenantsConfig",         # must be BEFORE version_control
#     "api.subscription.apps.SubscriptionConfig", # must be BEFORE version_control
#     "api.users.apps.UsersConfig",              # must be BEFORE version_control
#     "api.notifications",                        # must be BEFORE version_control
#     "api.audit_logs",                           # must be BEFORE version_control
#     "api.analytics",                            # must be BEFORE version_control
#     "api.security",                             # must be BEFORE version_control
#     ...
#     "api.version_control.apps.VersionControlConfig",  # ← already there ✓
#     ...
# ]


# =============================================================================
# SECTION 2 — MIDDLEWARE
# =============================================================================
# আপনার MIDDLEWARE list এ AuthenticationMiddleware এর পরে এই line যোগ করুন।
# Add AFTER AuthenticationMiddleware in your MIDDLEWARE list:

MIDDLEWARE_ADDITION = """
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # ✅ ADD THIS — version_control maintenance gate
    # Returns 503 JSON during active maintenance windows.
    # Checks X-App-Version and X-App-Platform headers on every request.
    "api.version_control.middleware.VersionControlMiddleware",
]
"""


# =============================================================================
# SECTION 3 — TEMPLATES context_processors
# =============================================================================
# আপনার TEMPLATES[0]["OPTIONS"]["context_processors"] list এ যোগ করুন।
# Add to your TEMPLATES[0]["OPTIONS"]["context_processors"]:

TEMPLATES_ADDITION = """
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [...],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # ✅ ADD THIS — injects {{ maintenance_active }}, {{ current_version }}
                "api.version_control.context_processors.version_control_context",
            ],
        },
    },
]
"""


# =============================================================================
# SECTION 4 — ASGI_APPLICATION
# =============================================================================
# আপনার settings.py তে ASGI_APPLICATION সেট করুন।
# Set your ASGI application:

# ASGI_APPLICATION already set correctly above as "config.asgi.application"


# =============================================================================
# SECTION 5 — CHANNEL_LAYERS
# =============================================================================
# WebSocket support এর জন্য। Redis ব্যবহার করলে RedisChannelLayer।
# For WebSocket support (version_control has 15 WS consumers).

# CHANNEL_LAYERS already configured above with REDIS_URL


# =============================================================================
# SECTION 6 — CELERY
# =============================================================================
# আপনার existing Celery config এর সাথে merge করুন।
# Merge with your existing Celery configuration:

# CELERY_BROKER_URL already set above from REDIS_URL env var
# CELERY_RESULT_BACKEND already set above from REDIS_URL env var

# version_control task routing (ADD to your existing CELERY_TASK_ROUTES):
CELERY_TASK_ROUTES_ADDITION = {
    # High priority — deployment notifications
    "api.version_control.tasks_cap.notify_deployment_status": {
        "queue": "high_priority"
    },
    # Low priority — cleanup
    "api.version_control.tasks_cap.cleanup_old_deployments": {"queue": "low_priority"},
    # Default
    "api.version_control.tasks_cap.sync_feature_flags": {"queue": "default"},
    "api.version_control.celery_tasks_extended.*": {"queue": "default"},
    "api.version_control.management.integration_system.deploy.tasks.*": {
        "queue": "default"
    },
}

# version_control beat schedule flags (ADD to your settings.py):
ENABLE_USAGE_METRICS = True
ENABLE_AUDIT_LOGGING = True
ENABLE_API_KEYS = True
ENABLE_USAGE_AGGREGATION = True
ENABLE_SUBSCRIPTION_RENEWALS = True
ENABLE_TRIAL_EXPIRATION = True
ENABLE_AUDIT_CLEANUP = True


# =============================================================================
# SECTION 7 — REST_FRAMEWORK
# =============================================================================
# আপনার existing REST_FRAMEWORK dict এ এই keys merge করুন।
# Merge these into your existing REST_FRAMEWORK dict:

REST_FRAMEWORK_ADDITIONS = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # ✅ ADD — version_control JWT bridge (tries simplejwt → main project JWT → session)
        "api.version_control.integration.auth.JWTOrSessionAuthentication",
        # Keep your existing auth classes:
        # "rest_framework_simplejwt.authentication.JWTAuthentication",
        # "rest_framework.authentication.SessionAuthentication",
    ],
    # ✅ ADD these throttle scopes to your existing DEFAULT_THROTTLE_RATES:
    "DEFAULT_THROTTLE_RATES_ADDITION": {
        "deployment": "60/minute",  # version_control DeploymentThrottle
        "feature_flag": "120/minute",  # version_control FeatureFlagThrottle
        "maintenance": "30/minute",  # version_control MaintenanceThrottle
        "changelog": "100/minute",  # version_control ChangelogThrottle
    },
}


# =============================================================================
# SECTION 8 — CACHES
# =============================================================================
# আপনার existing CACHES dict এ এই named cache যোগ করুন।
# Add this named cache to your existing CACHES dict:

CACHES_ADDITION = {
    # version_control uses a named "version_control" cache for maintenance
    # windows and feature-flag state (allows independent eviction).
    "version_control": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",  # use a different DB number
        "TIMEOUT": 300,
        "KEY_PREFIX": "vc",
    },
}


# =============================================================================
# SECTION 9 — CELERY AUTODISCOVER (main project celery.py)
# =============================================================================
# আপনার main project এর celery.py তে autodiscover_tasks() call এর পরে যোগ করুন।
# Add AFTER your existing app.autodiscover_tasks() call in celery.py:

CELERY_AUTODISCOVER_SNIPPET = """
# ✅ ADD to your main project celery.py — version_control task modules
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="tasks",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="tasks_cap",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="celery_tasks_extended",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control.management.integration_system.deploy"],
    related_name="tasks",
    force=True,
)
# Load version_control beat schedule
try:
    from api.version_control.celery_beat_config import beat_config  # noqa: F401
except Exception:
    pass
"""


# =============================================================================
# SECTION 10 — ASGI (main project asgi.py)
# =============================================================================
# আপনার main project এর asgi.py তে ProtocolTypeRouter এর আগে যোগ করুন।
# Add BEFORE your ProtocolTypeRouter in your main project's asgi.py:

ASGI_WEBSOCKET_SNIPPET = """
# ✅ ADD to your main project asgi.py — version_control WebSocket consumers

# Legacy consumers (DeploymentConsumer, FeatureFlagConsumer, etc.)
try:
    from api.version_control.routing import websocket_urlpatterns as vc_legacy_ws
except Exception:
    vc_legacy_ws = []

# v7+ consumers (DORA, SLO, GitOps, PR notification, etc.)
try:
    from api.version_control.websocket_routing import websocket_urlpatterns as vc_new_ws
except Exception:
    vc_new_ws = []

# Merge: vc new routes first (more specific), then vc legacy, then existing app routes
all_websocket_urlpatterns = (
    list(vc_new_ws)
    + list(vc_legacy_ws)
    + list(your_existing_websocket_urlpatterns)  # ← replace with your var name
)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(all_websocket_urlpatterns)   # ← use merged list
        )
    ),
})
"""


# =============================================================================
# SECTION 11 — URLS (main project urls.py)
# =============================================================================
# আপনার main project এর urls.py তে version_control এর URL একবারই যোগ করুন।
# Register version_control URLs ONCE in your main urls.py:

URLS_SNIPPET = """
# ✅ In your main project urls.py — add version_control with namespace:
from django.urls import path, include

urlpatterns = [
    # ... your existing URL patterns ...

    # version_control — single namespaced registration
    path('api/version/', include(('api.version_control.urls', 'version_control'))),

    # ⚠️ REMOVE any duplicate like:
    # path('api/v1/', include(('api.version_control.urls', 'version_control_v1'))),
]
"""


# =============================================================================
# SECTION 12 — pip install (new dependencies)
# =============================================================================
NEW_DEPENDENCIES = """
# ✅ Add to your requirements.txt / pip install:

channels>=4.0                  # WebSocket support
channels-redis>=4.1            # Redis channel layer
daphne>=4.0                    # OR: uvicorn[standard]>=0.24
celery>=5.3                    # Task queue (if not already installed)
redis>=5.0                     # Redis client
django-celery-beat>=2.5        # DB-backed beat scheduler
django-celery-results>=2.5     # Store task results in DB
python-dotenv>=1.0             # .env file support
"""

from api.webhooks.settings.webhooks_settings import (
    INBOUND_WEBHOOK_HANDLER_MODULES,
    WEBHOOK_ADAPTER_CONFIG,
    WEBHOOK_AUTH_BRIDGE_CONFIG,
    WEBHOOK_AUTO_SUSPEND_ENABLED,
    WEBHOOK_BRIDGE_CONFIG,
    WEBHOOK_DATA_BRIDGE_CONFIG,
    WEBHOOK_DEFAULT_TIMEOUT,
    WEBHOOK_FALLBACK_CONFIG,
    WEBHOOK_HEALTH_CHECK_INTERVAL,
    WEBHOOK_MAX_CONSECUTIVE_FAILURES,
    WEBHOOK_MAX_RETRIES,
    WEBHOOK_MESSAGE_QUEUE_CONFIG,
    WEBHOOK_REGISTRY_CONFIG,
    WEBHOOK_SECRET_LENGTH,
    WEBHOOK_SIGNAL_CONFIG,
    WEBHOOKS,
    WEBHOOKS_ALLOW_HTTP,
    WEBHOOKS_INTEGRATION_CONFIG,
)
try:
    from api.webhooks.settings import webhooks_settings as _wh
    if hasattr(_wh, 'CELERY_BEAT_SCHEDULE'):
        CELERY_BEAT_SCHEDULE.update(_wh.CELERY_BEAT_SCHEDULE)
    if hasattr(_wh, 'CELERY_TASK_ROUTES'):
        CELERY_TASK_ROUTES.update(_wh.CELERY_TASK_ROUTES)
    if hasattr(_wh, 'LOGGING'):
        # শুধু loggers নাও — কিন্তু শুধু সেগুলো যেগুলোর handlers আমাদের আছে
        safe_handlers = set(LOGGING['handlers'].keys())
        for logger_name, logger_cfg in _wh.LOGGING.get('loggers', {}).items():
            used_handlers = set(logger_cfg.get('handlers', []))
            if used_handlers.issubset(safe_handlers):
                LOGGING['loggers'][logger_name] = logger_cfg
            else:
                # অজানা handler-এর বদলে 'console' দিয়ে রাখো
                safe_cfg = dict(logger_cfg)
                safe_cfg['handlers'] = ['console']
                LOGGING['loggers'][logger_name] = safe_cfg
    if hasattr(_wh, 'REST_FRAMEWORK'):
        REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update(
            _wh.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        )
    if hasattr(_wh, 'CORS_ALLOWED_ORIGINS'):
        CORS_ALLOWED_ORIGINS = list(set(CORS_ALLOWED_ORIGINS + _wh.CORS_ALLOWED_ORIGINS))
except Exception:
    pass

# =============================================================================
# version_control — MAIN PROJECT SETTINGS ADDITIONS
# =============================================================================
# File: main_project_settings_additions.py
#
# এই ফাইলটি সরাসরি রান করবেন না।
# আপনার main project এর settings.py তে এই sections গুলো খুঁজে বের করে
# নিচের কোড যোগ করুন।
#
# DO NOT run this file. Copy each section into your main project's settings.py
# at the indicated location.
# =============================================================================


# =============================================================================
# SECTION 1 — INSTALLED_APPS
# =============================================================================
# আপনার INSTALLED_APPS list এ এটি ইতিমধ্যে আছে কিনা চেক করুন।
# Check your INSTALLED_APPS — version_control must appear AFTER its dependencies.
# Correct order:
#
# INSTALLED_APPS = [
#     ...
#     "channels",                    # ← add if not present (pip install channels)
#     "django_celery_beat",          # ← add if not present (pip install django-celery-beat)
#     "django_celery_results",       # ← add if not present (pip install django-celery-results)
#     ...
#     "api.tenants.apps.TenantsConfig",         # must be BEFORE version_control
#     "api.subscription.apps.SubscriptionConfig", # must be BEFORE version_control
#     "api.users.apps.UsersConfig",              # must be BEFORE version_control
#     "api.notifications",                        # must be BEFORE version_control
#     "api.audit_logs",                           # must be BEFORE version_control
#     "api.analytics",                            # must be BEFORE version_control
#     "api.security",                             # must be BEFORE version_control
#     ...
#     "api.version_control.apps.VersionControlConfig",  # ← already there ✓
#     ...
# ]


# =============================================================================
# SECTION 2 — MIDDLEWARE
# =============================================================================
# আপনার MIDDLEWARE list এ AuthenticationMiddleware এর পরে এই line যোগ করুন।
# Add AFTER AuthenticationMiddleware in your MIDDLEWARE list:

MIDDLEWARE_ADDITION = """
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # ✅ ADD THIS — version_control maintenance gate
    # Returns 503 JSON during active maintenance windows.
    # Checks X-App-Version and X-App-Platform headers on every request.
    "api.version_control.middleware.VersionControlMiddleware",
]
"""


# =============================================================================
# SECTION 3 — TEMPLATES context_processors
# =============================================================================
# আপনার TEMPLATES[0]["OPTIONS"]["context_processors"] list এ যোগ করুন।
# Add to your TEMPLATES[0]["OPTIONS"]["context_processors"]:

TEMPLATES_ADDITION = """
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [...],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # ✅ ADD THIS — injects {{ maintenance_active }}, {{ current_version }}
                "api.version_control.context_processors.version_control_context",
            ],
        },
    },
]
"""


# =============================================================================
# SECTION 4 — ASGI_APPLICATION
# =============================================================================
# আপনার settings.py তে ASGI_APPLICATION সেট করুন।
# Set your ASGI application:

# ASGI_APPLICATION already set correctly above as "config.asgi.application"


# =============================================================================
# SECTION 5 — CHANNEL_LAYERS
# =============================================================================
# WebSocket support এর জন্য। Redis ব্যবহার করলে RedisChannelLayer।
# For WebSocket support (version_control has 15 WS consumers).

# CHANNEL_LAYERS already configured above with REDIS_URL


# =============================================================================
# SECTION 6 — CELERY
# =============================================================================
# আপনার existing Celery config এর সাথে merge করুন।
# Merge with your existing Celery configuration:

# CELERY_BROKER_URL already set above from REDIS_URL env var
# CELERY_RESULT_BACKEND already set above from REDIS_URL env var

# version_control task routing (ADD to your existing CELERY_TASK_ROUTES):
CELERY_TASK_ROUTES_ADDITION = {
    # High priority — deployment notifications
    "api.version_control.tasks_cap.notify_deployment_status": {
        "queue": "high_priority"
    },
    # Low priority — cleanup
    "api.version_control.tasks_cap.cleanup_old_deployments": {"queue": "low_priority"},
    # Default
    "api.version_control.tasks_cap.sync_feature_flags": {"queue": "default"},
    "api.version_control.celery_tasks_extended.*": {"queue": "default"},
    "api.version_control.management.integration_system.deploy.tasks.*": {
        "queue": "default"
    },
}

# version_control beat schedule flags (ADD to your settings.py):
ENABLE_USAGE_METRICS = True
ENABLE_AUDIT_LOGGING = True
ENABLE_API_KEYS = True
ENABLE_USAGE_AGGREGATION = True
ENABLE_SUBSCRIPTION_RENEWALS = True
ENABLE_TRIAL_EXPIRATION = True
ENABLE_AUDIT_CLEANUP = True


# =============================================================================
# SECTION 7 — REST_FRAMEWORK
# =============================================================================
# আপনার existing REST_FRAMEWORK dict এ এই keys merge করুন।
# Merge these into your existing REST_FRAMEWORK dict:

REST_FRAMEWORK_ADDITIONS = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # ✅ ADD — version_control JWT bridge (tries simplejwt → main project JWT → session)
        "api.version_control.integration.auth.JWTOrSessionAuthentication",
        # Keep your existing auth classes:
        # "rest_framework_simplejwt.authentication.JWTAuthentication",
        # "rest_framework.authentication.SessionAuthentication",
    ],
    # ✅ ADD these throttle scopes to your existing DEFAULT_THROTTLE_RATES:
    "DEFAULT_THROTTLE_RATES_ADDITION": {
        "deployment": "60/minute",  # version_control DeploymentThrottle
        "feature_flag": "120/minute",  # version_control FeatureFlagThrottle
        "maintenance": "30/minute",  # version_control MaintenanceThrottle
        "changelog": "100/minute",  # version_control ChangelogThrottle
    },
}


# =============================================================================
# SECTION 8 — CACHES
# =============================================================================
# আপনার existing CACHES dict এ এই named cache যোগ করুন।
# Add this named cache to your existing CACHES dict:

CACHES_ADDITION = {
    # version_control uses a named "version_control" cache for maintenance
    # windows and feature-flag state (allows independent eviction).
    "version_control": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/3",  # use a different DB number
        "TIMEOUT": 300,
        "KEY_PREFIX": "vc",
    },
}


# =============================================================================
# SECTION 9 — CELERY AUTODISCOVER (main project celery.py)
# =============================================================================
# আপনার main project এর celery.py তে autodiscover_tasks() call এর পরে যোগ করুন।
# Add AFTER your existing app.autodiscover_tasks() call in celery.py:

CELERY_AUTODISCOVER_SNIPPET = """
# ✅ ADD to your main project celery.py — version_control task modules
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="tasks",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="tasks_cap",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control"],
    related_name="celery_tasks_extended",
    force=True,
)
app.autodiscover_tasks(
    packages=["api.version_control.management.integration_system.deploy"],
    related_name="tasks",
    force=True,
)
# Load version_control beat schedule
try:
    from api.version_control.celery_beat_config import beat_config  # noqa: F401
except Exception:
    pass
"""


# =============================================================================
# SECTION 10 — ASGI (main project asgi.py)
# =============================================================================
# আপনার main project এর asgi.py তে ProtocolTypeRouter এর আগে যোগ করুন।
# Add BEFORE your ProtocolTypeRouter in your main project's asgi.py:

ASGI_WEBSOCKET_SNIPPET = """
# ✅ ADD to your main project asgi.py — version_control WebSocket consumers

# Legacy consumers (DeploymentConsumer, FeatureFlagConsumer, etc.)
try:
    from api.version_control.routing import websocket_urlpatterns as vc_legacy_ws
except Exception:
    vc_legacy_ws = []

# v7+ consumers (DORA, SLO, GitOps, PR notification, etc.)
try:
    from api.version_control.websocket_routing import websocket_urlpatterns as vc_new_ws
except Exception:
    vc_new_ws = []

# Merge: vc new routes first (more specific), then vc legacy, then existing app routes
all_websocket_urlpatterns = (
    list(vc_new_ws)
    + list(vc_legacy_ws)
    + list(your_existing_websocket_urlpatterns)  # ← replace with your var name
)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(all_websocket_urlpatterns)   # ← use merged list
        )
    ),
})
"""


# =============================================================================
# SECTION 11 — URLS (main project urls.py)
# =============================================================================
# আপনার main project এর urls.py তে version_control এর URL একবারই যোগ করুন।
# Register version_control URLs ONCE in your main urls.py:

URLS_SNIPPET = """
# ✅ In your main project urls.py — add version_control with namespace:
from django.urls import path, include

urlpatterns = [
    # ... your existing URL patterns ...

    # version_control — single namespaced registration
    path('api/version/', include(('api.version_control.urls', 'version_control'))),

    # ⚠️ REMOVE any duplicate like:
    # path('api/v1/', include(('api.version_control.urls', 'version_control_v1'))),
]
"""


# =============================================================================
# ==================== DJOYALTY + PAYOUT_QUEUE SETTINGS ====================
# =============================================================================

# ── Sentry (shared by djoyalty + payout_queue apps.py) ───────────────────────
SENTRY_DSN              = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT      = env("SENTRY_ENVIRONMENT", default="development")
SENTRY_TRACES_RATE      = env.float("SENTRY_TRACES_RATE", default=0.05)
SENTRY_PROFILES_RATE    = env.float("SENTRY_PROFILES_RATE", default=0.0)
SENTRY_SEND_PII         = env.bool("SENTRY_SEND_PII", default=False)

# ── Payout Queue — Encryption ─────────────────────────────────────────────────
# encryption.py reads settings.PAYOUT_ENCRYPTION_KEY directly.
# Must be a valid 32-byte Fernet key. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PAYOUT_ENCRYPTION_KEY = env("PAYOUT_ENCRYPTION_KEY", default="")

# ── Djoyalty — Core Config ────────────────────────────────────────────────────
DJOYALTY_POINTS_CURRENCY        = env("DJOYALTY_POINTS_CURRENCY", default="pts")
DJOYALTY_POINTS_EXPIRY_DAYS     = env.int("DJOYALTY_POINTS_EXPIRY_DAYS", default=365)
DJOYALTY_FRAUD_SCORE_THRESHOLD  = env.int("DJOYALTY_FRAUD_SCORE_THRESHOLD", default=80)
DJOYALTY_TIER_EVALUATION_ENABLED = env.bool("DJOYALTY_TIER_EVALUATION_ENABLED", default=True)
DJOYALTY_LEADERBOARD_SIZE       = env.int("DJOYALTY_LEADERBOARD_SIZE", default=100)
DJOYALTY_CASHOUT_MIN_POINTS     = env.int("DJOYALTY_CASHOUT_MIN_POINTS", default=500)
DJOYALTY_CASHOUT_MAX_POINTS     = env.int("DJOYALTY_CASHOUT_MAX_POINTS", default=50000)
DJOYALTY_PARTNER_SYNC_ENABLED   = env.bool("DJOYALTY_PARTNER_SYNC_ENABLED", default=True)
DJOYALTY_VOUCHER_EXPIRY_DAYS    = env.int("DJOYALTY_VOUCHER_EXPIRY_DAYS", default=30)
DJOYALTY_SUBSCRIPTION_ENABLED   = env.bool("DJOYALTY_SUBSCRIPTION_ENABLED", default=True)
DJOYALTY_GIFT_CARD_EXPIRY_DAYS  = env.int("DJOYALTY_GIFT_CARD_EXPIRY_DAYS", default=180)
DJOYALTY_MAX_EARN_PER_DAY       = env.int("DJOYALTY_MAX_EARN_PER_DAY", default=10000)
DJOYALTY_STREAK_GRACE_HOURS     = env.int("DJOYALTY_STREAK_GRACE_HOURS", default=2)
DJOYALTY_REDEMPTION_AUTO_APPROVE_DAYS = env.int("DJOYALTY_REDEMPTION_AUTO_APPROVE_DAYS", default=3)

# ── Djoyalty — Celery Beat Schedule (26 tasks) ────────────────────────────────
CELERY_BEAT_SCHEDULE.update({

    # Points Expiry
    "djoyalty-expire-points-daily": {
        "task": "api.djoyalty.tasks.points_expiry_tasks.expire_points_task",
        "schedule": crontab(hour=1, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-send-expiry-warnings-daily": {
        "task": "api.djoyalty.tasks.points_expiry_tasks.send_expiry_warnings_task",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "djoyalty"},
    },

    # Tier Evaluation
    "djoyalty-evaluate-all-tiers-daily": {
        "task": "api.djoyalty.tasks.tier_evaluation_tasks.evaluate_all_tiers_task",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "djoyalty"},
    },

    # Streak Reset
    "djoyalty-reset-daily-streaks": {
        "task": "api.djoyalty.tasks.streak_reset_tasks.reset_all_daily_streaks_task",
        "schedule": crontab(hour=0, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-check-broken-streaks-daily": {
        "task": "api.djoyalty.tasks.streak_reset_tasks.check_broken_streaks_task",
        "schedule": crontab(hour=0, minute=30),
        "options": {"queue": "djoyalty"},
    },

    # Campaigns
    "djoyalty-activate-campaigns-hourly": {
        "task": "api.djoyalty.tasks.campaign_tasks.activate_due_campaigns_task",
        "schedule": crontab(minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-notify-campaign-participants-hourly": {
        "task": "api.djoyalty.tasks.campaign_tasks.notify_campaign_participants_task",
        "schedule": crontab(minute=20),
        "options": {"queue": "djoyalty"},
    },

    # Notifications
    "djoyalty-send-expiry-notifications-daily": {
        "task": "api.djoyalty.tasks.notification_tasks.send_expiry_notifications_task",
        "schedule": crontab(hour=9, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-send-pending-notifications-hourly": {
        "task": "api.djoyalty.tasks.notification_tasks.send_pending_notifications_task",
        "schedule": crontab(minute=30),
        "options": {"queue": "djoyalty"},
    },

    # Leaderboard
    "djoyalty-refresh-leaderboard-hourly": {
        "task": "api.djoyalty.tasks.leaderboard_tasks.refresh_leaderboard_task",
        "schedule": crontab(minute=15),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-refresh-monthly-leaderboard": {
        "task": "api.djoyalty.tasks.leaderboard_tasks.refresh_monthly_leaderboard_task",
        "schedule": crontab(hour=0, minute=5, day_of_month=1),
        "options": {"queue": "djoyalty"},
    },

    # Insights
    "djoyalty-generate-daily-insight": {
        "task": "api.djoyalty.tasks.insight_tasks.generate_daily_insight_task",
        "schedule": crontab(hour=5, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-generate-weekly-insight": {
        "task": "api.djoyalty.tasks.insight_tasks.generate_weekly_insight_task",
        "schedule": crontab(hour=5, minute=30, day_of_week=1),
        "options": {"queue": "djoyalty"},
    },

    # Fraud
    "djoyalty-fraud-scan-hourly": {
        "task": "api.djoyalty.tasks.fraud_check_tasks.fraud_scan_task",
        "schedule": crontab(minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-scan-rapid-transactions-15min": {
        "task": "api.djoyalty.tasks.fraud_check_tasks.scan_rapid_transactions_task",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "djoyalty"},
    },

    # Redemption
    "djoyalty-auto-approve-redemptions-hourly": {
        "task": "api.djoyalty.tasks.redemption_tasks.auto_approve_redemptions_task",
        "schedule": crontab(minute=45),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-expire-old-pending-redemptions-daily": {
        "task": "api.djoyalty.tasks.redemption_tasks.expire_old_pending_redemptions_task",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "djoyalty"},
    },

    # Voucher & Gift Card
    "djoyalty-expire-vouchers-daily": {
        "task": "api.djoyalty.tasks.voucher_expiry_tasks.expire_vouchers_task",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-expire-gift-cards-daily": {
        "task": "api.djoyalty.tasks.voucher_expiry_tasks.expire_gift_cards_task",
        "schedule": crontab(hour=4, minute=45),
        "options": {"queue": "djoyalty"},
    },

    # Partners
    "djoyalty-sync-partners-daily": {
        "task": "api.djoyalty.tasks.partner_sync_tasks.sync_partners_task",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-check-partner-webhooks-30min": {
        "task": "api.djoyalty.tasks.partner_sync_tasks.check_partner_webhooks_task",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "djoyalty"},
    },

    # Subscriptions
    "djoyalty-process-subscription-renewals-daily": {
        "task": "api.djoyalty.tasks.subscription_tasks.process_subscription_renewals_task",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-cancel-expired-subscriptions-daily": {
        "task": "api.djoyalty.tasks.subscription_tasks.cancel_expired_subscriptions_task",
        "schedule": crontab(hour=7, minute=30),
        "options": {"queue": "djoyalty"},
    },

    # Earn Rules
    "djoyalty-deactivate-expired-earn-rules-daily": {
        "task": "api.djoyalty.tasks.earn_rule_tasks.deactivate_expired_earn_rules_task",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "djoyalty"},
    },
    "djoyalty-activate-scheduled-earn-rules-15min": {
        "task": "api.djoyalty.tasks.earn_rule_tasks.activate_scheduled_earn_rules_task",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "djoyalty"},
    },
})

# ── Djoyalty — Celery Task Routes ─────────────────────────────────────────────
CELERY_TASK_ROUTES.update({
    "api.djoyalty.tasks.points_expiry_tasks.expire_points_task":              {"queue": "djoyalty"},
    "api.djoyalty.tasks.points_expiry_tasks.send_expiry_warnings_task":       {"queue": "djoyalty"},
    "api.djoyalty.tasks.tier_evaluation_tasks.evaluate_all_tiers_task":       {"queue": "djoyalty"},
    "api.djoyalty.tasks.tier_evaluation_tasks.evaluate_single_customer_tier_task": {"queue": "djoyalty"},
    "api.djoyalty.tasks.streak_reset_tasks.check_broken_streaks_task":        {"queue": "djoyalty"},
    "api.djoyalty.tasks.streak_reset_tasks.reset_all_daily_streaks_task":     {"queue": "djoyalty"},
    "api.djoyalty.tasks.campaign_tasks.activate_due_campaigns_task":          {"queue": "djoyalty"},
    "api.djoyalty.tasks.campaign_tasks.notify_campaign_participants_task":     {"queue": "djoyalty"},
    "api.djoyalty.tasks.notification_tasks.send_expiry_notifications_task":   {"queue": "djoyalty"},
    "api.djoyalty.tasks.notification_tasks.send_pending_notifications_task":  {"queue": "djoyalty"},
    "api.djoyalty.tasks.leaderboard_tasks.refresh_leaderboard_task":          {"queue": "djoyalty"},
    "api.djoyalty.tasks.leaderboard_tasks.refresh_monthly_leaderboard_task":  {"queue": "djoyalty"},
    "api.djoyalty.tasks.insight_tasks.generate_daily_insight_task":           {"queue": "djoyalty"},
    "api.djoyalty.tasks.insight_tasks.generate_weekly_insight_task":          {"queue": "djoyalty"},
    "api.djoyalty.tasks.fraud_check_tasks.fraud_scan_task":                   {"queue": "djoyalty"},
    "api.djoyalty.tasks.fraud_check_tasks.scan_rapid_transactions_task":      {"queue": "djoyalty"},
    "api.djoyalty.tasks.redemption_tasks.auto_approve_redemptions_task":      {"queue": "djoyalty"},
    "api.djoyalty.tasks.redemption_tasks.expire_old_pending_redemptions_task":{"queue": "djoyalty"},
    "api.djoyalty.tasks.voucher_expiry_tasks.expire_vouchers_task":           {"queue": "djoyalty"},
    "api.djoyalty.tasks.voucher_expiry_tasks.expire_gift_cards_task":         {"queue": "djoyalty"},
    "api.djoyalty.tasks.partner_sync_tasks.sync_partners_task":               {"queue": "djoyalty"},
    "api.djoyalty.tasks.partner_sync_tasks.check_partner_webhooks_task":      {"queue": "djoyalty"},
    "api.djoyalty.tasks.subscription_tasks.process_subscription_renewals_task":  {"queue": "djoyalty"},
    "api.djoyalty.tasks.subscription_tasks.cancel_expired_subscriptions_task":   {"queue": "djoyalty"},
    "api.djoyalty.tasks.earn_rule_tasks.deactivate_expired_earn_rules_task":  {"queue": "djoyalty"},
    "api.djoyalty.tasks.earn_rule_tasks.activate_scheduled_earn_rules_task":  {"queue": "djoyalty"},
})

# ── Djoyalty — Logging ────────────────────────────────────────────────────────
LOGGING["loggers"].update({
    "api.djoyalty": {
        "handlers": ["console"],
        "level": "INFO",
        "propagate": False,
    },
    "djoyalty": {
        "handlers": ["console"],
        "level": "INFO",
        "propagate": False,
    },
})

# =============================================================================
# ==================== END DJOYALTY + PAYOUT_QUEUE ====================
# =============================================================================

# ==================== SMARTLINK CORE CONFIG ====================
SMARTLINK_OFFER_MODEL       = "offer_inventory.Offer"
SMARTLINK_ADVERTISER_MODEL  = "advertiser_portal.Advertiser"
SMARTLINK_BASE_URL          = env("SMARTLINK_BASE_URL", default="https://go.yourdomain.com")
SMARTLINK_REDIRECT_PREFIX   = env("SMARTLINK_REDIRECT_PREFIX", default="go")
SMARTLINK_FRONTEND_URL      = env("SMARTLINK_FRONTEND_URL", default="https://yourdomain.com")
SMARTLINK_POSTBACK_URL      = env("SMARTLINK_POSTBACK_URL", default="/api/smartlink/postback/")
SMARTLINK_POSTBACK_SECRET   = env("SMARTLINK_POSTBACK_SECRET", default="change-me-in-production")
SMARTLINK_PIXEL_BASE_URL    = env("SMARTLINK_PIXEL_BASE_URL", default="")
SMARTLINK_ATTRIBUTION_WINDOW_HOURS = env.int("SMARTLINK_ATTRIBUTION_WINDOW_HOURS", default=24)
SMARTLINK_DEFAULT_FALLBACK_URL     = env("SMARTLINK_DEFAULT_FALLBACK_URL", default="https://yourdomain.com")
SMARTLINK_IOS_BUNDLE_IDS    = env.list("SMARTLINK_IOS_BUNDLE_IDS", default=[])
SMARTLINK_ANDROID_APPS      = env.list("SMARTLINK_ANDROID_APPS", default=[])
SMARTLINK_PLATFORM_NAME     = env("SMARTLINK_PLATFORM_NAME", default="SmartLink Platform")
SMARTLINK_PLATFORM_EMAIL    = env("SMARTLINK_PLATFORM_EMAIL", default="billing@yourdomain.com")
SMARTLINK_PLATFORM_ADDRESS  = env("SMARTLINK_PLATFORM_ADDRESS", default="")
SMARTLINK_PLATFORM_WEBSITE  = env("SMARTLINK_PLATFORM_WEBSITE", default="https://yourdomain.com")
SMARTLINK_PAYPAL_CLIENT_ID      = env("SMARTLINK_PAYPAL_CLIENT_ID", default="")
SMARTLINK_PAYPAL_CLIENT_SECRET  = env("SMARTLINK_PAYPAL_CLIENT_SECRET", default="")
SMARTLINK_PAYPAL_MODE           = env("SMARTLINK_PAYPAL_MODE", default="sandbox")
SMARTLINK_PAYPAL_WEBHOOK_ID     = env("SMARTLINK_PAYPAL_WEBHOOK_ID", default="")
SMARTLINK_WISE_API_KEY          = env("SMARTLINK_WISE_API_KEY", default="")
SMARTLINK_WISE_PROFILE_ID       = env("SMARTLINK_WISE_PROFILE_ID", default=None)
SMARTLINK_WISE_MODE             = env("SMARTLINK_WISE_MODE", default="sandbox")
SMARTLINK_WISE_WEBHOOK_SECRET   = env("SMARTLINK_WISE_WEBHOOK_SECRET", default="")

# ==================== SMARTLINK — CELERY BEAT ====================
CELERY_BEAT_SCHEDULE.update({
    "sl-process-schedules-1min":            {"task": "smartlink.process_schedules",                "schedule": 60,                              "options": {"queue": "default"}},
    "sl-retry-webhook-2min":                {"task": "smartlink.retry_webhook_deliveries",         "schedule": 120,                             "options": {"queue": "webhooks"}},
    "sl-warmup-resolver-5min":              {"task": "smartlink.warmup_resolver_cache",            "schedule": crontab(minute="*/5"),            "options": {"queue": "default"}},
    "sl-warmup-offer-pool-5min":            {"task": "smartlink.warmup_offer_pool_cache",          "schedule": crontab(minute="*/5"),            "options": {"queue": "default"}},
    "sl-redirect-health-10min":             {"task": "smartlink.check_smartlink_redirect_health",  "schedule": crontab(minute="*/10"),           "options": {"queue": "maintenance"}},
    "sl-fraud-velocity-15min":              {"task": "smartlink.scan_high_velocity_ips",           "schedule": crontab(minute="*/15"),           "options": {"queue": "fraud"}},
    "sl-check-expiry-15min":                {"task": "smartlink.check_smartlink_expiry",           "schedule": crontab(minute="*/15"),           "options": {"queue": "default"}},
    "sl-epc-scores-30min":                  {"task": "smartlink.update_epc_scores",                "schedule": crontab(minute="*/30"),           "options": {"queue": "analytics"}},
    "sl-offer-scores-30min":                {"task": "smartlink.update_offer_scores",              "schedule": crontab(minute="*/30"),           "options": {"queue": "analytics"}},
    "sl-heatmaps-30min":                    {"task": "smartlink.build_heatmaps",                   "schedule": crontab(minute="*/30"),           "options": {"queue": "analytics"}},
    "sl-offer-perf-stats-30min":            {"task": "smartlink.update_offer_performance_stats",   "schedule": crontab(minute="*/30"),           "options": {"queue": "analytics"}},
    "sl-cap-alert-30min":                   {"task": "smartlink.alert_cap_nearly_reached",         "schedule": crontab(minute="*/30"),           "options": {"queue": "notifications"}},
    "sl-hourly-stat-rollup":                {"task": "smartlink.hourly_stat_rollup",               "schedule": crontab(minute=0),                "options": {"queue": "analytics"}},
    "sl-hourly-fraud-scan":                 {"task": "smartlink.hourly_fraud_scan",                "schedule": crontab(minute=5),                "options": {"queue": "fraud"}},
    "sl-ab-tests-hourly":                   {"task": "smartlink.evaluate_ab_tests",                "schedule": crontab(minute=10),               "options": {"queue": "analytics"}},
    "sl-currency-rates-hourly":             {"task": "smartlink.update_currency_rates",            "schedule": crontab(minute=15),               "options": {"queue": "default"}},
    "sl-payout-notify-hourly":              {"task": "smartlink.send_payout_ready_notifications",  "schedule": crontab(minute=45),               "options": {"queue": "notifications"}},
    "sl-broken-links-6hr":                  {"task": "smartlink.check_broken_smartlinks",          "schedule": crontab(minute=0,  hour="*/6"),   "options": {"queue": "maintenance"}},
    "sl-verify-domains-6hr":                {"task": "smartlink.verify_pending_domains",           "schedule": crontab(minute=30, hour="*/6"),   "options": {"queue": "default"}},
    "sl-offer-pool-health-6hr":             {"task": "smartlink.check_offer_pool_health",          "schedule": crontab(minute=45, hour="*/6"),   "options": {"queue": "default"}},
    "sl-reset-daily-caps":                  {"task": "smartlink.reset_daily_caps",                 "schedule": crontab(minute=0,  hour=0),       "options": {"queue": "default"}},
    "sl-daily-stat-rollup":                 {"task": "smartlink.daily_stat_rollup",                "schedule": crontab(minute=5,  hour=0),       "options": {"queue": "analytics"}},
    "sl-ssl-expiry-daily":                  {"task": "smartlink.check_ssl_expiry",                 "schedule": crontab(minute=0,  hour=2),       "options": {"queue": "default"}},
    "sl-release-balances-daily":            {"task": "smartlink.release_pending_balances",         "schedule": crontab(minute=30, hour=2),       "options": {"queue": "default"}},
    "sl-cleanup-redirect-logs":             {"task": "smartlink.cleanup_old_redirect_logs",        "schedule": crontab(minute=0,  hour=3),       "options": {"queue": "maintenance"}},
    "sl-cleanup-unique-clicks":             {"task": "smartlink.cleanup_expired_unique_clicks",    "schedule": crontab(minute=20, hour=3),       "options": {"queue": "maintenance"}},
    "sl-cleanup-rotation-logs":             {"task": "smartlink.cleanup_old_rotation_logs",        "schedule": crontab(minute=40, hour=3),       "options": {"queue": "maintenance"}},
    "sl-purge-webhook-logs":                {"task": "smartlink.purge_old_webhook_logs",           "schedule": crontab(minute=0,  hour=4),       "options": {"queue": "maintenance"}},
    "sl-cleanup-bot-clicks":                {"task": "smartlink.cleanup_bot_clicks",               "schedule": crontab(minute=30, hour=4),       "options": {"queue": "maintenance"}},
    "sl-daily-publisher-reports":           {"task": "smartlink.send_daily_publisher_reports",     "schedule": crontab(minute=0,  hour=8),       "options": {"queue": "email"}},
    "sl-daily-report-emails":               {"task": "smartlink.send_daily_report_emails",         "schedule": crontab(minute=15, hour=8),       "options": {"queue": "notifications"}},
    "sl-archive-clicks-weekly":             {"task": "smartlink.archive_old_clicks",               "schedule": crontab(minute=0,  hour=4, day_of_week=0), "options": {"queue": "maintenance"}},
    "sl-publisher-tiers-weekly":            {"task": "smartlink.evaluate_publisher_tiers",         "schedule": crontab(minute=0,  hour=6, day_of_week=1), "options": {"queue": "analytics"}},
    "sl-weekly-reports":                    {"task": "smartlink.send_weekly_publisher_reports",    "schedule": crontab(minute=0,  hour=8, day_of_week=1), "options": {"queue": "email"}},
    "sl-reset-monthly-caps":                {"task": "smartlink.reset_monthly_caps",               "schedule": crontab(minute=0,  hour=0, day_of_month=1), "options": {"queue": "default"}},
})

# ==================== SMARTLINK — TASK ROUTES ====================
CELERY_TASK_ROUTES.update({
    "smartlink.process_click_async":             {"queue": "clicks"},
    "smartlink.record_bot_click":                {"queue": "clicks"},
    "smartlink.log_redirect_async":              {"queue": "clicks"},
    "smartlink.update_cap_tracker_db":           {"queue": "clicks"},
    "smartlink.attribute_conversion":            {"queue": "conversions"},
    "smartlink.hourly_stat_rollup":              {"queue": "analytics"},
    "smartlink.daily_stat_rollup":               {"queue": "analytics"},
    "smartlink.update_epc_scores":               {"queue": "analytics"},
    "smartlink.update_epc_for_smartlink":        {"queue": "analytics"},
    "smartlink.update_offer_scores":             {"queue": "analytics"},
    "smartlink.update_offer_performance_stats":  {"queue": "analytics"},
    "smartlink.build_heatmaps":                  {"queue": "analytics"},
    "smartlink.build_heatmap_for_smartlink":     {"queue": "analytics"},
    "smartlink.evaluate_ab_tests":               {"queue": "analytics"},
    "smartlink.evaluate_publisher_tiers":        {"queue": "analytics"},
    "smartlink.hourly_fraud_scan":               {"queue": "fraud"},
    "smartlink.scan_high_velocity_ips":          {"queue": "fraud"},
    "smartlink.send_daily_publisher_reports":    {"queue": "email"},
    "smartlink.send_weekly_publisher_reports":   {"queue": "email"},
    "smartlink.alert_cap_nearly_reached":        {"queue": "notifications"},
    "smartlink.send_daily_report_emails":        {"queue": "notifications"},
    "smartlink.send_payout_ready_notifications": {"queue": "notifications"},
    "smartlink.deliver_webhook_event":           {"queue": "webhooks"},
    "smartlink.retry_webhook_deliveries":        {"queue": "webhooks"},
    "smartlink.purge_old_webhook_logs":          {"queue": "maintenance"},
    "smartlink.process_payout_payment":          {"queue": "default"},
    "smartlink.process_batch_payments_async":    {"queue": "default"},
    "smartlink.release_pending_balances":        {"queue": "default"},
    "smartlink.check_smartlink_expiry":          {"queue": "default"},
    "smartlink.warmup_resolver_cache":           {"queue": "default"},
    "smartlink.invalidate_smartlink_cache":      {"queue": "default"},
    "smartlink.warmup_offer_pool_cache":         {"queue": "default"},
    "smartlink.reset_daily_caps":                {"queue": "default"},
    "smartlink.reset_monthly_caps":              {"queue": "default"},
    "smartlink.verify_pending_domains":          {"queue": "default"},
    "smartlink.check_ssl_expiry":                {"queue": "default"},
    "smartlink.process_schedules":               {"queue": "default"},
    "smartlink.update_currency_rates":           {"queue": "default"},
    "smartlink.check_broken_smartlinks":         {"queue": "maintenance"},
    "smartlink.check_smartlink_redirect_health": {"queue": "maintenance"},
    "smartlink.check_offer_pool_health":         {"queue": "default"},
    "smartlink.archive_old_clicks":              {"queue": "maintenance"},
    "smartlink.cleanup_old_redirect_logs":       {"queue": "maintenance"},
    "smartlink.cleanup_old_rotation_logs":       {"queue": "maintenance"},
    "smartlink.cleanup_bot_clicks":              {"queue": "maintenance"},
    "smartlink.cleanup_expired_unique_clicks":   {"queue": "maintenance"},
})

# ==================== SMARTLINK — LOGGING ====================
LOGGING["loggers"].update({
    "api.smartlink": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    "smartlink":     {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
})

# ==================== SMARTLINK — NAMED CACHE ====================
CACHES["smartlink"] = {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": REDIS_URL,
    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "SOCKET_CONNECT_TIMEOUT": 5, "SOCKET_TIMEOUT": 5, "RETRY_ON_TIMEOUT": True, "IGNORE_EXCEPTIONS": True},
    "KEY_PREFIX": "sl",
    "TIMEOUT": 300,
}

# ==================== REALTIME DASHBOARD — CELERY BEAT ====================
CELERY_BEAT_SCHEDULE.update({
    "rtd-cleanup-stale-connections-15min": {
        "task": "api.realtime_dashboard.tasks.cleanup_stale_connections",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "realtime_dashboard"},
    },
    "rtd-broadcast-active-metrics-30s": {
        "task": "api.realtime_dashboard.tasks.broadcast_active_metrics",
        "schedule": 30,
        "options": {"queue": "realtime_dashboard"},
    },
})

CELERY_TASK_ROUTES.update({
    "api.realtime_dashboard.tasks.cleanup_stale_connections": {"queue": "realtime_dashboard"},
    "api.realtime_dashboard.tasks.broadcast_active_metrics": {"queue": "realtime_dashboard"},
})


CACHES["version_control"] = {
    "BACKEND":   "django_redis.cache.RedisCache",
    "LOCATION":  os.environ.get("REDIS_URL", "redis://localhost:6379/3"),
    "TIMEOUT":   300,
    "KEY_PREFIX": "vc",
    "OPTIONS":   {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
}


# =============================================================================
# CMS v15 ADDITIONS
# =============================================================================

# ── INSTALLED_APPS ────────────────────────────────────────────────────────────
_CMS_APPS = ["api.cms", "api.offerwall", "api_finance"]
for _app in _CMS_APPS:
    if _app not in INSTALLED_APPS:
        INSTALLED_APPS.append(_app)

# ── MIDDLEWARE ─────────────────────────────────────────────────────────────────
_CMS_MIDDLEWARE = [
    "api.cms.middleware.MaintenanceModeMiddleware",
    "api.cms.middleware.CMSRequestTimingMiddleware",
    "api.cms.middleware.CMSSiteConfigMiddleware",
    "api.cms.middleware.CMSSecurityHeadersMiddleware",
    "api.cms.middleware.WebSocketAuthMiddleware",
    "api.cms.middleware.AnalyticsTrackingMiddleware",
    "api.cms.middleware.SurveyRateLimitMiddleware",
    "api.cms.middleware.TaskSecurityMiddleware",
    "api.cms.middleware.RewardSecurityMiddleware",
]
for _mw in _CMS_MIDDLEWARE:
    if _mw not in MIDDLEWARE:
        MIDDLEWARE.append(_mw)

# ── REST_FRAMEWORK throttle rates ─────────────────────────────────────────────
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "cms_write":        "60/minute",
    "cpalead_postback": "500/day",
    "cms_withdrawal":   "5/hour",
    "cms_quiz":         "30/hour",
    "cms_form_submit":  "20/hour",
})

# ── CMS Celery beat ───────────────────────────────────────────────────────────
try:
    from api.cms.celery_beat_config import CMS_BEAT_SCHEDULE as _cms_s
    CELERY_BEAT_SCHEDULE.update(_cms_s)
except ImportError:
    pass

# ── LOGGING ───────────────────────────────────────────────────────────────────
LOGGING["loggers"].update({
    "cms":             {"handlers": ["console"], "level": "INFO",  "propagate": False},
    "cms.integration": {"handlers": ["console"], "level": "INFO",  "propagate": False},
    "cms.exceptions":  {"handlers": ["console"], "level": "ERROR", "propagate": True},
    "offerwall":       {"handlers": ["console"], "level": "INFO",  "propagate": False},
    "api_finance":     {"handlers": ["console"], "level": "INFO",  "propagate": False},
})

# ── Elasticsearch ─────────────────────────────────────────────────────────────
ELASTICSEARCH_URL     = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_ENABLED = os.environ.get("ELASTICSEARCH_ENABLED", "False") == "True"
ELASTICSEARCH_DSL     = {"default": {"hosts": ELASTICSEARCH_URL}}

# ── Push notifications ────────────────────────────────────────────────────────
FCM_SERVER_KEY    = os.environ.get("FCM_SERVER_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")

# ── S3 Storage ────────────────────────────────────────────────────────────────
if os.environ.get("USE_S3", "False") == "True":
    DEFAULT_FILE_STORAGE    = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID       = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY   = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME", "cms-media")
    AWS_S3_REGION_NAME      = os.environ.get("AWS_REGION", "ap-southeast-1")
    AWS_S3_FILE_OVERWRITE   = False
    AWS_DEFAULT_ACL         = "private"

# ── Extra payment gateways ────────────────────────────────────────────────────
PAYPAL_CLIENT_ID        = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET    = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_SANDBOX          = os.environ.get("PAYPAL_SANDBOX", "True") == "True"
COINPAYMENTS_PUBLIC_KEY = os.environ.get("COINPAYMENTS_PUBLIC_KEY", "")
COINPAYMENTS_PRIVATE_KEY= os.environ.get("COINPAYMENTS_PRIVATE_KEY", "")
BINANCE_PAY_API_KEY     = os.environ.get("BINANCE_PAY_API_KEY", "")
BINANCE_PAY_SECRET_KEY  = os.environ.get("BINANCE_PAY_SECRET_KEY", "")

# ── CMS misc ──────────────────────────────────────────────────────────────────
CMS_OUTBOUND_WEBHOOKS = {
    "reward_earned": [], "withdrawal": [],
    "postback_approved": [], "survey_completed": [],
}
METRICS_ENABLED   = True
SEND_ERROR_ALERTS = True

# ── version_control named cache ───────────────────────────────────────────────
CACHES["version_control"] = {
    "BACKEND":   "django_redis.cache.RedisCache",
    "LOCATION":  os.environ.get("REDIS_URL", "redis://localhost:6379/3"),
    "TIMEOUT":   300,
    "KEY_PREFIX": "vc",
    "OPTIONS":   {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
}

# ── realtime_dashboard integration (appended by setup script) ────────────────
if 'api.realtime_dashboard' not in INSTALLED_APPS:
    INSTALLED_APPS.append('api.realtime_dashboard')

from celery.schedules import crontab as _rtd_crontab
CELERY_BEAT_SCHEDULE = {
    **globals().get('CELERY_BEAT_SCHEDULE', {}),
    'cleanup-stale-websocket-connections': {
        'task': 'api.realtime_dashboard.tasks.cleanup_stale_connections',
        'schedule': _rtd_crontab(minute='*/15'),
        'kwargs': {'timeout_seconds': 3600},
    },
    'broadcast-active-metrics': {
        'task': 'api.realtime_dashboard.tasks.broadcast_active_metrics',
        'schedule': 30.0,
    },
}

# Gamification encryption key (set in .env)
GAMIFICATION_ENCRYPTION_KEY = env("GAMIFICATION_ENCRYPTION_KEY", default=None)

# Messaging middleware (MessagingConfig.ready() warns when these are missing)
for _mw in (
    "api.messaging.middleware.InboxUnreadCountMiddleware",
    "api.messaging.middleware.MessagingRequestTimingMiddleware",
    "api.messaging.middleware.WebSocketRateLimitMiddleware",
):
    if _mw not in MIDDLEWARE:
        MIDDLEWARE.append(_mw)

# --- messaging periodic tasks (added 2026-10-21) ---
try:
    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
    _have = {str(v.get("task")) for v in CELERY_BEAT_SCHEDULE.values() if isinstance(v, dict)}
    CELERY_BEAT_SCHEDULE.update({k: v for k, v in MESSAGING_BEAT_SCHEDULE.items()
                                 if k not in CELERY_BEAT_SCHEDULE and str(v.get("task")) not in _have})
except Exception as _exc:  # never break settings import
    import warnings as _w
    _w.warn("messaging beat schedule not loaded: %r" % (_exc,))

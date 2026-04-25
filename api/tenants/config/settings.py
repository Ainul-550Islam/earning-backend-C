"""
Django Settings for Tenant Management System

Production-ready settings with comprehensive configuration for
multi-tenant SaaS application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'django_extensions',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
]

LOCAL_APPS = [
    'api.tenants',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'tenant_management'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'en'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
    'EXCEPTION_HANDLER': 'api.tenants.exceptions.custom_exception_handler',
}

# CORS settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Configuration
CELERY_BEAT_SCHEDULE = {
    'collect-metrics': {
        'task': 'api.tenants.tasks.metrics.collect_metrics_task',
        'schedule': 300.0,  # Every 5 minutes
    },
    'calculate-health-scores': {
        'task': 'api.tenants.tasks.analytics.calculate_health_scores_task',
        'schedule': 3600.0,  # Every hour
    },
    'send-payment-reminders': {
        'task': 'api.tenants.tasks.billing.send_payment_reminders_task',
        'schedule': 86400.0,  # Daily
    },
    'cleanup-expired-api-keys': {
        'task': 'api.tenants.tasks.security.cleanup_expired_api_keys_task',
        'schedule': 86400.0,  # Daily
    },
    'process-scheduled-notifications': {
        'task': 'api.tenants.tasks.notifications.process_scheduled_notifications_task',
        'schedule': 60.0,  # Every minute
    },
}

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400 * 7  # 7 days
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'api.tenants': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_REDIRECT_EXEMPT = []
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = 'DENY'

# Site Configuration
SITE_ID = 1

# Tenant Management Settings
TENANTS_DEFAULT_PLAN = os.getenv('TENANTS_DEFAULT_PLAN', 'basic')
TENANTS_TRIAL_DAYS = int(os.getenv('TENANTS_TRIAL_DAYS', '14'))
TENANTS_MAX_TENANTS_PER_USER = int(os.getenv('TENANTS_MAX_TENANTS_PER_USER', '10'))
TENANTS_API_KEY_LENGTH = int(os.getenv('TENANTS_API_KEY_LENGTH', '32'))
TENANTS_WEBHOOK_TIMEOUT = int(os.getenv('TENANTS_WEBHOOK_TIMEOUT', '30'))
TENANTS_AUDIT_LOG_RETENTION_DAYS = int(os.getenv('TENANTS_AUDIT_LOG_RETENTION_DAYS', '90'))

# Billing Settings
TENANTS_BILLING_ENABLED = os.getenv('TENANTS_BILLING_ENABLED', 'True') == 'True'
TENANTS_DEFAULT_CURRENCY = os.getenv('TENANTS_DEFAULT_CURRENCY', 'USD')
TENANTS_INVOICE_PREFIX = os.getenv('TENANTS_INVOICE_PREFIX', 'INV')
TENANTS_PAYMENT_REMINDER_DAYS = int(os.getenv('TENANTS_PAYMENT_REMINDER_DAYS', '7'))

# Analytics Settings
TENANTS_METRICS_RETENTION_DAYS = int(os.getenv('TENANTS_METRICS_RETENTION_DAYS', '365'))
TENANTS_HEALTH_SCORE_CALCULATION_INTERVAL = int(os.getenv('TENANTS_HEALTH_SCORE_CALCULATION_INTERVAL', '24'))
TENANTS_FEATURE_FLAG_CACHE_TIMEOUT = int(os.getenv('TENANTS_FEATURE_FLAG_CACHE_TIMEOUT', '300'))

# Security Settings
TENANTS_MAX_LOGIN_ATTEMPTS = int(os.getenv('TENANTS_MAX_LOGIN_ATTEMPTS', '5'))
TENANTS_LOGIN_ATTEMPT_TIMEOUT = int(os.getenv('TENANTS_LOGIN_ATTEMPT_TIMEOUT', '300'))
TENANTS_PASSWORD_MIN_LENGTH = int(os.getenv('TENANTS_PASSWORD_MIN_LENGTH', '8'))
TENANTS_PASSWORD_REQUIRE_UPPERCASE = os.getenv('TENANTS_PASSWORD_REQUIRE_UPPERCASE', 'True') == 'True'
TENANTS_PASSWORD_REQUIRE_LOWERCASE = os.getenv('TENANTS_PASSWORD_REQUIRE_LOWERCASE', 'True') == 'True'
TENANTS_PASSWORD_REQUIRE_NUMBERS = os.getenv('TENANTS_PASSWORD_REQUIRE_NUMBERS', 'True') == 'True'
TENANTS_PASSWORD_REQUIRE_SPECIAL = os.getenv('TENANTS_PASSWORD_REQUIRE_SPECIAL', 'True') == 'True'

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
UPLOAD_FILE_MAX_SIZE = 50 * 1024 * 1024  # 50MB

# API Rate Limiting
TENANTS_API_RATE_LIMITS = {
    'basic': {
        'per_minute': 100,
        'per_hour': 1000,
        'per_day': 10000,
    },
    'professional': {
        'per_minute': 1000,
        'per_hour': 10000,
        'per_day': 100000,
    },
    'enterprise': {
        'per_minute': 10000,
        'per_hour': 100000,
        'per_day': 1000000,
    },
}

# Development Settings
if DEBUG:
    # Disable security headers in development
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_CONTENT_TYPE_NOSNIFF = False
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    
    # Enable debug toolbar
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
        INTERNAL_IPS = ['127.0.0.1']
    except ImportError:
        pass
    
    # Enable silk for profiling
    try:
        import silk
        INSTALLED_APPS += ['silk']
        MIDDLEWARE += ['silk.middleware.SilkyMiddleware']
        SILKY_PYTHON_PROFILER_RESULT_PATH_PREFIX = '/profiling'
    except ImportError:
        pass

# Production Settings
if not DEBUG:
    # Use production database settings
    DATABASES['default'].update({
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',
        }
    })
    
    # Use production cache settings
    CACHES['default']['OPTIONS'].update({
        'SOCKET_CONNECT_TIMEOUT': 5,
        'SOCKET_TIMEOUT': 5,
        'RETRY_ON_TIMEOUT': True,
    })

# Testing Settings
if 'test' in sys.argv:
    # Use in-memory SQLite for tests
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test.db',
        }
    }
    
    # Disable migrations for tests
    class DisableMigrations:
        def __contains__(self, item):
            return True
        
        def __getitem__(self, item):
            return None
    
    MIGRATION_MODULES = DisableMigrations()
    
    # Use password hashers that don't require much CPU
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # Disable logging during tests
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'null': {
                'class': 'logging.NullHandler',
            },
        },
        'root': {
            'handlers': ['null'],
        },
    }

# Custom User Configuration
AUTH_USER_MODEL = 'auth.User'

# Admin Configuration
ADMIN_URL = os.getenv('ADMIN_URL', 'admin/')
ADMIN_TITLE = 'Tenant Management Admin'
ADMIN_HEADER = 'Tenant Management'
ADMIN_INDEX_TITLE = 'Welcome to Tenant Management Admin'

# Internationalization
LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    ('de', 'German'),
    ('zh', 'Chinese'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

# Time Zone Support
USE_TZ = True
TIME_ZONE = 'UTC'

# File Storage
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Background Tasks
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
CELERY_TASK_EAGER_PROPAGATES = True

# Health Check Configuration
HEALTH_CHECK = {
    'DISK_USAGE_MAX': 90 * (1024**3),  # 90GB
    'MEMORY_MIN': 100 * 1024 * 1024,  # 100MB
    'CPU_MAX': 90,  # 90%
}

# Monitoring and Analytics
SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False
    )

# Feature Flags
FEATURE_FLAGS = {
    'ENABLE_ANALYTICS': os.getenv('ENABLE_ANALYTICS', 'True') == 'True',
    'ENABLE_RESELLER_FEATURES': os.getenv('ENABLE_RESELLER_FEATURES', 'True') == 'True',
    'ENABLE_ADVANCED_SECURITY': os.getenv('ENABLE_ADVANCED_SECURITY', 'True') == 'True',
    'ENABLE_BULK_OPERATIONS': os.getenv('ENABLE_BULK_OPERATIONS', 'True') == 'True',
}

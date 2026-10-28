"""
alerts/settings.py — NEWLY CREATED (was completely missing)
Full Django settings for the alerts application.

Key additions over a blank settings:
  - All 4 middleware.py classes registered
  - All 4 context_processors.py functions registered
  - Celery configuration pointing to broker
  - All INSTALLED_APPS needed by the project
  - REST_FRAMEWORK config with throttling + pagination
  - Logging configured with production_logging.py

Copy to your project root as config/settings.py and adjust
DATABASE, REDIS, EMAIL, and SECRET_KEY for each environment.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'   # off unless explicitly enabled
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('Set the DJANGO_SECRET_KEY environment variable (DEBUG is off).')
    SECRET_KEY = 'insecure-development-only-key'  # only reachable with DJANGO_DEBUG=true
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# ── Installed apps ─────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',

    # Alerts app
    'api.alerts.apps.AlertsConfig',
]


# ── Middleware (including all 4 from middleware.py — previously floating) ────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Alerts middleware (was floating in middleware.py — now registered)
    'api.alerts.middleware.AlertContextMiddleware',
    'api.alerts.middleware.AlertRateLimitMiddleware',
    'api.alerts.middleware.AlertSecurityMiddleware',
    'api.alerts.middleware.AlertLoggingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'alerts' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # Alerts context processors (was floating — now registered)
                'api.alerts.context_processors.alert_counts',
                'api.alerts.context_processors.user_alerts',
                'api.alerts.context_processors.system_health',
                'api.alerts.context_processors.alert_statistics',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'alerts_db'),
        'USER': os.environ.get('DB_USER', 'alerts_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),  # no default credential
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'sslmode': 'prefer'},
    }
}


# ── Cache (Redis) ─────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
        },
        'TIMEOUT': 300,
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'


# ── Authentication ────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'api.alerts.throttling.AlertRateThrottle',
        'api.alerts.throttling.AlertCreateRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'alert_rate': '1000/hour',
        'alert_create': '100/hour',
        'notification_rate': '500/hour',
        'webhook_rate': '200/hour',
        'anon': '50/hour',
    },
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'api.alerts.pagination.AlertPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'api.alerts.exceptions.custom_exception_handler',
}


# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', f'{REDIS_URL}/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_RESULT_EXPIRES = 3600
CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_CONCURRENCY', 4))

# Task queues (matches celery.py task_routes)
CELERY_TASK_QUEUES = {
    'alerts':        {'exchange': 'alerts',        'routing_key': 'alerts'},
    'incidents':     {'exchange': 'incidents',     'routing_key': 'incidents'},
    'reporting':     {'exchange': 'reporting',     'routing_key': 'reporting'},
    'intelligence':  {'exchange': 'intelligence',  'routing_key': 'intelligence'},
    'notifications': {'exchange': 'notifications', 'routing_key': 'notifications'},
    'health':        {'exchange': 'health',        'routing_key': 'health'},
}


# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'alerts@example.com')


# ── Notification channel secrets ─────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
PAGERDUTY_API_KEY = os.environ.get('PAGERDUTY_API_KEY', '')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')


# ── Alerts-specific settings ──────────────────────────────────────────────────
ALERTS_SETTINGS = {
    'DEFAULT_COOLDOWN_MINUTES': 30,
    'DEFAULT_TIME_WINDOW_MINUTES': 15,
    'DEFAULT_THRESHOLD_VALUE': 80.0,
    'MAX_ESCALATION_LEVELS': 5,
    'MAX_RETRY_COUNT': 3,
    'WEBHOOK_TIMEOUT_SECONDS': 30,
    'BACKUP_RETENTION_DAYS': 30,
    'METRICS_RETENTION_DAYS': 90,
    'REPORT_RETENTION_DAYS': 365,
    'SEARCH_MAX_RESULTS': 1000,
    'CIRCUIT_BREAKER_FAILURE_THRESHOLD': 5,
    'CIRCUIT_BREAKER_TIMEOUT_SECONDS': 60,
    'RATE_LIMIT_REQUESTS_PER_MINUTE': 100,
    'RATE_LIMIT_REQUESTS_PER_HOUR': 1000,
}


# ── Internationalization ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ── Logging (uses production_logging.py formatters) ──────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'api.alerts.production_logging.CustomJSONFormatter',
        },
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose' if DEBUG else 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'alerts.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'alerts': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('ALERTS_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080'
).split(',')
CORS_ALLOW_CREDENTIALS = True


# ── Security (production) ─────────────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# ── Test settings ─────────────────────────────────────────────────────────────
if os.environ.get('DJANGO_ENV') == 'test':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

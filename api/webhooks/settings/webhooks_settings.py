# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook System Settings
settings/webhooks_settings.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO USE:

  আপনার main settings.py-তে শুধু এই একটি line যোগ করুন:

      from .webhooks_settings import *

  অথবা specific values import করুন:

      from .webhooks_settings import WEBHOOKS, CELERY_BEAT_SCHEDULE

  অথবা env variable দিয়ে override করুন।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRODUCTION READINESS STATUS:
  এই file-এর সব settings properly configure করলে:
  → Webhook system: 100% production ready
  → Integration system: 100% operational
  → Celery tasks: 100% scheduled
  → Security: Enterprise-grade

সবচেয়ে গুরুত্বপূর্ণ settings (⭐):
  ⭐ INSTALLED_APPS — api.webhooks যোগ করতে হবে
  ⭐ DATABASES — PostgreSQL configure করতে হবে
  ⭐ CELERY_BROKER_URL — Redis URL দিতে হবে
  ⭐ WEBHOOKS['INTEGRATION_ENABLED'] — True/False
  ⭐ WEBHOOK_MAX_RETRIES, WEBHOOK_DEFAULT_TIMEOUT
"""

import os
from datetime import timedelta

# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 1. INSTALLED_APPS — অবশ্যই এগুলো add করতে হবে
# ─────────────────────────────────────────────────────────────────────────────

WEBHOOK_REQUIRED_APPS = [
    # Django core (already in your settings — confirm these exist)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party (pip install -r requirements.txt)
    'rest_framework',           # Django REST Framework
    'django_filters',           # django-filter
    'corsheaders',              # django-cors-headers
    'django_celery_beat',       # Celery beat scheduler

    # Webhook system — এটা আপনার INSTALLED_APPS-এ add করুন
    'api.webhooks.apps.WebhooksConfig',
]
"""
আপনার settings.py-তে:

    INSTALLED_APPS = [
        ...
        'rest_framework',
        'django_filters',
        'corsheaders',
        'django_celery_beat',
        'api.webhooks.apps.WebhooksConfig',   # ← এই line add করুন
    ]
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 2. DATABASES — PostgreSQL (recommended for production)
# ─────────────────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     os.environ.get('DB_NAME',     'ainul_webhooks'),
        'USER':     os.environ.get('DB_USER',     'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'your_db_password'),
        'HOST':     os.environ.get('DB_HOST',     'localhost'),
        'PORT':     os.environ.get('DB_PORT',     '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
"""
.env file-এ রাখুন:
    DB_NAME=ainul_webhooks
    DB_USER=postgres
    DB_PASSWORD=your_secure_password
    DB_HOST=localhost
    DB_PORT=5432
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 3. CACHE — Redis (required for rate limiting + distributed lock)
# ─────────────────────────────────────────────────────────────────────────────

CACHES = {
    'default': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS':         'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT':       5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
            },
            'COMPRESSOR':           'django_redis.compressors.zlib.ZlibCompressor',
        },
        'KEY_PREFIX': 'ainul_webhooks',
        'TIMEOUT':    3600,  # 1 hour default TTL
    },

    # Separate cache for rate limiting (shorter TTL, higher throughput)
    'rate_limit': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_RATE_LIMIT_URL', 'redis://localhost:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'ainul_rl',
        'TIMEOUT':    3600,
    },

    # Session cache
    'sessions': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_SESSION_URL', 'redis://localhost:6379/3'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'ainul_sess',
        'TIMEOUT':    86400,  # 24 hours
    },
}
"""
.env file-এ রাখুন:
    REDIS_URL=redis://localhost:6379/1
    REDIS_RATE_LIMIT_URL=redis://localhost:6379/2
    REDIS_SESSION_URL=redis://localhost:6379/3
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 4. CELERY — Task queue (required for async dispatch + beat tasks)
# ─────────────────────────────────────────────────────────────────────────────

CELERY_BROKER_URL            = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND        = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT        = ['json']
CELERY_TASK_SERIALIZER       = 'json'
CELERY_RESULT_SERIALIZER     = 'json'
CELERY_TIMEZONE              = 'UTC'
CELERY_ENABLE_UTC            = True
CELERY_TASK_TRACK_STARTED    = True
CELERY_TASK_TIME_LIMIT       = 600   # 10 min hard limit per task
CELERY_TASK_SOFT_TIME_LIMIT  = 540   # 9 min soft limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_ACKS_LATE        = True  # Only ack after successful completion
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Task routing — different queues for different priority
CELERY_TASK_ROUTES = {
    'api.webhooks.tasks.*':                         {'queue': 'webhooks_core'},
    'api.webhooks.tasks.aging_tasks.*':             {'queue': 'webhooks_aging'},
    'api.webhooks.tasks.health_check_tasks.*':      {'queue': 'webhooks_health'},
    'api.webhooks.tasks.analytics_tasks.*':         {'queue': 'webhooks_analytics'},
    'api.webhooks.tasks.integration_sync_tasks.*':  {'queue': 'webhooks_integration'},
    'api.webhooks.tasks.dispatch_event.*':          {'queue': 'webhooks_dispatch'},
    'api.webhooks.tasks.retry_failed_dispatch.*':   {'queue': 'webhooks_retry'},
}

# Beat schedule — import from celery.py
from api.webhooks.celery import WEBHOOK_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {
    **WEBHOOK_BEAT_SCHEDULE,
    # আপনার অন্য beat tasks এখানে যোগ করুন
}
"""
.env file-এ রাখুন:
    CELERY_BROKER_URL=redis://localhost:6379/0
    CELERY_RESULT_BACKEND=redis://localhost:6379/0

Worker চালু করতে:
    celery -A config worker -l info -Q webhooks_core,webhooks_dispatch,webhooks_retry
    celery -A config worker -l info -Q webhooks_aging,webhooks_analytics
    celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 5. WEBHOOKS — Main configuration dict (সবচেয়ে important)
# ─────────────────────────────────────────────────────────────────────────────

WEBHOOKS = {

    # ── Core delivery settings ────────────────────────────────────────────────
    'MAX_RETRIES':              int(os.environ.get('WEBHOOK_MAX_RETRIES', 5)),
    'RETRY_DELAY':              int(os.environ.get('WEBHOOK_RETRY_DELAY', 60)),       # seconds
    'DEFAULT_TIMEOUT':          int(os.environ.get('WEBHOOK_DEFAULT_TIMEOUT', 30)),   # seconds
    'MAX_BATCH_SIZE':           int(os.environ.get('WEBHOOK_MAX_BATCH_SIZE', 1000)),
    'DEFAULT_RATE_LIMIT':       int(os.environ.get('WEBHOOK_DEFAULT_RATE_LIMIT', 1000)),  # per hour
    'MAX_PAYLOAD_SIZE':         int(os.environ.get('WEBHOOK_MAX_PAYLOAD_SIZE', 1048576)),  # 1 MB

    # ── Security settings ─────────────────────────────────────────────────────
    'SECRET_LENGTH':            int(os.environ.get('WEBHOOK_SECRET_LENGTH', 64)),
    'SECRET_GRACE_PERIOD_HOURS': int(os.environ.get('WEBHOOK_SECRET_GRACE_PERIOD', 24)),
    'MAX_OLD_SECRETS':          int(os.environ.get('WEBHOOK_MAX_OLD_SECRETS', 5)),
    'SIGNATURE_ALGORITHM':      os.environ.get('WEBHOOK_SIG_ALGO', 'sha256'),         # sha256 | sha512
    'ALLOW_HTTP':               os.environ.get('WEBHOOKS_ALLOW_HTTP', 'false').lower() == 'true',

    # ── Health monitoring ─────────────────────────────────────────────────────
    'HEALTH_CHECK_INTERVAL':    int(os.environ.get('WEBHOOK_HEALTH_INTERVAL', 3600)),  # 1 hour
    'HEALTH_TIMEOUT':           int(os.environ.get('WEBHOOK_HEALTH_TIMEOUT', 10)),
    'MAX_CONSECUTIVE_FAILURES': int(os.environ.get('WEBHOOK_MAX_FAILURES', 5)),
    'AUTO_SUSPEND_ENABLED':     os.environ.get('WEBHOOK_AUTO_SUSPEND', 'true').lower() == 'true',
    'FAILURE_THRESHOLD':        int(os.environ.get('WEBHOOK_FAILURE_THRESHOLD', 5)),
    'RECOVERY_THRESHOLD':       int(os.environ.get('WEBHOOK_RECOVERY_THRESHOLD', 3)),

    # ── Celery beat schedule overrides ────────────────────────────────────────
    'BEAT_OVERRIDES': {
        # Optional: override default schedules (in seconds or crontab)
        # 'retry_failed':   300,    # Every 5 min
        # 'health_check':   3600,   # Every 1 hour
        # 'aging_sweep':    21600,  # Every 6 hours
    },

    # ── Integration system ────────────────────────────────────────────────────
    'INTEGRATION_ENABLED':      os.environ.get('WEBHOOK_INTEGRATION_ENABLED', 'false').lower() == 'true',
    'INTEGRATION_CONFIG': {
        'enabled':              False,
        'timeout':              30,
        'max_retries':          3,
        'enable_validation':    True,
        'fallback_behavior':    'queue',      # 'queue' | 'fail' | 'skip'
        'sync_interval_hours':  6,
        'enabled_bridges':      ['erp', 'crm'],
        'enabled_adapters':     ['rest', 'grpc'],
        'enable_async':         True,
        'enable_cache_logging': True,
        'max_integrations':     100,
    },

    # ── Message queue (for INTEGRATION_SYSTEM) ────────────────────────────────
    'MESSAGE_QUEUE': {
        'enabled':          False,
        'queue_type':       'redis',          # 'redis' | 'rabbitmq' | 'kafka'
        'max_queue_size':   10000,
        'enable_dead_letter': True,
        'max_dead_letter':  1000,
        'default_queue':    'webhooks',
        'queues': [
            'webhooks',
            'webhooks_priority',
            'webhooks_bulk',
        ],
        # Redis queue config
        'redis': {
            'host':     os.environ.get('REDIS_HOST', 'localhost'),
            'port':     int(os.environ.get('REDIS_PORT', 6379)),
            'db':       int(os.environ.get('REDIS_QUEUE_DB', 4)),
            'password': os.environ.get('REDIS_PASSWORD', ''),
        },
        # RabbitMQ config (if using rabbitmq)
        'rabbitmq': {
            'host':         os.environ.get('RABBITMQ_HOST', 'localhost'),
            'port':         int(os.environ.get('RABBITMQ_PORT', 5672)),
            'username':     os.environ.get('RABBITMQ_USER', 'guest'),
            'password':     os.environ.get('RABBITMQ_PASS', 'guest'),
            'virtual_host': os.environ.get('RABBITMQ_VHOST', '/'),
        },
    },

    # ── Event bus ─────────────────────────────────────────────────────────────
    'EVENT_BUS': {
        'enabled':              False,
        'bootstrap_servers':    os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
        'enable_persistence':   True,
        'max_history':          1000,
        'enable_dead_letter':   True,
    },

    # ── Performance monitoring ────────────────────────────────────────────────
    'PERFORMANCE_CONFIG': {
        'enabled':              True,
        'stats_enabled':        True,
        'cache_results':        True,
        'cache_timeout':        300,
        'metrics_retention':    30,    # days
        'alert_on_failure':     True,
        'alert_thresholds': {
            'response_time_ms': 5000,
            'error_rate_pct':   20,
            'queue_depth':      1000,
        },
        'track_slow_queries':   True,
        'slow_query_threshold': 1000,  # ms
    },

    # ── Analytics & data retention ────────────────────────────────────────────
    'ANALYTICS_RETENTION_DAYS':  int(os.environ.get('WEBHOOK_ANALYTICS_RETENTION', 90)),
    'DELIVERY_LOG_RETENTION_DAYS': int(os.environ.get('WEBHOOK_LOG_RETENTION', 30)),
    'ENABLE_DATABASE_LOGGING':   True,
    'ENABLE_FILE_LOGGING':       False,

    # ── Aging & lifecycle ─────────────────────────────────────────────────────
    'AGING': {
        'enabled':                  True,
        'default_archive_days':     30,
        'default_purge_days':       90,
        'notification_days_before': 7,
        'auto_archive':             True,
        'auto_purge':               False,   # ⚠️ Set True only after testing
        'conflict_retention_days':  365,
    },

    # ── Inbound webhooks ──────────────────────────────────────────────────────
    'INBOUND': {
        'enabled':          True,
        'verify_signatures': True,
        'supported_sources': ['stripe', 'paypal', 'bkash', 'nagad', 'custom'],
        'max_payload_size': 1048576,  # 1 MB
        'store_raw_payload': True,
        'async_processing':  True,
    },

    # ── Caching (used by RateLimiterService + DistributedLock) ────────────────
    'CACHE': {
        'enabled':          True,
        'cache_key_prefix': 'ainul_webhooks',
        'cache_timeout':    3600,
        'enable_caching':   True,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  ⭐ 6. Individual WEBHOOK_* settings (used by services directly)
# ─────────────────────────────────────────────────────────────────────────────

# Core dispatch settings
WEBHOOK_MAX_RETRIES          = int(os.environ.get('WEBHOOK_MAX_RETRIES', 5))
WEBHOOK_RETRY_DELAY          = int(os.environ.get('WEBHOOK_RETRY_DELAY', 60))
WEBHOOK_DEFAULT_TIMEOUT      = int(os.environ.get('WEBHOOK_DEFAULT_TIMEOUT', 30))
WEBHOOK_MAX_BATCH_SIZE       = int(os.environ.get('WEBHOOK_MAX_BATCH_SIZE', 1000))
WEBHOOK_BATCH_SIZE           = int(os.environ.get('WEBHOOK_BATCH_SIZE', 100))
WEBHOOK_BATCH_TIMEOUT        = int(os.environ.get('WEBHOOK_BATCH_TIMEOUT', 300))
WEBHOOK_DEFAULT_RATE_LIMIT   = int(os.environ.get('WEBHOOK_DEFAULT_RATE_LIMIT', 1000))

# Security
WEBHOOK_SECRET_LENGTH        = int(os.environ.get('WEBHOOK_SECRET_LENGTH', 64))
WEBHOOK_SECRET_GRACE_PERIOD_HOURS = int(os.environ.get('WEBHOOK_SECRET_GRACE_PERIOD', 24))
WEBHOOK_MAX_OLD_SECRETS      = int(os.environ.get('WEBHOOK_MAX_OLD_SECRETS', 5))
WEBHOOKS_ALLOW_HTTP          = os.environ.get('WEBHOOKS_ALLOW_HTTP', 'false').lower() == 'true'

# Health monitoring
WEBHOOK_HEALTH_CHECK_INTERVAL = int(os.environ.get('WEBHOOK_HEALTH_INTERVAL', 3600))
WEBHOOK_HEALTH_TIMEOUT       = int(os.environ.get('WEBHOOK_HEALTH_TIMEOUT', 10))
WEBHOOK_MAX_CONSECUTIVE_FAILURES = int(os.environ.get('WEBHOOK_MAX_FAILURES', 5))
WEBHOOK_AUTO_SUSPEND_ENABLED = os.environ.get('WEBHOOK_AUTO_SUSPEND', 'true').lower() == 'true'

# Integration system
WEBHOOKS_INTEGRATION_CONFIG  = WEBHOOKS['INTEGRATION_CONFIG']
WEBHOOK_INTEGRATION_CONFIG   = WEBHOOKS['INTEGRATION_CONFIG']

# Individual integration bridge configs (used by INTEGRATION_SYSTEM/)
WEBHOOK_BRIDGE_CONFIG = {
    'enabled':          WEBHOOKS['INTEGRATION_ENABLED'],
    'timeout':          30,
    'max_retries':      3,
    'enable_async':     True,
    'enabled_bridges':  ['erp', 'crm'],
    'default_strategy': 'async',
}
WEBHOOK_AUTH_BRIDGE_CONFIG = {
    'enabled':          True,
    'token_expiry':     3600,
    'refresh_token_expiry': 86400,
    'default_permissions': ['read', 'write'],
    'cache_timeout':    300,
    'permission_cache_timeout': 60,
}
WEBHOOK_DATA_BRIDGE_CONFIG = {
    'enabled':          True,
    'enable_validation': True,
    'enable_compression': True,
    'enable_encryption': False,  # Set True in high-security environments
    'max_data_size':    1048576,  # 1 MB
    'encoding':         'utf-8',
}
WEBHOOK_ADAPTER_CONFIG = {
    'enabled':          True,
    'enabled_adapters': ['rest', 'grpc'],
    'default_timeout':  30,
    'max_retries':      3,
    'enable_async':     True,
    'default_resolver': 'rest',
}
WEBHOOK_REGISTRY_CONFIG = {
    'enabled':          True,
    'auto_discovery':   True,
    'max_integrations': 100,
    'cache_timeout':    300,
    'discovery_modules': [
        'api.webhooks.INTEGRATION_SYSTEM',
    ],
}
WEBHOOK_SIGNAL_CONFIG = {
    'enabled':          True,
    'enabled_signals':  ['payment', 'user', 'kyc', 'fraud', 'withdrawal', 'offer', 'wallet'],
    'enable_async':     True,
    'max_handlers':     100,
}
WEBHOOK_DATA_VALIDATOR_CONFIG = {
    'enabled':          True,
    'enabled_validators': ['schema', 'type', 'range'],
    'strict_mode':      False,
    'enable_cache_logging': True,
}
WEBHOOK_FALLBACK_CONFIG = {
    'enabled':          True,
    'enable_fallback':  True,
    'max_fallback_attempts': 3,
    'fallback_strategies': ['retry', 'queue', 'log'],
    'default_strategy': 'queue',
    'strategy_order':   ['retry', 'queue', 'log'],
}
WEBHOOK_HEALTH_CHECK_CONFIG = {
    'enabled':          True,
    'check_interval':   3600,
    'health_checks':    ['connectivity', 'authentication', 'data_flow'],
    'auto_resolve':     True,
    'alert_on_failure': True,
    'recovery_timeout': 300,
}
WEBHOOK_PERFORMANCE_MONITOR_CONFIG = {
    'enabled':          True,
    'stats_enabled':    True,
    'cache_results':    True,
    'cache_timeout':    300,
    'metrics_retention': 30,
    'track_slow_queries': True,
    'slow_query_threshold': 1000,
}
WEBHOOK_SYNC_CONFIG = {
    'enabled':          True,
    'default_interval': 3600,
    'max_conflicts':    10,
    'conflict_retention_days': 30,
    'enable_cross_module': True,
    'enable_validation': True,
}
WEBHOOK_MESSAGE_QUEUE_CONFIG  = WEBHOOKS['MESSAGE_QUEUE']
WEBHOOK_EVENT_BUS_CONFIG      = WEBHOOKS['EVENT_BUS']
WEBHOOK_AUDIT_CONFIG = {
    'enabled':          True,
    'enable_database_logging': True,
    'enable_file_logging': False,
    'log_level':        'INFO',
    'retention_days':   90,
    'max_log_size':     104857600,  # 100 MB
}

# Inbound webhook handler modules
INBOUND_WEBHOOK_HANDLER_MODULES = [
    'api.webhooks.services.inbound.InboundWebhookService',
]


# ─────────────────────────────────────────────────────────────────────────────
#  7. DJANGO REST FRAMEWORK
# ─────────────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    # BUG FIX (Session 10): TokenAuthentication must be listed BEFORE
    # SessionAuthentication. DRF picks the *first* authenticator's
    # `authenticate_header()` to decide how to report a failed auth check
    # (APIView.get_authenticate_header() / handle_exception()).
    # SessionAuthentication doesn't define one (returns None), so with the
    # old ordering *every* unauthenticated request across the whole API was
    # silently downgraded from 401 Unauthorized to 403 Forbidden — visible
    # here as `NotAuthenticated` being raised with the right "credentials
    # were not provided" message but the wrong status code. Confirmed
    # against this app's own test suite (test_aging.py / test_views.py
    # assert exactly 401) and against DRF's source
    # (rest_framework/views.py::APIView.handle_exception). TokenAuthentication
    # does define authenticate_header() (returns "Token"), so moving it
    # first restores the correct 401 for "no credentials at all" while
    # 403 is still correctly returned once a user IS authenticated but
    # lacks permission (e.g. IsAdminUser-gated endpoints).
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        # 'rest_framework_simplejwt.authentication.JWTAuthentication',  # JWT ব্যবহার করলে
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon':     '100/hour',
        'user':     '1000/hour',
        'webhook':  '5000/hour',
    },
    'EXCEPTION_HANDLER': 'api.webhooks.exceptions.webhook_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.openapi.AutoSchema',
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%SZ',
    'DATETIME_INPUT_FORMATS': ['iso-8601'],

    # BUG FIX (Session 10): this app's own test suite (test_viewsets.py,
    # test_api_coverage.py, test_missing_coverage.py — ~190 test methods)
    # posts nested dict/list payloads (e.g. `payload={...}`, `filter_config`,
    # `filters`) via `self.client.post(url, data)` with no explicit
    # `format=`. DRF's test client defaults to multipart when not told
    # otherwise, and multipart can't encode nested structures at all
    # ("Test data contained a dictionary value for key '...', but
    # multipart uploads do not support nested data" — raised before the
    # request even reaches the view). No test in this suite exercises a
    # real file upload (grepped for FileField/SimpleUploadedFile: the only
    # FileField, AdminWebhookImportSerializer.file, is only ever posted an
    # empty body in tests), so defaulting the test client to JSON is safe
    # and fixes the whole class of failures at the root instead of
    # patching each call site individually. Has no effect on production
    # request parsing — this only changes what `rest_framework.test.APIClient`
    # sends when a test doesn't specify `format=`.
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}


# ─────────────────────────────────────────────────────────────────────────────
#  8. CORS (যদি frontend আলাদা domain-এ থাকে)
# ─────────────────────────────────────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8080',
    os.environ.get('FRONTEND_URL', 'https://yourapp.com'),
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
    'x-webhook-signature', 'x-bkash-signature', 'x-nagad-signature',
    'stripe-signature',
]


# ─────────────────────────────────────────────────────────────────────────────
#  9. LOGGING — Webhook-specific loggers
# ─────────────────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style':  '{',
        },
        'webhook': {
            'format': '[{asctime}] [{levelname}] [{name}] {message}',
            'style':  '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style':  '{',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'webhook',
        },
        'webhook_file': {
            'class':       'logging.handlers.RotatingFileHandler',
            'filename':    os.environ.get('WEBHOOK_LOG_FILE', 'logs/webhooks.log'),
            'maxBytes':    104857600,   # 100 MB
            'backupCount': 5,
            'formatter':   'verbose',
        },
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        # Webhook system loggers
        'ainul.webhooks': {
            'handlers':  ['console', 'webhook_file'],
            'level':     os.environ.get('WEBHOOK_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'ainul.webhooks.dispatch': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        'ainul.webhooks.signature': {
            'handlers':  ['console'],
            'level':     'WARNING',
            'propagate': True,
        },
        'ainul.webhooks.aging': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        'ainul.webhooks.tasks': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        'ainul.webhooks.integration': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        'ainul.webhooks.inbound_receiver': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        'ainul.webhooks.signals': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': True,
        },
        # Celery
        'celery': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers':  ['console'],
            'level':     'INFO',
            'propagate': False,
        },
        # Django
        'django': {
            'handlers':  ['console'],
            'level':     'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level':    'WARNING',
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  10. MIDDLEWARE — Required middleware order
# ─────────────────────────────────────────────────────────────────────────────

WEBHOOK_REQUIRED_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',              # CORS — প্রথমে রাখুন
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
"""
আপনার settings.py MIDDLEWARE list-এ exactly এই order মানুন।
CorsMiddleware অবশ্যই SecurityMiddleware-এর পরে রাখুন।
"""


# ─────────────────────────────────────────────────────────────────────────────
#  11. SECURITY SETTINGS (production-এ)
# ─────────────────────────────────────────────────────────────────────────────

# Production security (DEBUG=False হলে এগুলো active করুন)
if not os.environ.get('DEBUG', 'false').lower() == 'true':
    SECURE_SSL_REDIRECT             = True
    SECURE_HSTS_SECONDS             = 31536000   # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
    SECURE_HSTS_PRELOAD             = True
    SECURE_CONTENT_TYPE_NOSNIFF     = True
    SECURE_BROWSER_XSS_FILTER       = True
    SESSION_COOKIE_SECURE           = True
    CSRF_COOKIE_SECURE              = True
    X_FRAME_OPTIONS                 = 'DENY'
else:
    WEBHOOKS_ALLOW_HTTP = True   # Dev-এ HTTP allow করা


# ─────────────────────────────────────────────────────────────────────────────
#  12. URL CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

WEBHOOK_URL_PREFIX = os.environ.get('WEBHOOK_URL_PREFIX', 'api/webhooks')
"""
আপনার main urls.py-তে add করুন:

    from django.urls import path, include

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('api/webhooks/', include('api.webhooks.urls', namespace='webhooks')),
        # অন্য apps...
    ]
"""


# ─────────────────────────────────────────────────────────────────────────────
#  13. STATIC & MEDIA (যদি admin ব্যবহার করেন)
# ─────────────────────────────────────────────────────────────────────────────

STATIC_URL    = '/static/'
STATIC_ROOT   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'staticfiles')
MEDIA_URL     = '/media/'
MEDIA_ROOT    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media')


# ─────────────────────────────────────────────────────────────────────────────
#  14. EMAIL (alerts এর জন্য)
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL  = os.environ.get('DEFAULT_FROM_EMAIL', 'webhooks@yourapp.com')
ADMINS              = [('Webhook Admin', os.environ.get('ADMIN_EMAIL', 'admin@yourapp.com'))]


# ─────────────────────────────────────────────────────────────────────────────
#  15. SENTRY (production error tracking)
# ─────────────────────────────────────────────────────────────────────────────

SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style='url'),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=os.environ.get('ENVIRONMENT', 'production'),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  📋 .env TEMPLATE — সব environment variables একসাথে
# ─────────────────────────────────────────────────────────────────────────────
"""
আপনার .env file-এ এই variables রাখুন:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Django
SECRET_KEY=your-super-secret-key-minimum-50-chars
DEBUG=false
ALLOWED_HOSTS=yourapp.com,www.yourapp.com
ENVIRONMENT=production

# Database (PostgreSQL)
DB_NAME=ainul_webhooks
DB_USER=postgres
DB_PASSWORD=your_secure_db_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/1
REDIS_RATE_LIMIT_URL=redis://localhost:6379/2
REDIS_SESSION_URL=redis://localhost:6379/3
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_QUEUE_DB=4

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Webhook core settings
WEBHOOK_MAX_RETRIES=5
WEBHOOK_RETRY_DELAY=60
WEBHOOK_DEFAULT_TIMEOUT=30
WEBHOOK_MAX_BATCH_SIZE=1000
WEBHOOK_BATCH_SIZE=100
WEBHOOK_SECRET_LENGTH=64
WEBHOOK_SECRET_GRACE_PERIOD=24
WEBHOOK_MAX_OLD_SECRETS=5
WEBHOOK_DEFAULT_RATE_LIMIT=1000
WEBHOOK_LOG_LEVEL=INFO
WEBHOOK_LOG_FILE=logs/webhooks.log

# Security
WEBHOOKS_ALLOW_HTTP=false
WEBHOOK_MAX_FAILURES=5
WEBHOOK_AUTO_SUSPEND=true
WEBHOOK_HEALTH_INTERVAL=3600
WEBHOOK_HEALTH_TIMEOUT=10

# Integration (enable করতে true করুন)
WEBHOOK_INTEGRATION_ENABLED=false

# Frontend URL
FRONTEND_URL=https://yourapp.com

# Email (alerts এর জন্য)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=webhooks@yourapp.com
ADMIN_EMAIL=admin@yourapp.com

# Sentry (optional)
SENTRY_DSN=https://your@sentry.io/project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

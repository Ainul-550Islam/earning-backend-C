"""
settings_telemetry_additions.py
────────────────────────────────
Copy these blocks into your main settings file.
Check each one — skip anything already configured.

Usage:
    # At the bottom of your settings file:
    from api.telemetry_observability.integration.settings_additions import *
    # OR copy-paste the blocks you need directly.
"""
import os
from datetime import timedelta

# ── INSTALLED_APPS addition ───────────────────────────────────────────────────
# Add to your INSTALLED_APPS list:
#   'api.telemetry_observability',

# ── MIDDLEWARE addition ───────────────────────────────────────────────────────
# Add after SecurityMiddleware and SessionMiddleware:
#   'api.telemetry_observability.middleware.TelemetryMiddleware',

# ── Cache (django-redis) ──────────────────────────────────────────────────────
# SKIP if you already have CACHES configured with django_redis.cache.RedisCache.
# REQUIRED if you want cache.delete_pattern() to work in Celery tasks.
CACHES = {
    'default': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS':  {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'MAX_ENTRIES':  10000,
        },
    }
}

# ── JWT ───────────────────────────────────────────────────────────────────────
# SKIP if SIMPLE_JWT already configured in your project.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':    timedelta(minutes=int(os.environ.get('JWT_ACCESS_MINUTES', 60))),
    'REFRESH_TOKEN_LIFETIME':   timedelta(days=int(os.environ.get('JWT_REFRESH_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS':    True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM':                'HS256',
    'AUTH_HEADER_TYPES':        ('Bearer',),
}

# Add JWTAuthentication to REST_FRAMEWORK (MERGE — don't replace the whole dict):
# REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].insert(0,
#     'rest_framework_simplejwt.authentication.JWTAuthentication'
# )

# ── Telemetry settings ────────────────────────────────────────────────────────
TELEMETRY_RETENTION_DAYS    = int(os.environ.get('TELEMETRY_RETENTION_DAYS', 90))
TELEMETRY_WEBHOOK_URLS      = [
    u for u in os.environ.get('TELEMETRY_WEBHOOK_URLS', '').split(',') if u
]
TELEMETRY_WEBHOOK_SECRET    = os.environ.get('TELEMETRY_WEBHOOK_SECRET', '')
TELEMETRY_WEBHOOK_TIMEOUT   = int(os.environ.get('TELEMETRY_WEBHOOK_TIMEOUT', 5))
TELEMETRY_WEBHOOK_MAX_RETRIES = int(os.environ.get('TELEMETRY_WEBHOOK_MAX_RETRIES', 2))

# ── Internet check ────────────────────────────────────────────────────────────
INTERNET_CHECK_PASS_THRESHOLD  = float(os.environ.get('INTERNET_CHECK_PASS_THRESHOLD', 0.5))
INTERNET_CHECK_TIMEOUT         = int(os.environ.get('INTERNET_CHECK_TIMEOUT', 5))
INTERNET_CHECK_ENVIRONMENT     = os.environ.get('INTERNET_CHECK_ENVIRONMENT',
                                  os.environ.get('DJANGO_ENV', 'production'))

# ── App version ───────────────────────────────────────────────────────────────
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')

# ── Sentry ────────────────────────────────────────────────────────────────────
# SKIP if sentry_sdk.init() is already called in your project.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis  import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style='url'),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
        ],
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', 0.10)),
        release=os.environ.get('APP_VERSION', '1.0.0'),
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        send_default_pii=False,
    )

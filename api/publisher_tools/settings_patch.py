# earning_backend/settings_patch.py
"""
Production settings additions for publisher_tools।

এই ফাইলটি earning_backend/settings.py-এর শেষে paste করো
অথবা settings.py-এর bottom-এ import করো:

    from .settings_patch import *   # noqa

অথবা প্রতিটি section আলাদাভাবে merge করো।

Sections:
  1. Celery Beat Schedule     — 20 publisher_tools tasks wired
  2. DRF Throttling           — rate limits per endpoint type
  3. Middleware               — PublisherContextMiddleware registered
  4. Caching                  — Redis cache config for analytics
  5. Celery Queues            — dedicated queues per task type
  6. File Storage             — KYC/brand image upload settings
  7. Logging                  — per-module log levels
"""

import os

# ──────────────────────────────────────────────────────────────────────────────
# 1. CELERY BEAT SCHEDULE
# ──────────────────────────────────────────────────────────────────────────────

from publisher_tools.celery_beat_schedule import PUBLISHER_TOOLS_BEAT_SCHEDULE

CELERY_BEAT_SCHEDULE = {
    **PUBLISHER_TOOLS_BEAT_SCHEDULE,
    # অন্য app-এর schedules এখানে:
    # **OTHER_APP_BEAT_SCHEDULE,
}

# Celery timezone must match Django TIME_ZONE
CELERY_TIMEZONE = 'Asia/Dhaka'
DJANGO_CELERY_BEAT_TZ_AWARE = False


# ──────────────────────────────────────────────────────────────────────────────
# 2. DRF THROTTLING
# ──────────────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    # Keep your existing DRF settings and add these:
    'DEFAULT_THROTTLE_CLASSES': [
        'publisher_tools.throttling.PublisherBurstThrottle',
        'publisher_tools.throttling.PublisherSustainedThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'publisher_burst':      '60/min',
        'publisher_sustained':  '1000/hour',
        'fraud_check':          '30/min',
        'payout_submit':        '5/min',
        'kyc_submit':           '3/min',
        'export':               '10/hour',
        'webhook_replay':       '20/min',
        'admin_tools':          '300/min',
        'anon':                 '20/min',
    },
    # Existing settings to keep:
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        # 'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. MIDDLEWARE
# ──────────────────────────────────────────────────────────────────────────────
# publisher_tools/middleware.py এর PublisherContextMiddleware register করো।
# MIDDLEWARE list-এ SessionMiddleware-এর পরে যোগ করো:

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # ── publisher_tools middleware ──
    'publisher_tools.middleware.PublisherContextMiddleware',
    'publisher_tools.middleware.PublisherRateLimitMiddleware',
]


# ──────────────────────────────────────────────────────────────────────────────
# 4. CACHING — Redis-backed cache for analytics queries
# ──────────────────────────────────────────────────────────────────────────────

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CACHES = {
    'default': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS':      'django_redis.client.DefaultClient',
            'COMPRESSOR':        'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,   # Redis down → cache miss, not 500
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'pt',     # publisher_tools prefix
        'TIMEOUT':    300,      # 5 minute default TTL
    },
    # Separate cache for session data (no compression needed)
    'session': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_SESSION_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
        'KEY_PREFIX': 'sess',
        'TIMEOUT':    86400,    # 1 day
    },
}

# Cache TTLs per analytics endpoint (seconds)
PUBLISHER_TOOLS_CACHE_TTL = {
    'live_stats':          60,       # 1 minute  (real-time)
    'dashboard_summary':   300,      # 5 minutes
    'monthly_report':      3600,     # 1 hour
    'revenue_forecast':    1800,     # 30 minutes
    'ecpm_breakdown':      900,      # 15 minutes
    'top_units':           600,      # 10 minutes
    'fraud_report':        1800,     # 30 minutes
    'payout_eligibility':  120,      # 2 minutes
}


# ──────────────────────────────────────────────────────────────────────────────
# 5. CELERY QUEUES
# ──────────────────────────────────────────────────────────────────────────────

from kombu import Exchange, Queue

CELERY_TASK_QUEUES = (
    Queue('default',       Exchange('default'),       routing_key='default'),
    Queue('earnings',      Exchange('earnings'),      routing_key='earnings'),
    Queue('invoices',      Exchange('invoices'),      routing_key='invoices'),
    Queue('payouts',       Exchange('payouts'),       routing_key='payouts'),
    Queue('fraud',         Exchange('fraud'),         routing_key='fraud'),
    Queue('site_quality',  Exchange('site_quality'),  routing_key='site_quality'),
    Queue('optimization',  Exchange('optimization'),  routing_key='optimization'),
    Queue('webhooks',      Exchange('webhooks'),      routing_key='webhooks'),
    Queue('analytics',     Exchange('analytics'),     routing_key='analytics'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications'),
    Queue('maintenance',   Exchange('maintenance'),   routing_key='maintenance'),
)

CELERY_TASK_DEFAULT_QUEUE    = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'

CELERY_TASK_ROUTES = {
    # Earnings
    'publisher_tools.tasks.aggregate_hourly_earnings':               {'queue': 'earnings'},
    'publisher_tools.tasks.finalize_daily_earnings':                  {'queue': 'earnings'},
    'publisher_tools.tasks.finalize_previous_month_earnings':         {'queue': 'earnings'},
    'publisher_tools.tasks.update_publisher_revenue_totals':          {'queue': 'earnings'},
    'publisher_tools.tasks.update_publisher_performance_snapshots':   {'queue': 'earnings'},
    # Invoices
    'publisher_tools.tasks.generate_monthly_invoices':                {'queue': 'invoices'},
    'publisher_tools.tasks.send_overdue_invoice_reminders':           {'queue': 'invoices'},
    'publisher_tools.tasks.generate_monthly_report_data':             {'queue': 'invoices'},
    # Payouts
    'publisher_tools.tasks.process_automatic_payouts':                {'queue': 'payouts'},
    # Fraud
    'publisher_tools.tasks.scan_invalid_traffic':                     {'queue': 'fraud'},
    'publisher_tools.tasks.detect_fraud_patterns':                    {'queue': 'fraud'},
    'publisher_tools.tasks.refresh_publisher_fraud_scores':           {'queue': 'fraud'},
    # Site Quality
    'publisher_tools.tasks.check_all_ads_txt':                        {'queue': 'site_quality'},
    'publisher_tools.tasks.update_site_quality_metrics':              {'queue': 'site_quality'},
    'publisher_tools.tasks.recalculate_site_quality_metrics':         {'queue': 'site_quality'},
    # Optimization
    'publisher_tools.tasks.auto_optimize_waterfalls':                 {'queue': 'optimization'},
    # Webhooks
    'publisher_tools.tasks.retry_failed_webhook_deliveries':          {'queue': 'webhooks'},
    'publisher_tools.tasks.cleanup_old_webhook_logs':                 {'queue': 'webhooks'},
    # Analytics
    'publisher_tools.tasks.evaluate_ab_tests':                        {'queue': 'analytics'},
    # Notifications
    'publisher_tools.tasks.send_publisher_welcome_notification':      {'queue': 'notifications'},
    'publisher_tools.tasks.send_publisher_approved_notification':     {'queue': 'notifications'},
    'publisher_tools.tasks.notify_subscription_renewals':             {'queue': 'notifications'},
    # Maintenance
    'publisher_tools.tasks.cleanup_old_traffic_logs':                 {'queue': 'maintenance'},
    'publisher_tools.tasks.cleanup_expired_velocity_records':         {'queue': 'maintenance'},
    'publisher_tools.tasks.expire_kyc_records':                       {'queue': 'maintenance'},
}

CELERY_TASK_SERIALIZER    = 'json'
CELERY_RESULT_SERIALIZER  = 'json'
CELERY_ACCEPT_CONTENT     = ['json']
CELERY_RESULT_EXPIRES     = 60 * 60 * 24   # 24 hours


# ──────────────────────────────────────────────────────────────────────────────
# 6. FILE STORAGE (KYC documents, brand images)
# ──────────────────────────────────────────────────────────────────────────────

MEDIA_URL  = '/media/'
MEDIA_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'media')

# KYC document upload size limit: 10 MB
KYC_DOCUMENT_MAX_SIZE_MB = 10

# Allowed KYC document MIME types
KYC_ALLOWED_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
]

# Brand image max size: 2 MB
BRAND_IMAGE_MAX_SIZE_MB = 2


# ──────────────────────────────────────────────────────────────────────────────
# 7. LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style':  '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style':  '{',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level':    'WARNING',
    },
    'loggers': {
        'publisher_tools': {
            'handlers': ['console'],
            'level':    os.environ.get('PUBLISHER_TOOLS_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'publisher_tools.tasks': {
            'handlers': ['console'],
            'level':    'INFO',
            'propagate': False,
        },
        'publisher_tools.fraud_prevention': {
            'handlers': ['console'],
            'level':    'WARNING',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level':    'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level':    'ERROR',   # Set to DEBUG locally to see SQL
            'propagate': False,
        },
    },
}

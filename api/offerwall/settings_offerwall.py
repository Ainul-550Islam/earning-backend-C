"""
api/offerwall/settings_offerwall.py

App-specific configuration for offerwall module.
Usage in main settings.py:
    from api.offerwall.settings_offerwall import *
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update(THROTTLE_RATES)
"""
from decimal import Decimal

# ─────────────────────────────────────────────────────────────
# OFFERWALL MODULE CONFIGURATION
# ─────────────────────────────────────────────────────────────

OFFERWALL_CONFIG = {
    'AUTO_APPROVE_CONVERSIONS':          False,
    'FRAUD_DETECTION_ENABLED':           True,
    'WEBHOOK_SIGNATURE_VERIFICATION':    True,
    'RATE_LIMITING_ENABLED':             True,
    'FRAUD_SETTINGS': {
        'MAX_CLICKS_PER_HOUR':                   30,
        'MAX_CONVERSIONS_PER_DAY':               10,
        'DUPLICATE_CONVERSION_WINDOW_MINUTES':    5,
        'VPN_DETECTION_ENABLED':                 True,
        'MULTI_ACCOUNT_DETECTION_ENABLED':        True,
        'CLICK_FRAUD_THRESHOLD':                 0.7,
    },
    'MIN_QUALITY_SCORE':             50,
    'MAX_OFFERS_PER_PAGE':           50,
    'DEFAULT_OFFERS_PER_PAGE':       20,
    'MIN_PAYOUT_THRESHOLD':          Decimal('0.10'),
    'MAX_PAYOUT_PERCENTAGE':         Decimal('99.00'),
    'DEFAULT_REVENUE_SHARE':         Decimal('70.00'),
    'DEFAULT_CURRENCY':              'USD',
    'CONVERSION_CURRENCY':           'USD',
    'PAYOUT_CURRENCY':               'USD',
    'PROVIDER_RATE_LIMITS': {
        'offers_sync_per_hour':        100,
        'conversions_per_hour':        1000,
        'webhook_requests_per_hour':   1000,
    },
    'CACHE_OFFERS_MINUTES':          15,
    'CACHE_PROVIDER_MINUTES':        30,
    'CACHE_USER_OFFERS_MINUTES':      5,
    'WEBHOOK_TIMEOUT_SECONDS':       10,
    'WEBHOOK_RETRY_ATTEMPTS':         3,
    'WEBHOOK_RETRY_BACKOFF_MINUTES': [1, 5, 15],
    'EMBED_TOKEN_EXPIRY_HOURS':      24,
    'EMBED_TOKEN_LENGTH':            32,
    'PUBLISHER_EARNINGS_MINIMUM_PAYOUT': Decimal('5.00'),
    'PUBLISHER_PAYOUT_FREQUENCY':    'weekly',
    'CHARGEBACK_WINDOW_DAYS':        90,
    'CHARGEBACK_AUTO_REVERSE':       True,
    'EXPORT_MAX_ROWS':               100000,
    'EXPORT_BATCH_SIZE':             1000,
    'EXPORT_FORMATS':                ['csv', 'xlsx', 'json'],
}

# ─────────────────────────────────────────────────────────────
# DRF CONFIGURATION
# ─────────────────────────────────────────────────────────────

REST_FRAMEWORK_OFFERWALL = {
    'DEFAULT_PAGINATION_CLASS': 'api.offerwall.pagination.StandardPagination',
    'DEFAULT_FILTER_BACKENDS': [
        'api.offerwall.filters.OfferFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'api.offerwall.throttling.OfferListThrottle',
        'api.offerwall.throttling.PublicThrottle',
    ],
}

THROTTLE_RATES = {
    'offer_list':   '100/hour',
    'offer_detail': '200/hour',
    'offer_click':  '30/hour',
    'conversion':   '10/hour',
    'webhook':      '1000/hour',
    'analytics':    '50/hour',
    'admin':        '500/hour',
    'public':       '50/hour',
}

# ─────────────────────────────────────────────────────────────
# CELERY
# ─────────────────────────────────────────────────────────────

CELERY_BEAT_SCHEDULE_OFFERWALL = {
    'sync-all-offers':            {'task': 'api.offerwall.tasks.sync_offers_task',                'schedule': 3600},
    'expire-offers':              {'task': 'api.offerwall.tasks.expire_offers_task',               'schedule': 1800},
    'check-pending-conversions':  {'task': 'api.offerwall.tasks.check_pending_conversions_task',   'schedule': 900},
    'cleanup-fraud-logs':         {'task': 'api.offerwall.tasks.cleanup_fraud_logs_task',          'schedule': 86400},
    'aggregate-analytics':        {'task': 'api.offerwall.tasks.aggregate_analytics_task',         'schedule': 3600},
}

CELERY_TASK_ROUTES_OFFERWALL = {
    'api.offerwall.tasks.sync_offers_task':               {'queue': 'offerwall_sync'},
    'api.offerwall.tasks.process_webhook_task':           {'queue': 'offerwall_webhooks'},
    'api.offerwall.tasks.check_pending_conversions_task': {'queue': 'offerwall_conversions'},
    'api.offerwall.tasks.cleanup_fraud_logs_task':        {'queue': 'offerwall_cleanup'},
}

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

LOGGING_OFFERWALL = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'level': 'INFO', 'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'api.offerwall':          {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'api.offerwall.webhooks': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}

INSTALLED_APPS_OFFERWALL = ['api.offerwall']

__all__ = [
    'OFFERWALL_CONFIG',
    'REST_FRAMEWORK_OFFERWALL',
    'THROTTLE_RATES',
    'CELERY_BEAT_SCHEDULE_OFFERWALL',
    'CELERY_TASK_ROUTES_OFFERWALL',
    'LOGGING_OFFERWALL',
    'INSTALLED_APPS_OFFERWALL',
]

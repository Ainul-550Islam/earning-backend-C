# api/djoyalty/settings_snippet.py
"""
Django settings snippet for Djoyalty integration।
এই settings গুলো আপনার project এর settings.py তে যোগ করুন।
"""

# ==================== INSTALLED APPS ====================
DJOYALTY_APPS = [
    'api.djoyalty',
    # Optional but recommended:
    # 'drf_spectacular',       # pip install drf-spectacular
    # 'django_filters',        # pip install django-filter
    # 'corsheaders',           # pip install django-cors-headers
]

# ==================== DRF SETTINGS ====================
REST_FRAMEWORK_DJOYALTY = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'api.djoyalty.throttles.DjoyaltyUserThrottle',
        'api.djoyalty.throttles.DjoyaltyAnonThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'djoyalty_user': '1000/hour',
        'djoyalty_anon': '100/hour',
        'djoyalty_burst': '60/minute',
        'djoyalty_earn': '200/hour',
        'djoyalty_redeem': '20/hour',
        'djoyalty_public': '500/hour',
        'djoyalty_voucher_validate': '30/minute',
        'djoyalty_webhook': '100/minute',
        'djoyalty_admin': '50/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'api.djoyalty.pagination.DjoyaltyPagePagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'api.djoyalty.exception_handler.djoyalty_exception_handler',
    'DEFAULT_RENDERER_CLASSES': [
        'api.djoyalty.renderers.DjoyaltyJSONRenderer',
    ],
}

# ==================== MIDDLEWARE ====================
DJOYALTY_MIDDLEWARE = [
    'api.djoyalty.middleware.DjoyaltySecurityMiddleware',
    'api.djoyalty.middleware.DjoyaltyRequestMiddleware',
    'api.djoyalty.middleware.DjoyaltyAPIVersionMiddleware',
]

# ==================== CACHE (Redis) ====================
CACHES_DJOYALTY = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'MAX_CONNECTIONS': 1000,
            'COMPRESS_MIN_LEN': 10,
        },
        'KEY_PREFIX': 'djoyalty',
        'TIMEOUT': 300,
    }
}

# ==================== CELERY ====================
CELERY_DJOYALTY = {
    'CELERY_BROKER_URL': 'redis://127.0.0.1:6379/0',
    'CELERY_RESULT_BACKEND': 'redis://127.0.0.1:6379/0',
    'CELERY_ACCEPT_CONTENT': ['json'],
    'CELERY_TASK_SERIALIZER': 'json',
    'CELERY_RESULT_SERIALIZER': 'json',
    'CELERY_TIMEZONE': 'UTC',
    'CELERY_BEAT_SCHEDULER': 'django_celery_beat.schedulers:DatabaseScheduler',
    'CELERY_TASK_ALWAYS_EAGER': False,
    'CELERY_TASK_ACKS_LATE': True,
    'CELERY_WORKER_PREFETCH_MULTIPLIER': 1,
}

# ==================== LOGGING ====================
LOGGING_DJOYALTY = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'djoyalty_json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
        'djoyalty_simple': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        },
    },
    'handlers': {
        'djoyalty_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'djoyalty_simple',
        },
        'djoyalty_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/djoyalty.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'djoyalty_json',
        },
        'djoyalty_audit_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/djoyalty_audit.log',
            'maxBytes': 50 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'djoyalty_json',
        },
    },
    'loggers': {
        'djoyalty': {
            'handlers': ['djoyalty_console', 'djoyalty_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'djoyalty.audit.structured': {
            'handlers': ['djoyalty_audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'djoyalty.middleware': {
            'handlers': ['djoyalty_console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ==================== SPECTACULAR (OpenAPI) ====================
SPECTACULAR_SETTINGS_DJOYALTY = {
    'TITLE': 'Djoyalty API',
    'DESCRIPTION': 'World-class Django Loyalty System',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'api.djoyalty.openapi.djoyalty_postprocessing_hook',
    ],
}

# ==================== SENTRY ====================
def configure_sentry(dsn: str, environment: str = 'production'):
    """
    Sentry error tracking setup।
    pip install sentry-sdk
    """
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[
                DjangoIntegration(transaction_style='url'),
                CeleryIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=0.1,
            send_default_pii=False,
            before_send=_before_send_sentry,
        )
    except ImportError:
        pass


def _before_send_sentry(event, hint):
    """Filter out non-critical Djoyalty errors from Sentry।"""
    from .exceptions import (
        InsufficientPointsError, VoucherExpiredError,
        VoucherAlreadyUsedError, RedemptionMinimumNotMetError,
    )
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        # These are expected user errors — don't send to Sentry
        if isinstance(exc_value, (
            InsufficientPointsError, VoucherExpiredError,
            VoucherAlreadyUsedError, RedemptionMinimumNotMetError,
        )):
            return None
    return event

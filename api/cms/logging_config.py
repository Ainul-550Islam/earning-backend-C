# api/cms/logging_config.py
"""
CMS Structured Logging Configuration.
Import in settings.py: from api.cms.logging_config import CMS_LOGGING
Then: LOGGING = CMS_LOGGING
"""

CMS_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} pid={process:d} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '{levelname} {name}: {message}',
            'style': '{',
        },
        'json': {
            # Enable if python-json-logger installed: pip install python-json-logger
            'format': '[{asctime}] {levelname} {name} {process:d}: {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'DEBUG',
        },
        'console_simple': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_app': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/cms_app.log',
            'maxBytes': 10 * 1024 * 1024,   # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'file_security': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/cms_security.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'level': 'WARNING',
        },
        'file_celery': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/cms_celery.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'mail_admins': {
            'level': 'CRITICAL',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'formatter': 'verbose',
        },
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'loggers': {
        # Django core
        'django': {
            'handlers': ['console', 'file_app'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_security', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_app', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        # CMS modules
        'cms': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms.services_new': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms.INTEGRATION_SYSTEM': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms.exceptions': {
            'handlers': ['file_security'],
            'level': 'ERROR',
            'propagate': True,
        },
        'cms.sanctions': {
            'handlers': ['file_security', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'cms.monitoring': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        # Celery
        'celery': {
            'handlers': ['console', 'file_celery'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['file_celery'],
            'level': 'INFO',
            'propagate': False,
        },
        # Third-party
        'channels': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'redis': {
            'handlers': ['null'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Root logger
        '': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}

# Development override — more verbose
CMS_LOGGING_DEV = dict(CMS_LOGGING)
CMS_LOGGING_DEV['loggers'] = dict(CMS_LOGGING_DEV['loggers'])
CMS_LOGGING_DEV['loggers']['cms'] = {
    'handlers': ['console'],
    'level': 'DEBUG',
    'propagate': False,
}

LOGGING = CMS_LOGGING  # Default export

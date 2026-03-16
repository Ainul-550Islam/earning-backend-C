# config/settings/test.py
# Test এর জন্য আলাদা settings

from .base import *  # noqa

# ==================== CELERY ====================
# Test এ Celery task গুলো sync এ run হবে (Redis লাগবে না)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# ==================== CACHE ====================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# ==================== EMAIL ====================
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ==================== PASSWORD HASHERS ====================
# Test দ্রুত করতে simple hasher
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# ==================== LOGGING ====================
# Test এ কম log দেখাবে
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
    },
}
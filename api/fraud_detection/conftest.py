# conftest.py - Place this at the Django project root (one level above fraud_detection/)
import django
from django.conf import settings


def pytest_configure():
    settings.configure(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'fraud_detection_test',
                'USER': 'postgres',
                'PASSWORD': 'postgres',
                'HOST': 'localhost',
                'PORT': '5432',
                'TEST': {
                    'NAME': 'test_fraud_detection',
                },
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'django.contrib.admin',
            'rest_framework',
            'django_filters',
            'channels',
            'api.fraud_detection',
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        SECRET_KEY='test-secret-key-not-for-production',
        USE_TZ=True,
        TIME_ZONE='UTC',
        CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            }
        },
        CHANNEL_LAYERS={
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            }
        },
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
            'DEFAULT_PERMISSION_CLASSES': [
                'rest_framework.permissions.IsAuthenticated',
            ],
            'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
            'PAGE_SIZE': 20,
        },
        FRAUD_DETECTION={
            'ENABLED': True,
            'AUTO_BAN_THRESHOLD': 90,
            'RISK_SCORE_THRESHOLD': 70,
        },
        LOGGING={
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                },
            },
            'root': {
                'handlers': ['console'],
                'level': 'WARNING',
            },
        },
    )

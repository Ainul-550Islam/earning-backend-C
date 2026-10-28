# engagement/conftest.py — COMPLETE 100%
import pytest
from django.conf import settings


def pytest_configure(config):
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY="test-secret-key-engagement-world-1-complete",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME":   ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.admin",
                "django.contrib.sessions",
                "rest_framework",
                "tenants",
                "engagement",
            ],
            AUTH_USER_MODEL="auth.User",
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            REST_FRAMEWORK={
                "DEFAULT_AUTHENTICATION_CLASSES": [
                    "rest_framework.authentication.SessionAuthentication",
                ],
                "DEFAULT_PERMISSION_CLASSES": [
                    "rest_framework.permissions.IsAuthenticated",
                ],
                "DEFAULT_THROTTLE_RATES": {
                    "checkin":       "100/min",
                    "spin":          "100/min",
                    "shop_purchase": "100/min",
                    "leaderboard":   "100/min",
                },
            },
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                }
            },
            CELERY_TASK_ALWAYS_EAGER=True,
            CELERY_TASK_EAGER_PROPAGATES=True,
            FIREBASE_CREDENTIALS_PATH=None,
            USE_TZ=True,
            TIME_ZONE="UTC",
        )

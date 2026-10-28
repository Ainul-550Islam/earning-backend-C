# cms_patched/settings_production_additions.py
"""
Production Settings Additions — Part 7

Patch to add to settings_production.py:

1. REST_FRAMEWORK exception handler
2. MetricsMiddleware
3. MobileOptimizationMiddleware
4. Celery Beat schedule (all 7 batch jobs)
5. django-filter backend
6. drf-spectacular schema settings
7. CORS & security headers
8. Cache configuration
"""

# ─────────────────────────────────────────────────────────────────────────────
# HOW TO APPLY
# ─────────────────────────────────────────────────────────────────────────────
# Copy-paste each section into your settings_production.py
# or import this file at the bottom of settings_production.py:
#
#   from settings_production_additions import *
#
# ─────────────────────────────────────────────────────────────────────────────

# ── 1. REST FRAMEWORK ────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # Use custom exception handler (Part 3 File 12)
    'EXCEPTION_HANDLER': 'cms.exceptions.custom_exception_handler',

    # Default authentication
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],

    # Default permission
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],

    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,

    # Filtering
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],

    # Throttling
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },

    # Schema
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ── 2. MIDDLEWARE ─────────────────────────────────────────────────────────────
# Add these to your MIDDLEWARE list (order matters):
MIDDLEWARE_ADDITIONS = [
    # After SecurityMiddleware:
    'cms.monitoring.metrics.MetricsMiddleware',
    # After SessionMiddleware:
    'cms.mobile.optimization.MobileOptimizationMiddleware',
]

# ── 3. CELERY BEAT SCHEDULE ──────────────────────────────────────────────────
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # Daily earnings calculation at 1 AM
    'daily-earnings-calculation': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=1, minute=0),
        'args': ('daily_earnings_calculation',),
    },
    # Update leaderboard at 2 AM
    'update-leaderboard': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=2, minute=0),
        'args': ('update_leaderboard',),
    },
    # Send pending notifications every 15 minutes
    'send-pending-notifications': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(minute='*/15'),
        'args': ('send_pending_notifications',),
    },
    # Generate weekly reports (Sunday 3 AM)
    'generate-weekly-reports': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'args': ('generate_reports',),
    },
    # Cleanup old data at 4 AM
    'cleanup-old-data': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=4, minute=0),
        'args': ('cleanup_old_data',),
    },
    # Warm caches at midnight
    'warm-caches': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=0, minute=0),
        'args': ('warm_caches',),
    },
    # Aggregate analytics at 5 AM
    'aggregate-analytics': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=5, minute=0),
        'args': ('aggregate_analytics',),
    },
}

# ── 4. DRF SPECTACULAR (API Schema) ──────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'CMS FINAL API',
    'DESCRIPTION': 'CPAlead CMS — Complete REST API (v3)',
    'VERSION': '3.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v3/',
}

# ── 5. CACHE CONFIGURATION ───────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
        },
        'KEY_PREFIX': 'cms',
        'TIMEOUT': 3600,
    }
}

# ── 6. METRICS ────────────────────────────────────────────────────────────────
METRICS_ENABLED = True
SEND_ERROR_ALERTS = True   # Send email to ADMINS on 500 errors

# ── 7. CORS ───────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://api.yourdomain.com",
]
CORS_ALLOW_CREDENTIALS = True

# ── 8. SECURITY ───────────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# ── 9. LOGGING ────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/cms.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'cms': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'cms.exceptions': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'cms.monitoring': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ── 10. INSTALLED APPS ADDITIONS ──────────────────────────────────────────────
# Make sure these are in INSTALLED_APPS:
REQUIRED_INSTALLED_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'drf_spectacular',
    'corsheaders',
    'channels',
    'django_celery_beat',
    'django_celery_results',
    'cms',
]

# ─────────────────────────────────────────────────────────────────────────────
# QUICK APPLY PATCH SCRIPT
# Run this in the project root to auto-patch settings_production.py
# ─────────────────────────────────────────────────────────────────────────────
"""
APPLY PATCH:

python3 - << 'EOF'
import re

settings_file = 'settings_production.py'
with open(settings_file, 'r') as f:
    content = f.read()

# 1. Add exception handler to REST_FRAMEWORK if present
if 'EXCEPTION_HANDLER' not in content:
    content = content.replace(
        "'DEFAULT_AUTHENTICATION_CLASSES':",
        "'EXCEPTION_HANDLER': 'cms.exceptions.custom_exception_handler',\\n    'DEFAULT_AUTHENTICATION_CLASSES':"
    )

# 2. Add MetricsMiddleware after SessionMiddleware
if 'MetricsMiddleware' not in content:
    content = content.replace(
        "'django.contrib.sessions.middleware.SessionMiddleware',",
        "'django.contrib.sessions.middleware.SessionMiddleware',\\n    'cms.monitoring.metrics.MetricsMiddleware',"
    )

# 3. Add METRICS_ENABLED
if 'METRICS_ENABLED' not in content:
    content += "\\nMETRICS_ENABLED = True\\n"

with open(settings_file, 'w') as f:
    f.write(content)

print("Settings patched successfully!")
EOF
"""

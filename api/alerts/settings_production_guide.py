"""
Production Settings Configuration Guide for Alerts System

This file contains the recommended production settings configuration.
Copy the relevant sections to your settings.py file.
"""
import os

# ============================================================================
# SENTRY INTEGRATION CONFIGURATION
# ============================================================================

# Install Sentry SDK first:
# pip install sentry-sdk

# Add to settings.py:
SENTRY_DSN = os.environ.get('SENTRY_DSN', 'your-sentry-dsn-here')
SENTRY_TRACES_SAMPLE_RATE = float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1'))

# ============================================================================
# PRODUCTION LOGGING CONFIGURATION
# ============================================================================

# Add to settings.py:
LOGGING_ROOT = '/var/log/alerts'  # Or your preferred log directory
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')
ALERTS_VERSION = '1.0.0'  # Update with your version

# Import production logging
from api.alerts.production_logging import get_production_logging_config

LOGGING = get_production_logging_config()

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# Session and CSRF security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Production database settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'alerts'),
        'USER': os.environ.get('DB_USER', 'alerts_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'secure_password'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 60,
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}

# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

# Redis cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/{os.environ.get('REDIS_DB', '0')}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
        },
        'KEY_PREFIX': 'alerts_',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

# Celery broker and backend
CELERY_BROKER_URL = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/{os.environ.get('REDIS_BROKER_DB', '1')}"
CELERY_RESULT_BACKEND = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/{os.environ.get('REDIS_RESULT_DB', '2')}"

# Celery settings
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================

# Production email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'alerts@yourdomain.com')

# ============================================================================
# STATIC AND MEDIA FILES
# ============================================================================

# Static files configuration
STATIC_ROOT = '/var/www/alerts/static/'
STATIC_URL = '/static/'
MEDIA_ROOT = '/var/www/alerts/media/'
MEDIA_URL = '/media/'

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================

# Database connection settings
DATABASE_POOL_ARGS = {
    'max_overflow': 10,
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Cache settings
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600  # 10 minutes
CACHE_MIDDLEWARE_KEY_PREFIX = 'alerts_'

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# ============================================================================
# MONITORING AND HEALTH CHECKS
# ============================================================================

# Health check settings
HEALTH_CHECK_ENABLED = True
HEALTH_CHECK_TOKEN = os.environ.get('HEALTH_CHECK_TOKEN', 'secure-token')

# Performance monitoring
ENABLE_PERFORMANCE_LOGGING = True
SLOW_QUERY_THRESHOLD = 1.0  # seconds

# ============================================================================
# RATE LIMITING
# ============================================================================

# Rate limiting settings
RATE_LIMIT_ENABLE = True
RATE_LIMIT_USE_CACHE = 'default'

# Custom rate limits for different endpoints
RATE_LIMITS = {
    'alerts_create': '10/h',
    'alerts_list': '1000/h',
    'notifications_send': '100/h',
    'webhook_call': '1000/h',
    'export_data': '5/h',
}

# ============================================================================
# BACKUP AND MAINTENANCE
# ============================================================================

# Backup settings
BACKUP_ENABLED = True
BACKUP_SCHEDULE = '0 2 * * *'  # Daily at 2 AM
BACKUP_RETENTION_DAYS = 30

# Maintenance mode settings
MAINTENANCE_MODE = False
MAINTENANCE_MESSAGE = "System is under maintenance. Please try again later."

# ============================================================================
# ENVIRONMENT VARIABLES SETUP
# ============================================================================

"""
Create .env file with the following variables:

# Database
DB_NAME=alerts
DB_USER=alerts_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_BROKER_DB=1
REDIS_RESULT_DB=2

# Sentry
SENTRY_DSN=your-sentry-dsn-here
SENTRY_TRACES_SAMPLE_RATE=0.1

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=alerts@yourdomain.com

# Environment
ENVIRONMENT=production
DEBUG=False
SECRET_KEY=your-very-secret-key

# Health Check
HEALTH_CHECK_TOKEN=secure-token

# Backup
BACKUP_ENABLED=True
BACKUP_RETENTION_DAYS=30
"""

# ============================================================================
# DEPLOYMENT COMMANDS
# ============================================================================

"""
Deployment checklist:

1. Install dependencies:
   pip install django redis django-redis celery sentry-sdk psycopg2-binary

2. Set environment variables:
   cp .env.example .env
   # Edit .env with your values

3. Run migrations:
   python manage.py migrate

4. Collect static files:
   python manage.py collectstatic --noinput

5. Check deployment:
   python manage.py check --deploy

6. Test health check:
   curl http://localhost:8000/api/alerts/health/

7. Setup Celery workers:
   celery -A alerts worker --loglevel=info

8. Setup Celery beat:
   celery -A alerts beat --loglevel=info

9. Setup monitoring:
   # Configure your monitoring service to ping health endpoints
   # /api/alerts/health/ - Comprehensive health check
   # /api/alerts/health/simple/ - Simple health check
   # /api/alerts/health/readiness/ - Readiness probe
   # /api/alerts/health/liveness/ - Liveness probe
"""

# ============================================================================
# URL CONFIGURATION
# ============================================================================

"""
Add to urls.py:

from api.alerts.health import (
    health_check, health_simple, health_readiness, 
    health_liveness, health_heartbeat
)

urlpatterns = [
    # ... your existing urls
    path('api/alerts/health/', health_check, name='health_check'),
    path('api/alerts/health/simple/', health_simple, name='health_simple'),
    path('api/alerts/health/readiness/', health_readiness, name='health_readiness'),
    path('api/alerts/health/liveness/', health_liveness, name='health_liveness'),
    path('api/alerts/health/heartbeat/', health_heartbeat, name='health_heartbeat'),
]
"""

# ============================================================================
# INITIALIZATION CODE
# ============================================================================

"""
Add to the bottom of settings.py:

# Initialize production logging
try:
    from api.alerts.production_logging import setup_production_logging
    setup_production_logging()
except ImportError:
    print("Warning: Production logging not available")
    pass

# Set start time for uptime tracking
import time
START_TIME = time.time()
"""

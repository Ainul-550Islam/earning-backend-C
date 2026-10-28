# Ainul Webhook System — Production Setup Guide

## ১ম ধাপ: ইনস্টল করুন

```bash
pip install -r requirements.txt
```

## ২য় ধাপ: settings.py-তে add করুন

```python
# আপনার main settings.py-তে:

INSTALLED_APPS = [
    # ... existing apps
    'rest_framework',
    'django_filters',
    'corsheaders',
    'django_celery_beat',
    'api.webhooks.apps.WebhooksConfig',   # ← যোগ করুন
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # ← CORS যোগ করুন
    # ... বাকি middleware
]

# Webhook settings import
from api.webhooks.settings.webhooks_settings import (
    WEBHOOKS,
    CACHES,
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_BEAT_SCHEDULE,
    CELERY_TASK_ROUTES,
    REST_FRAMEWORK,
    LOGGING,
    CORS_ALLOWED_ORIGINS,
    # Individual settings
    WEBHOOK_MAX_RETRIES,
    WEBHOOK_DEFAULT_TIMEOUT,
    WEBHOOK_SECRET_LENGTH,
    WEBHOOK_MAX_CONSECUTIVE_FAILURES,
    WEBHOOK_AUTO_SUSPEND_ENABLED,
    WEBHOOK_HEALTH_CHECK_INTERVAL,
    WEBHOOK_HEALTH_TIMEOUT,
    WEBHOOK_SECRET_GRACE_PERIOD_HOURS,
    WEBHOOK_MAX_OLD_SECRETS,
    WEBHOOK_BATCH_SIZE,
    WEBHOOK_BATCH_TIMEOUT,
    WEBHOOK_DEFAULT_RATE_LIMIT,
    WEBHOOKS_ALLOW_HTTP,
    WEBHOOKS_INTEGRATION_CONFIG,
    # Bridge configs
    WEBHOOK_BRIDGE_CONFIG,
    WEBHOOK_AUTH_BRIDGE_CONFIG,
    WEBHOOK_DATA_BRIDGE_CONFIG,
    WEBHOOK_ADAPTER_CONFIG,
    WEBHOOK_REGISTRY_CONFIG,
    WEBHOOK_SIGNAL_CONFIG,
    WEBHOOK_DATA_VALIDATOR_CONFIG,
    WEBHOOK_FALLBACK_CONFIG,
    WEBHOOK_HEALTH_CHECK_CONFIG,
    WEBHOOK_PERFORMANCE_MONITOR_CONFIG,
    WEBHOOK_SYNC_CONFIG,
    WEBHOOK_MESSAGE_QUEUE_CONFIG,
    WEBHOOK_EVENT_BUS_CONFIG,
    WEBHOOK_AUDIT_CONFIG,
    INBOUND_WEBHOOK_HANDLER_MODULES,
)
```

## ৩য় ধাপ: URL configure করুন

```python
# আপনার main urls.py-তে:
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/webhooks/', include('api.webhooks.urls', namespace='webhooks')),
]
```

## ৪র্থ ধাপ: Environment variables সেট করুন

```bash
cp .env.example .env
# .env file edit করুন এবং সব values সেট করুন
```

## ৫ম ধাপ: Database migration

```bash
python manage.py migrate
python manage.py createsuperuser
```

## ৬ষ্ঠ ধাপ: Celery workers চালু করুন

```bash
# Terminal 1 — Core dispatch worker
celery -A config worker -l info -Q webhooks_core,webhooks_dispatch,webhooks_retry -c 4

# Terminal 2 — Aging + analytics worker
celery -A config worker -l info -Q webhooks_aging,webhooks_analytics,webhooks_health -c 2

# Terminal 3 — Integration worker (যদি enabled থাকে)
celery -A config worker -l info -Q webhooks_integration -c 1

# Terminal 4 — Beat scheduler
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## ৭ম ধাপ: Admin এ event types seed করুন

```bash
python manage.py seed_event_types
```

## ৮ম ধাপ: Test run করুন

```bash
pytest tests/ -v --tb=short
# অথবা
python manage.py test api.webhooks.tests
```

---

## Production Checklist

```
□ DEBUG=False
□ SECRET_KEY পরিবর্তন করা হয়েছে
□ ALLOWED_HOSTS সঠিকভাবে সেট
□ PostgreSQL connected
□ Redis connected
□ Celery workers চালু
□ Celery beat scheduler চালু
□ HTTPS enforced (WEBHOOKS_ALLOW_HTTP=false)
□ WEBHOOK_INTEGRATION_ENABLED=true/false সিদ্ধান্ত নেওয়া
□ Email alerts configured
□ Sentry DSN configured (optional)
□ Log directory exists: logs/
□ Static files collected: python manage.py collectstatic
□ Database migrations applied
□ Admin superuser created
```

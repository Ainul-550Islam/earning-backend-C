# Telemetry Observability — Integration Guide
## earning_backend / api/telemetry_observability

---

## Step 1 — Copy the package

```bash
cp -r telemetry_observability/  earning_backend/api/telemetry_observability/
```

Final location:
```
earning_backend/
  api/
    telemetry_observability/   ← HERE
    fraud_detection/
    analytics/
    ...
```

---

## Step 2 — Install new dependencies

Add to `requirements.txt` (only the ones not already present):

```
django-redis>=5.0
djangorestframework-simplejwt>=5.0
sentry-sdk>=1.0
django-channels>=4.0       # only if you want WebSocket streaming
```

Then:
```bash
pip install -r requirements.txt
```

---

## Step 3 — INSTALLED_APPS

In your main settings file (e.g. `config/settings/base.py` or `settings_production.py`):

```python
INSTALLED_APPS = [
    # ... your existing apps ...
    'api.telemetry_observability',   # ← ADD THIS
]
```

---

## Step 4 — MIDDLEWARE

Add `TelemetryMiddleware` **after** `SecurityMiddleware` and `SessionMiddleware`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'api.telemetry_observability.middleware.TelemetryMiddleware',  # ← ADD
    # ... rest of your middleware ...
]
```

---

## Step 5 — URL routing

In your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... your existing patterns ...

    # Telemetry — all endpoints under /telemetry/
    path('telemetry/', include('api.telemetry_observability.urls')),
]
```

This exposes:
- `GET  /telemetry/ping/`                       — liveness probe (no auth)
- `GET  /telemetry/readiness/`                  — readiness probe (no auth)
- `*    /telemetry/api/v1/telemetry/metrics/`   — metrics
- `*    /telemetry/api/v1/telemetry/logs/`
- `*    /telemetry/api/v1/telemetry/traces/`
- `*    /telemetry/api/v1/telemetry/alerts/`
- `*    /telemetry/api/v1/telemetry/health/`
- `*    /telemetry/api/v1/telemetry/dashboards/`
- `*    /telemetry/api/v1/telemetry/analytics/`

---

## Step 6 — Celery beat schedule

In your main `celery.py` or `celery_config.py`:

```python
from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE

# Merge into your existing beat_schedule
app.conf.beat_schedule.update(TELEMETRY_BEAT_SCHEDULE)
```

Or if you use `CELERY_BEAT_SCHEDULE` in Django settings:

```python
from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE

CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,        # your existing tasks
    **TELEMETRY_BEAT_SCHEDULE,     # telemetry tasks
}
```

---

## Step 7 — Settings to add

Add these to your main settings file. Check each block — skip any that are already configured.

### Cache (django-redis — required for delete_pattern in tasks)

```python
# Only add if you don't already have a Redis cache configured.
# If you DO have one, just make sure BACKEND is 'django_redis.cache.RedisCache'
CACHES = {
    'default': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS':  {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}
```

### JWT (if not already configured)

```python
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM':              'HS256',
    'SIGNING_KEY':            SECRET_KEY,
    'AUTH_HEADER_TYPES':      ('Bearer',),
}
```

Add JWT to REST_FRAMEWORK authentication (merge, don't replace):

```python
REST_FRAMEWORK = {
    # ... your existing REST_FRAMEWORK settings ...
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}
```

### Telemetry-specific settings

```python
# How many days to keep telemetry records (cleanup task uses this)
TELEMETRY_RETENTION_DAYS = int(os.environ.get('TELEMETRY_RETENTION_DAYS', 90))

# Outbound webhook URLs — comma-separated (leave empty to disable)
TELEMETRY_WEBHOOK_URLS   = os.environ.get('TELEMETRY_WEBHOOK_URLS', '').split(',')
TELEMETRY_WEBHOOK_SECRET = os.environ.get('TELEMETRY_WEBHOOK_SECRET', '')

# Internet check config
INTERNET_CHECK_PASS_THRESHOLD  = 0.5
INTERNET_CHECK_TIMEOUT         = 5
INTERNET_CHECK_ENVIRONMENT     = os.environ.get('DJANGO_ENV', 'production')

# App version (shown in /ping/ and Sentry)
APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
```

### Sentry (optional but recommended)

```python
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', 0.1)),
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        send_default_pii=False,
    )
```

---

## Step 8 — WebSocket (optional)

Only needed if you want real-time streaming of metrics/logs/traces/alerts.

In your main `asgi.py`:

```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from api.telemetry_observability.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns  # ← ADD THIS
            # + your other websocket patterns
        )
    ),
})
```

WebSocket endpoints:
- `ws://<host>/ws/telemetry/metrics/`
- `ws://<host>/ws/telemetry/logs/`
- `ws://<host>/ws/telemetry/traces/`
- `ws://<host>/ws/telemetry/alerts/`
- `ws://<host>/ws/telemetry/health/`

---

## Step 9 — Run migrations

```bash
python manage.py migrate api_telemetry_observability  # or just:
python manage.py migrate
```

Django will create these tables:
- `telemetry_observability_metricevent`
- `telemetry_observability_logentry`
- `telemetry_observability_tracespan`
- `telemetry_observability_alert`
- `telemetry_observability_healthstatus`
- `telemetry_observability_dashboardwidget`

---

## Step 10 — Verify

```bash
# Check app loaded
python manage.py check --deploy

# Seed sample data
python manage.py seed_telemetry

# Manual internet connectivity check
python manage.py check_internet

# Run telemetry tests
pytest api/telemetry_observability/tests/ -v
```

---

## .env additions

```env
# Telemetry
TELEMETRY_RETENTION_DAYS=90
TELEMETRY_WEBHOOK_URLS=
TELEMETRY_WEBHOOK_SECRET=
INTERNET_CHECK_PASS_THRESHOLD=0.5
INTERNET_CHECK_TIMEOUT=5
APP_VERSION=1.0.0

# Sentry (optional)
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.10

# JWT (if not already set)
JWT_ACCESS_MINUTES=60
JWT_REFRESH_DAYS=7
```

---

## Conflict checklist

| Concern | Status | Action |
|---|---|---|
| `manage.py` | Main project already has one | ✅ No conflict — telemetry doesn't have one |
| `settings/` | Main project handles settings | ✅ Removed from package |
| `asgi.py` / `wsgi.py` | Main project has these | ✅ Removed from package |
| `celery.py` | Main project has its own | ✅ Converted to `celery_schedule.py` |
| `/admin/` URL | Main project registers admin | ✅ Removed from telemetry urls.py |
| `/api/token/` JWT URL | Main project may already have it | ✅ Removed — add to main urls.py if needed |
| Django URL name conflicts | Router basenames were generic | ✅ All prefixed with `telemetry-` |
| App label | Must be unique in Django | ✅ `label = 'telemetry_observability'` set |
| Migration conflicts | Migrations use `app_label` | ✅ `label` in AppConfig matches migrations |
| Absolute imports | Were `telemetry_observability.*` | ✅ All fixed to `api.telemetry_observability.*` |
| Task names | Were `telemetry_observability.tasks.*` | ✅ All fixed to `api.telemetry_observability.tasks.*` |

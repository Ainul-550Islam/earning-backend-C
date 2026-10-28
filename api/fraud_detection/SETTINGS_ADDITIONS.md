# ============================================================
# REQUIRED SETTINGS ADDITIONS  (add to config/settings/base.py)
# ============================================================

## 1. context_processors.py — add to TEMPLATES[0]['OPTIONS']['context_processors']
```python
TEMPLATES = [{
    ...
    'OPTIONS': {
        'context_processors': [
            # ... existing processors ...
            'api.fraud_detection.context_processors.fraud_detection_context',
            'api.fraud_detection.context_processors.get_fraud_feature_flags_context',
        ],
    },
}]
```

## 2. WebSocket (routing.py consumers.py)  — add to asgi.py
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from api.fraud_detection.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

## 3. django-channels — add to INSTALLED_APPS
```python
INSTALLED_APPS += ['channels']
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}
ASGI_APPLICATION = "config.asgi.application"
```

## 4. Celery Beat (celery_beat_config.py)
```python
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
```

## 5. Fraud Detection master URL include — add to project urls.py
```python
path("api/fraud/", include("api.fraud_detection.urls")),
```

---

## 6. Multi-tenant middleware
```python
MIDDLEWARE += ['api.fraud_detection.tenant_middleware.TenantMiddleware']
```

## 7. KYC provider
```python
KYC_PROVIDER = "stub"          # or "onfido", "jumio", "persona"
```

## 8. MFA settings
```python
MFA_TOTP_PERIOD  = 30          # seconds
MFA_TOTP_DIGITS  = 6
MFA_MAX_ATTEMPTS = 3
MFA_LOCKOUT_TTL  = 300         # 5 min
MFA_ISSUER       = "YourAppName"
```

## 9. Report delivery
```python
FRAUD_REPORT_RECIPIENTS = ["compliance@yourcompany.com"]
```

## 10. New Celery beat tasks (add to celery config)
```python
from api.fraud_detection.celery_beat_config import get_all_beat_schedules
CELERY_BEAT_SCHEDULE = get_all_beat_schedules()
```

## 11. New installed apps (models_tenant.py requires migration)
```bash
python manage.py makemigrations fraud_detection
python manage.py migrate
```

# Notification System — Earning Site (CPAlead-level)

## Architecture Overview

```
notifications/
├── _models_core.py          ← Original 4200-line models (KEEP — active)
├── _services_core.py        ← Original 3280-line services (KEEP — active)
├── _tasks_core.py           ← Original 1892-line tasks (KEEP — active)
├── _serializers_core.py     ← Original 2481-line serializers (KEEP — active)
├── models/                  ← New split models (17 new models)
├── services/                ← New services + 6 provider adapters
├── viewsets/                ← 16 REST viewsets
├── tasks/                   ← 14 Celery task modules
├── serializers/             ← New model serializers
├── consumers.py             ← WebSocket real-time notifications
├── signals.py               ← Auto-notifications on earning events
└── migrations/              ← DB migrations (0001-0004)
```

## Installation

```bash
pip install -r requirements.txt
# Additional for full feature support:
pip install channels channels-redis pywebpush firebase-admin sendgrid twilio apns2 PyJWT httpx django-filter
```

## Required Settings

```python
# settings.py

# Firebase
FIREBASE_CREDENTIALS = '/path/to/serviceAccountKey.json'
APNS_TOPIC = 'com.yourapp.app'

# SendGrid
SENDGRID_API_KEY = 'SG.xxxx'
DEFAULT_FROM_EMAIL = 'noreply@yoursite.com'
DEFAULT_FROM_NAME = 'Your Site'

# Twilio
TWILIO_ACCOUNT_SID = 'ACxxxx'
TWILIO_AUTH_TOKEN = 'xxxx'
TWILIO_FROM_NUMBER = '+1415xxxxxxx'
TWILIO_WHATSAPP_FROM = 'whatsapp:+14155238886'

# ShohoSMS (Bangladesh)
SHOHO_SMS_API_KEY = 'your_api_key'
SHOHO_SMS_SENDER_ID = 'YourBrand'

# Web Push (VAPID)
WEBPUSH_VAPID_PRIVATE_KEY = 'your_private_key'
WEBPUSH_VAPID_PUBLIC_KEY = 'your_public_key'
WEBPUSH_VAPID_CLAIMS_EMAIL = 'mailto:admin@yoursite.com'

# WebSocket (Django Channels)
INSTALLED_APPS += ['channels']
ASGI_APPLICATION = 'config.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
    }
}

# Fatigue limits
NOTIFICATION_FATIGUE_DAILY_LIMIT = 10
NOTIFICATION_FATIGUE_WEEKLY_LIMIT = 50

# Celery
from api.notifications.celery_beat_schedule import NOTIFICATION_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {**CELERY_BEAT_SCHEDULE, **NOTIFICATION_BEAT_SCHEDULE}
```

## Middleware (settings.py)

```python
MIDDLEWARE = [
    ...
    'api.notifications.middleware.NotificationUserActivityMiddleware',
    'api.notifications.middleware.DoNotDisturbMiddleware',
    'api.notifications.middleware.WebhookSignatureMiddleware',
]
```

## Deploy

```bash
# 1. Run migration
python manage.py migrate notifications

# 2. Initial setup
python manage.py notification_maintenance --all

# 3. Start Celery worker
celery -A config worker -Q notifications_high,notifications_push,notifications_email,notifications_sms,notifications_campaigns,notifications_scheduled,notifications_retry,notifications_tracking,notifications_analytics,notifications_maintenance,notifications_batch,notifications_optout --loglevel=info

# 4. Start Celery Beat
celery -A config beat --loglevel=info

# 5. Start WebSocket server (ASGI)
daphne -p 8001 config.asgi:application
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/notifications/` | List notifications |
| `POST /api/notifications/mark-all-read/` | Mark all read |
| `GET /api/notifications/v2/in-app-messages/` | In-app messages |
| `POST /api/notifications/v2/push-devices/register/` | Register device |
| `GET /api/notifications/v2/insights/` | Analytics data |
| `POST /api/notifications/v2/opt-outs/opt_out/` | Unsubscribe |
| `POST /api/notifications/webhooks/sendgrid/` | SendGrid webhook |
| `POST /api/notifications/webhooks/twilio/sms/` | Twilio webhook |
| `GET /api/notifications/push/vapid-key/` | VAPID public key |
| `WS /ws/notifications/` | WebSocket real-time |

## Backup Safety

The original code is fully preserved:
- `models.py` → kept as-is (shadowed by `models/` but backed up as `_models_core.py`)
- `services.py` → kept as-is (shadowed by `services/` but backed up as `_services_core.py`)
- `tasks.py` → kept as-is (shadowed by `tasks/` but backed up as `_tasks_core.py`)
- `serializers.py` → kept as-is (shadowed by `serializers/` but backed up as `_serializers_core.py`)

**No original code was deleted. All imports from _*_core.py are active.**

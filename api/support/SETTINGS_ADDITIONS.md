# settings.py-তে যা যোগ করতে হবে

## STEP 1: INSTALLED_APPS
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'api.support',          # Support system
    'channels',             # WebSocket (pip install channels)
]
```

## STEP 2: Support System Settings
```python
# ═══════════════════════════════════════════════════════════════
# WORLD #1 SUPPORT SYSTEM SETTINGS
# ═══════════════════════════════════════════════════════════════

# Site info
SITE_URL  = 'https://yoursite.com'       # ⚠️ CHANGE THIS
SITE_NAME = 'YourSite'                    # ⚠️ CHANGE THIS

# AI (Claude API) — for auto-responder
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', default='')

# Support admin email — receives daily digest
SUPPORT_ADMIN_EMAIL = env('SUPPORT_ADMIN_EMAIL', default='admin@yoursite.com')

# Telegram Bot — for agent notifications
TELEGRAM_BOT_TOKEN = env('TELEGRAM_BOT_TOKEN', default='')

# WhatsApp — for user notifications
WHATSAPP_API_TOKEN  = env('WHATSAPP_API_TOKEN', default='')
WHATSAPP_API_URL    = env('WHATSAPP_API_URL', default='')
WHATSAPP_PHONE_ID   = env('WHATSAPP_PHONE_ID', default='')

# Slack webhook — for agent alerts
SLACK_WEBHOOK_URL = env('SLACK_WEBHOOK_URL', default='')

# Push notifications (Firebase FCM)
FCM_SERVER_KEY     = env('FCM_SERVER_KEY', default='')
VAPID_PUBLIC_KEY   = env('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY  = env('VAPID_PRIVATE_KEY', default='')
VAPID_ADMIN_EMAIL  = env('VAPID_ADMIN_EMAIL', default='admin@yoursite.com')

# SMS (choose one: twilio, infobip, sslcommerz_sms)
SMS_PROVIDER       = env('SMS_PROVIDER', default='')
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN  = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER = env('TWILIO_FROM_NUMBER', default='')

# SLA timezone (important for Bangladesh)
SLA_TIMEZONE = 'Asia/Dhaka'

# Live Chat WebSocket (Django Channels + Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://127.0.0.1:6379/0')],
        },
    },
}
ASGI_APPLICATION = 'yourproject.asgi.application'  # ⚠️ CHANGE yourproject

# File uploads for support attachments
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
MAX_SUPPORT_ATTACHMENT_MB = 10  # 10MB limit
```

## STEP 3: Email Settings (if not already set)
```python
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT          = env('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = env('DEFAULT_FROM_EMAIL', default='noreply@yoursite.com')
```

## STEP 4: Celery Beat Schedule
```python
# Add to your existing CELERY_BEAT_SCHEDULE:
from api.support.celery_schedule import SUPPORT_CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {
    **CELERY_BEAT_SCHEDULE,         # your existing tasks
    **SUPPORT_CELERY_BEAT_SCHEDULE,  # support tasks
}

# If CELERY_BEAT_SCHEDULE doesn't exist yet:
CELERY_BEAT_SCHEDULE = {**SUPPORT_CELERY_BEAT_SCHEDULE}
```

## STEP 5: Main urls.py
```python
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... existing urls ...
    path('api/support/', include('api.support.urls')),
    path('api/support/', include('api.support.cpa_urls')),  # CPA endpoints
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

## STEP 6: asgi.py (for WebSocket live chat)
```python
# yourproject/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from api.support.consumers.routing import support_websocket_patterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')

application = ProtocolTypeRouter({
    'http':      get_asgi_application(),
    'websocket': AuthMiddlewareStack(URLRouter(support_websocket_patterns)),
})
```

## STEP 7: .env file additions
```env
# Support System
ANTHROPIC_API_KEY=sk-ant-your-key-here
SUPPORT_ADMIN_EMAIL=admin@yoursite.com
TELEGRAM_BOT_TOKEN=your-bot-token
WHATSAPP_API_TOKEN=your-whatsapp-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
FCM_SERVER_KEY=your-fcm-key
VAPID_PUBLIC_KEY=your-vapid-public
VAPID_PRIVATE_KEY=your-vapid-private

# Redis (for Channels + Celery)
REDIS_URL=redis://127.0.0.1:6379/0
```

## STEP 8: pip install
```bash
pip install \
    channels \
    channels-redis \
    daphne \
    pywebpush \
    openpyxl \
    anthropic \
    celery \
    redis \
    requests \
    Pillow
```

## STEP 9: After install, run
```bash
python manage.py migrate support
python manage.py seed_sla_policies
python manage.py seed_canned_responses
python manage.py seed_departments
python manage.py check
```

## STEP 10: Create first SupportAgent (in Django shell)
```python
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> from api.support.models import SupportAgent
>>> User = get_user_model()
>>> admin = User.objects.get(username='your_admin_username')
>>> SupportAgent.objects.create(user=admin, role='manager', is_active=True, is_available=True)
```

# World #1 Support System — Installation Guide

## This Package Contains:
Complete replacement for `api/support/` directory.
- **131+ Python files** across 20+ modules
- **25 Django models** (new + extended existing)
- **25+ API endpoints**
- **AI, SLA, Automation, Dashboard, CPA** modules

## Step 1: Replace your support directory
```bash
# Backup your existing support
cp -r api/support api/support_backup

# Copy this package
cp -r support_world1_FINAL/* api/support/
```

## Step 2: Run migrations
```bash
python manage.py migrate support
```

## Step 3: Add to settings.py
```python
# Add to MIDDLEWARE:
'api.support.middleware.support_middleware.VisitorTrackingMiddleware',
'api.support.middleware.rate_limit_middleware.SupportRateLimitMiddleware',

# Required settings (from settings_support.py):
ANTHROPIC_API_KEY = 'sk-ant-...'
SITE_URL = 'https://yoursite.com'
SITE_NAME = 'YourSite'
SUPPORT_ADMIN_EMAIL = 'admin@yoursite.com'
TELEGRAM_BOT_TOKEN = ''
WHATSAPP_API_TOKEN = ''
SLACK_WEBHOOK_URL = ''
FCM_SERVER_KEY = ''
```

## Step 4: Update Celery
```python
# settings.py
from api.support.celery_schedule import SUPPORT_CELERY_BEAT_SCHEDULE
CELERY_BEAT_SCHEDULE = {**CELERY_BEAT_SCHEDULE, **SUPPORT_CELERY_BEAT_SCHEDULE}
```

## Step 5: Add URLs
```python
# main urls.py
path('api/support/', include('api.support.urls')),
# Plus CPA endpoints:
path('api/support/', include('api.support.cpa_urls')),
```

## Step 6: pip install
```bash
pip install pywebpush openpyxl channels channels-redis pytz
```

## Step 7: Verify
```bash
python manage.py check
python manage.py shell < api/support/test_imports.py
```

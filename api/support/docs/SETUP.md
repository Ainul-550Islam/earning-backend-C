# Support System Setup Guide

## Requirements
```
django>=5.0
djangorestframework>=3.15
celery>=5.3
redis>=5.0
channels>=4.0
channels-redis>=4.0
django-filter>=23.0
cryptography>=41.0  # optional, for encryption
factory-boy>=3.3    # for tests
```

## Django Settings
```python
INSTALLED_APPS = [
    ...
    "api.support",
]

# In settings.py
from api.support.settings_support import (
    SUPPORT_THROTTLE_RATES, SUPPORT_BEAT_SCHEDULE
)

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": SUPPORT_THROTTLE_RATES,
    ...
}
CELERY_BEAT_SCHEDULE.update(SUPPORT_BEAT_SCHEDULE)
```

## URLs
```python
# api/urls.py
urlpatterns = [
    path("support/", include("api.support.urls")),
]
```

## Migrations
```bash
python manage.py migrate support
```

## Seed Data
```bash
python manage.py seed_sla_policies
python manage.py seed_departments
python manage.py seed_canned_responses
python manage.py seed_kb_categories
# Or use fixtures:
python manage.py loaddata initial_sla initial_departments initial_kb initial_canned
```

## Environment Variables
```env
SUPPORT_ADMIN_EMAIL=admin@yoursite.com
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SUPPORT_EMAIL_PASSWORD=app_password
SUPPORT_SLACK_WEBHOOK_URL=https://hooks.slack.com/...
FACEBOOK_APP_SECRET=...
SUPPORT_ENCRYPTION_KEY=32_char_random_key
SUPPORT_AI_ENABLED=false
SUPPORT_CHAT_ENABLED=true
REDIS_URL=redis://localhost:6379/0
```

## Railway Deployment
1. Set all environment variables in Railway dashboard
2. `python manage.py migrate`
3. `python manage.py seed_sla_policies`
4. Start Celery worker: `celery -A config worker -l info`
5. Start Celery beat: `celery -A config beat -l info`

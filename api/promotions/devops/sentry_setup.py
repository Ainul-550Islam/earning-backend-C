# =============================================================================
# devops/sentry_setup.py
# Sentry Error Tracking + Performance Monitoring
# Add to settings.py: from api.promotions.devops.sentry_setup import init_sentry; init_sentry()
# =============================================================================
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from django.conf import settings


def init_sentry():
    """Initialize Sentry — call from settings.py"""
    dsn = getattr(settings, 'SENTRY_DSN', '')
    if not dsn:
        return  # Skip in development

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            DjangoIntegration(transaction_style='url'),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,    # 10% performance tracking
        profiles_sample_rate=0.05, # 5% profiling
        environment=getattr(settings, 'ENVIRONMENT', 'production'),
        release=getattr(settings, 'VERSION', '1.0.0'),
        send_default_pii=False,    # GDPR compliance
        before_send=_filter_sensitive_events,
    )


def _filter_sensitive_events(event, hint):
    """Remove sensitive data before sending to Sentry."""
    if 'request' in event:
        headers = event.get('request', {}).get('headers', {})
        # Remove auth headers
        for key in ['Authorization', 'Cookie', 'X-API-Key']:
            headers.pop(key, None)
    # Remove PII from extra data
    extra = event.get('extra', {})
    for key in ['email', 'phone', 'password', 'api_key']:
        extra.pop(key, None)
    return event

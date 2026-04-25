# earning_backend/api/notifications/throttling.py
"""
Custom throttling/rate limiting for the notification API.
Prevents notification spam and API abuse.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
from django.conf import settings


class NotificationCreateThrottle(UserRateThrottle):
    """Limit how often a user can create notifications via API."""
    scope = 'notification_create'
    rate = getattr(settings, 'NOTIFICATION_CREATE_RATE', '30/hour')


class BulkSendThrottle(UserRateThrottle):
    """Limit bulk notification sends (admin)."""
    scope = 'notification_bulk_send'
    rate = getattr(settings, 'NOTIFICATION_BULK_SEND_RATE', '5/hour')


class DeviceRegisterThrottle(UserRateThrottle):
    """Limit device token registrations per user."""
    scope = 'device_register'
    rate = getattr(settings, 'DEVICE_REGISTER_RATE', '10/day')


class WebhookThrottle(AnonRateThrottle):
    """Rate limit incoming webhooks from providers (SendGrid, Twilio)."""
    scope = 'webhook'
    rate = getattr(settings, 'WEBHOOK_RATE', '1000/minute')


class CampaignThrottle(UserRateThrottle):
    """Limit campaign creation and start operations."""
    scope = 'campaign'
    rate = getattr(settings, 'CAMPAIGN_RATE', '10/day')


class OptOutThrottle(UserRateThrottle):
    """Limit opt-out/unsubscribe actions (prevent abuse)."""
    scope = 'opt_out'
    rate = getattr(settings, 'OPT_OUT_RATE', '20/hour')


class PushSendThrottle(SimpleRateThrottle):
    """Per-device push send throttle to avoid token blacklisting."""
    scope = 'push_send'
    rate = '100/hour'

    def get_cache_key(self, request, view):
        # Throttle per user, not per IP
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk,
        }


# Add to settings.py:
# REST_FRAMEWORK = {
#     'DEFAULT_THROTTLE_CLASSES': [],
#     'DEFAULT_THROTTLE_RATES': {
#         'notification_create': '30/hour',
#         'notification_bulk_send': '5/hour',
#         'device_register': '10/day',
#         'webhook': '1000/minute',
#         'campaign': '10/day',
#         'opt_out': '20/hour',
#         'push_send': '100/hour',
#     }
# }

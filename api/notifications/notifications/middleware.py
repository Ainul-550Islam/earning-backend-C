# earning_backend/api/notifications/middleware.py
"""
Notification system middleware.

1. NotificationUserActivityMiddleware  — tracks last_active, updates fatigue
2. DoNotDisturbMiddleware             — checks DND schedule before sending
3. WebhookSignatureMiddleware         — verifies SendGrid/Twilio webhook signatures
"""
import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class NotificationUserActivityMiddleware(MiddlewareMixin):
    """
    Tracks authenticated user activity and updates DeviceToken.last_active
    once per hour (not on every request to avoid DB hammering).
    """

    UPDATE_INTERVAL_SECONDS = 3600  # 1 hour

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        # Use session to track last update time
        last_update = request.session.get('_notif_activity_update', 0)
        now = time.time()

        if now - last_update < self.UPDATE_INTERVAL_SECONDS:
            return None

        request.session['_notif_activity_update'] = now

        # Update device tokens in background (non-blocking)
        try:
            from api.notifications.models import DeviceToken
            DeviceToken.objects.filter(
                user=request.user,
                is_active=True,
            ).update(last_active=timezone.now())
        except Exception:
            pass

        return None


class DoNotDisturbMiddleware(MiddlewareMixin):
    """
    Checks DND (Do Not Disturb) schedule for outgoing notification API calls.
    Only applies to POST /notifications/ endpoints during user's quiet hours.
    """

    DND_PATHS = ['/api/notifications/', '/api/v2/notifications/']

    def process_request(self, request):
        # Only check POST requests on notification creation endpoints
        if request.method != 'POST':
            return None
        if not any(request.path.startswith(p) for p in self.DND_PATHS):
            return None
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        try:
            from api.notifications.models import NotificationPreference
            pref = NotificationPreference.objects.filter(user=request.user).first()
            if pref and getattr(pref, 'dnd_enabled', False):
                if self._is_dnd_active(pref):
                    # Don't block — just tag request for suppression
                    request._notification_dnd_active = True
        except Exception:
            pass

        return None

    def _is_dnd_active(self, pref) -> bool:
        """Check if current time is within DND window."""
        try:
            import pytz
            from datetime import datetime

            dnd_tz = getattr(pref, 'dnd_timezone', 'Asia/Dhaka') or 'Asia/Dhaka'
            dnd_start = getattr(pref, 'dnd_start', None)
            dnd_end = getattr(pref, 'dnd_end', None)

            if not dnd_start or not dnd_end:
                return False

            tz = pytz.timezone(dnd_tz)
            now_local = datetime.now(tz).time()

            # Handle overnight DND (e.g. 22:00 → 07:00)
            if dnd_start > dnd_end:
                return now_local >= dnd_start or now_local <= dnd_end
            else:
                return dnd_start <= now_local <= dnd_end
        except Exception:
            return False


class WebhookSignatureMiddleware(MiddlewareMixin):
    """
    Verifies webhook signatures from SendGrid and Twilio on incoming webhook calls.
    Returns 401 if signature is invalid.
    """

    SENDGRID_WEBHOOK_PATH = '/api/notifications/webhooks/sendgrid/'
    TWILIO_WEBHOOK_PATH = '/api/notifications/webhooks/twilio/sms/'

    def process_request(self, request):
        path = request.path

        if path == self.SENDGRID_WEBHOOK_PATH:
            return self._verify_sendgrid(request)
        elif path == self.TWILIO_WEBHOOK_PATH:
            return self._verify_twilio(request)

        return None

    def _verify_sendgrid(self, request):
        """Verify SendGrid Event Webhook signature."""
        key = getattr(settings, 'SENDGRID_WEBHOOK_VERIFICATION_KEY', '')
        if not key:
            return None  # Skip verification if key not configured

        signature = request.headers.get('X-Twilio-Email-Event-Webhook-Signature', '')
        timestamp = request.headers.get('X-Twilio-Email-Event-Webhook-Timestamp', '')

        if not signature or not timestamp:
            logger.warning('SendGrid webhook missing signature headers')
            return HttpResponse('Unauthorized', status=401)

        try:
            payload = timestamp.encode() + request.body
            expected = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning('SendGrid webhook signature mismatch')
                return HttpResponse('Unauthorized', status=401)
        except Exception as exc:
            logger.error(f'SendGrid webhook verification error: {exc}')
            return HttpResponse('Unauthorized', status=401)

        return None

    def _verify_twilio(self, request):
        """Verify Twilio webhook signature."""
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        if not auth_token:
            return None  # Skip if not configured

        try:
            from twilio.request_validator import RequestValidator
            validator = RequestValidator(auth_token)
            signature = request.headers.get('X-Twilio-Signature', '')
            url = request.build_absolute_uri()
            params = dict(request.POST)

            if not validator.validate(url, params, signature):
                logger.warning('Twilio webhook signature validation failed')
                return HttpResponse('Unauthorized', status=401)
        except ImportError:
            pass  # twilio not installed
        except Exception as exc:
            logger.error(f'Twilio webhook verification error: {exc}')
            return HttpResponse('Unauthorized', status=401)

        return None

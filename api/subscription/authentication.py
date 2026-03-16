"""authentication.py – Custom authentication for the subscription module."""
import hashlib
import hmac
import time
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .constants import WEBHOOK_SIGNATURE_HEADER, WEBHOOK_TOLERANCE_SECONDS


class WebhookAuthentication(BaseAuthentication):
    """
    HMAC-SHA256 signature verification for incoming payment gateway webhooks.
    The gateway must send a header: X-Subscription-Signature: t=<timestamp>,v1=<sig>
    """

    def authenticate(self, request):
        # Only apply to webhook endpoints
        if not request.path.startswith("/api/subscriptions/webhooks/"):
            return None

        header = request.META.get("HTTP_" + WEBHOOK_SIGNATURE_HEADER.upper().replace("-", "_"), "")
        if not header:
            raise AuthenticationFailed("Missing webhook signature header.")

        try:
            parts = dict(item.split("=", 1) for item in header.split(","))
            timestamp = int(parts["t"])
            signature = parts["v1"]
        except (KeyError, ValueError):
            raise AuthenticationFailed("Malformed webhook signature header.")

        # Replay attack guard
        if abs(time.time() - timestamp) > WEBHOOK_TOLERANCE_SECONDS:
            raise AuthenticationFailed("Webhook timestamp is too old.")

        secret = getattr(settings, "SUBSCRIPTION_WEBHOOK_SECRET", "")
        payload = f"{timestamp}.{request.body.decode('utf-8')}"
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise AuthenticationFailed("Webhook signature verification failed.")

        # Return None user – webhook is system-level, not user-level
        return (None, None)

    def authenticate_header(self, request):
        return WEBHOOK_SIGNATURE_HEADER
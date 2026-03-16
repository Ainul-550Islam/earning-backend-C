"""throttling.py – Rate limiting for subscription endpoints."""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from .constants import (
    SUBSCRIPTION_THROTTLE_RATE,
    PAYMENT_THROTTLE_RATE,
    WEBHOOK_THROTTLE_RATE,
)


class SubscriptionThrottle(UserRateThrottle):
    """Standard throttle for subscription read/write operations."""
    scope = "subscription"
    rate = SUBSCRIPTION_THROTTLE_RATE


class PaymentThrottle(UserRateThrottle):
    """Stricter throttle for payment-related operations."""
    scope = "payment"
    rate = PAYMENT_THROTTLE_RATE


class WebhookThrottle(AnonRateThrottle):
    """High-volume throttle for incoming gateway webhooks (anonymous callers)."""
    scope = "webhook"
    rate = WEBHOOK_THROTTLE_RATE


class BurstSubscriptionThrottle(UserRateThrottle):
    """Short-burst throttle to prevent accidental double-submissions."""
    scope = "subscription_burst"
    rate = "3/second"
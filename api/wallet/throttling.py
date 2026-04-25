# api/wallet/throttling.py
"""
Custom DRF throttle classes for wallet endpoints.
More granular than Django REST framework defaults.

Usage in viewset:
    class WithdrawalRequestViewSet(viewsets.ModelViewSet):
        throttle_classes = [WithdrawalThrottle]
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class WithdrawalThrottle(UserRateThrottle):
    """5 withdrawal requests per hour per user."""
    scope = "withdrawal"
    THROTTLE_RATES = {"withdrawal": "5/hour"}

    def get_rate(self):
        return "5/hour"


class EarningThrottle(UserRateThrottle):
    """100 earning API calls per hour per user."""
    scope = "earning"

    def get_rate(self):
        return "100/hour"


class KYCSubmitThrottle(UserRateThrottle):
    """3 KYC submissions per day per user."""
    scope = "kyc_submit"

    def get_rate(self):
        return "3/day"


class TransferThrottle(UserRateThrottle):
    """10 transfers per hour per user."""
    scope = "transfer"

    def get_rate(self):
        return "10/hour"


class WebhookThrottle(AnonRateThrottle):
    """500 webhook calls per minute from any IP."""
    scope = "webhook"

    def get_rate(self):
        return "500/min"


class AdminOperationThrottle(UserRateThrottle):
    """50 admin operations per hour."""
    scope = "admin_op"

    def get_rate(self):
        return "50/hour"


class PublicAPIThrottle(AnonRateThrottle):
    """30 public API calls per minute for unauthenticated users."""
    scope = "public"

    def get_rate(self):
        return "30/min"


class OfferConversionThrottle(UserRateThrottle):
    """50 offer conversions per hour per user."""
    scope = "offer_convert"

    def get_rate(self):
        return "50/hour"

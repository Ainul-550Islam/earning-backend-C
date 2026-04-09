# api/djoyalty/throttles.py
"""Custom DRF throttle classes for Djoyalty API rate limiting।"""
from rest_framework.throttling import (
    UserRateThrottle, AnonRateThrottle, ScopedRateThrottle
)


class DjoyaltyUserThrottle(UserRateThrottle):
    """Standard authenticated user — 1000/hour।"""
    scope = 'djoyalty_user'
    rate = '1000/hour'


class DjoyaltyAnonThrottle(AnonRateThrottle):
    """Anonymous user — 100/hour।"""
    scope = 'djoyalty_anon'
    rate = '100/hour'


class DjoyaltyBurstThrottle(UserRateThrottle):
    """Burst limit — 60/minute for heavy endpoints।"""
    scope = 'djoyalty_burst'
    rate = '60/minute'


class PointsEarnThrottle(UserRateThrottle):
    """Points earn endpoint — 200/hour per user।"""
    scope = 'djoyalty_earn'
    rate = '200/hour'


class RedemptionThrottle(UserRateThrottle):
    """Redemption requests — 20/hour per user।"""
    scope = 'djoyalty_redeem'
    rate = '20/hour'


class PublicAPIThrottle(ScopedRateThrottle):
    """Partner public API — 500/hour per partner API key।"""
    scope = 'djoyalty_public'
    rate = '500/hour'

    def get_cache_key(self, request, view):
        # Rate limit by API key, not user
        api_key = request.headers.get('X-Loyalty-API-Key', '')
        if api_key:
            return f'throttle_public_api_{api_key}'
        return super().get_cache_key(request, view)


class VoucherValidateThrottle(AnonRateThrottle):
    """Voucher validation — prevent brute force।"""
    scope = 'djoyalty_voucher_validate'
    rate = '30/minute'


class WebhookThrottle(AnonRateThrottle):
    """Inbound webhook — 100/minute per IP।"""
    scope = 'djoyalty_webhook'
    rate = '100/minute'


class AdminActionThrottle(UserRateThrottle):
    """Admin bulk actions — 50/hour।"""
    scope = 'djoyalty_admin'
    rate = '50/hour'


# Settings to add to REST_FRAMEWORK:
DJOYALTY_THROTTLE_SETTINGS = {
    'DEFAULT_THROTTLE_CLASSES': [
        'api.djoyalty.throttles.DjoyaltyUserThrottle',
        'api.djoyalty.throttles.DjoyaltyAnonThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'djoyalty_user': '1000/hour',
        'djoyalty_anon': '100/hour',
        'djoyalty_burst': '60/minute',
        'djoyalty_earn': '200/hour',
        'djoyalty_redeem': '20/hour',
        'djoyalty_public': '500/hour',
        'djoyalty_voucher_validate': '30/minute',
        'djoyalty_webhook': '100/minute',
        'djoyalty_admin': '50/hour',
    }
}

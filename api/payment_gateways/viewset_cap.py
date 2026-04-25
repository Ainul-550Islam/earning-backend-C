# api/payment_gateways/viewset_cap.py
# Capacity-aware viewset mixin — auto-checks caps before processing

from rest_framework.response import Response


class CapAwareViewSetMixin:
    """Viewset mixin that checks conversion/deposit caps before processing."""

    def check_offer_cap(self, offer) -> bool:
        try:
            from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
            result = ConversionCapEngine().check_caps(offer)
            if not result['can_convert']:
                return False, result.get('reason', 'Cap reached')
            return True, ''
        except Exception:
            return True, ''

    def check_rate_limit(self, user, operation: str) -> bool:
        from django.core.cache import cache
        key   = f'rate_limit:{user.id}:{operation}'
        count = cache.get(key, 0)
        if count >= self.get_rate_limit(operation):
            return False
        cache.set(key, count + 1, 3600)
        return True

    def get_rate_limit(self, operation: str) -> int:
        limits = {'deposit': 10, 'withdrawal': 3, 'conversion': 100}
        return limits.get(operation, 50)

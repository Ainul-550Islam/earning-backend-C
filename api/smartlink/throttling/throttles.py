"""
SmartLink Rate Limiting / Throttling
Protects redirect and API endpoints from abuse.
"""
from rest_framework.throttling import SimpleRateThrottle, AnonRateThrottle


class PublicRedirectThrottle(AnonRateThrottle):
    """
    Throttle for /go/<slug>/ endpoint.
    10,000 requests/minute per IP (burst-friendly).
    """
    scope = 'redirect'
    rate = '10000/min'

    def get_cache_key(self, request, view):
        # Per-IP throttle
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class PublisherAPIThrottle(SimpleRateThrottle):
    """
    Per-publisher API throttle: 1000 requests/minute.
    """
    scope = 'publisher_api'
    rate = '1000/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class PostbackThrottle(AnonRateThrottle):
    """
    Postback endpoint throttle: 5000/minute per IP.
    """
    scope = 'postback'
    rate = '5000/min'


class AdminAPIThrottle(SimpleRateThrottle):
    """Admin API: 500/minute."""
    scope = 'admin_api'
    rate = '500/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return None

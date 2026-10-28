"""
SmartLink Rate Limiting / Throttling
Protects redirect and API endpoints from abuse.

Tier-based throttling (FIX):
  Previously PublisherAPIThrottle had a hardcoded 1000/min rate for all publishers.
  Now it reads the publisher's tier from PublisherTier.api_rate_limit and
  applies the correct limit per tier:
    Gold       → 5000/min
    Silver     → 2000/min
    Bronze     → 1000/min
    Standard   → 500/min
    UnderReview→ 100/min
"""
from rest_framework.throttling import SimpleRateThrottle, AnonRateThrottle


class PublicRedirectThrottle(AnonRateThrottle):
    """
    Throttle for /go/<slug>/ endpoint.
    10,000 requests/minute per IP (burst-friendly for viral links).
    """
    scope = 'redirect'
    rate  = '10000/min'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class PublisherAPIThrottle(SimpleRateThrottle):
    """
    Per-publisher API throttle with tier-aware rate limit.

    FIX: Previously hardcoded at 1000/min for all publishers.
    Now reads the publisher's tier to apply the correct rate.
    Falls back to 500/min (Standard tier) if no tier record exists.
    """
    scope = 'publisher_api'
    rate  = '500/min'  # Default (Standard tier) — overridden per request

    # Maps tier → requests per minute
    TIER_RATES = {
        'gold':         5000,
        'silver':       2000,
        'bronze':       1000,
        'standard':     500,
        'under_review': 100,
    }

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }

    def get_rate(self):
        """
        Return rate string for the current request's publisher tier.
        Called by DRF before allow_request(); self.request is set at that point.
        """
        # Default if no request context (e.g. during test setup)
        if not hasattr(self, 'request') or self.request is None:
            return f"{self.TIER_RATES['standard']}/min"

        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return f"{self.TIER_RATES['standard']}/min"

        # Staff always get Gold tier limits
        if user.is_staff:
            return f"{self.TIER_RATES['gold']}/min"

        # Look up publisher tier
        try:
            from api.smartlink.models.extensions.smartlink_schedule import PublisherTier
            tier_obj = PublisherTier.objects.get(publisher=user)
            api_limit = tier_obj.api_rate_limit  # field on PublisherTier model
            if api_limit:
                return f"{api_limit}/min"
            # Fall back to tier name mapping
            rate = self.TIER_RATES.get(tier_obj.tier, self.TIER_RATES['standard'])
            return f"{rate}/min"
        except Exception:
            return f"{self.TIER_RATES['standard']}/min"

    def allow_request(self, request, view):
        """Override to set dynamic rate before DRF evaluates the limit."""
        self.request = request
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


class PostbackThrottle(AnonRateThrottle):
    """
    Postback endpoint throttle: 5,000 requests per minute per IP.
    S2S postbacks can be high-volume from ad networks.
    """
    scope = 'postback'
    rate  = '5000/min'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class AdminAPIThrottle(SimpleRateThrottle):
    """
    Admin API endpoints: 500 requests per minute.
    Admin operations are heavyweight — lower limit protects DB.
    """
    scope = 'admin_api'
    rate  = '500/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {
                'scope': self.scope,
                'ident': request.user.pk,
            }
        return None


class WebhookTestThrottle(SimpleRateThrottle):
    """
    Webhook test endpoint: 10 tests per minute per publisher.
    Prevents flooding third-party endpoints during testing.
    """
    scope = 'webhook_test'
    rate  = '10/min'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {
                'scope': self.scope,
                'ident': request.user.pk,
            }
        return self.get_ident(request)


class ReportExportThrottle(SimpleRateThrottle):
    """
    CSV/JSON export endpoint: 20 exports per hour per publisher.
    Streaming exports are CPU and I/O heavy.
    """
    scope = 'report_export'
    rate  = '20/hour'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {
                'scope': self.scope,
                'ident': request.user.pk,
            }
        return None

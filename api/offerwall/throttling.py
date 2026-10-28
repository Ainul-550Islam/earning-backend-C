"""
api/offerwall/throttling.py

DRF Throttling classes for offerwall module.
Provides 8 throttle strategies to prevent abuse and API overload:
  1. OfferListThrottle — 100 requests/hour for offer list
  2. OfferDetailThrottle — 200 requests/hour for offer detail
  3. OfferClickThrottle — 30 requests/hour per user (prevent click spam)
  4. ConversionThrottle — 10 requests/hour per user (critical operation)
  5. WebhookThrottle — 1000 requests/hour for webhooks
  6. AnalyticsThrottle — 50 requests/hour for analytics queries
  7. AdminThrottle — 500 requests/hour for admin operations
  8. PublicThrottle — 50 requests/hour for unauthenticated users
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, ScopedRateThrottle


class OfferListThrottle(ScopedRateThrottle):
    """
    Throttle for listing offers.
    Scope: 'offer_list'
    Rate: 100 requests per hour (for authenticated users)
    """
    scope = 'offer_list'


class OfferDetailThrottle(ScopedRateThrottle):
    """
    Throttle for retrieving offer details.
    Scope: 'offer_detail'
    Rate: 200 requests per hour (frequent access okay)
    """
    scope = 'offer_detail'


class OfferClickThrottle(ScopedRateThrottle):
    """
    Throttle for clicking/tracking offers.
    Scope: 'offer_click'
    Rate: 30 requests per hour per user (prevent click spam/fraud)
    Keyed by user_id and IP address.
    """
    scope = 'offer_click'
    
    def get_cache_key(self):
        if self.request.user and self.request.user.is_authenticated:
            ident = f"{self.request.user.id}:{self.get_ident(self.request)}"
        else:
            ident = self.get_ident(self.request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class ConversionThrottle(ScopedRateThrottle):
    """
    Throttle for conversion (approval/rejection) operations.
    Scope: 'conversion'
    Rate: 10 requests per hour (critical, infrequent operations)
    Very strict to prevent accidental mass-operations.
    """
    scope = 'conversion'


class WebhookThrottle(ScopedRateThrottle):
    """
    Throttle for incoming webhook events from external providers.
    Scope: 'webhook'
    Rate: 1000 requests per hour (high volume from providers)
    Per IP address to prevent provider from overwhelming us.
    """
    scope = 'webhook'
    
    def get_cache_key(self):
        # Key by IP address for webhooks
        ident = self.get_ident(self.request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class AnalyticsThrottle(ScopedRateThrottle):
    """
    Throttle for analytics and reporting endpoints.
    Scope: 'analytics'
    Rate: 50 requests per hour (analytics queries can be heavy)
    Prevents abuse of expensive database queries.
    """
    scope = 'analytics'


class AdminThrottle(ScopedRateThrottle):
    """
    Throttle for admin/staff operations.
    Scope: 'admin'
    Rate: 500 requests per hour (admins need higher limits)
    Applied to staff-only endpoints.
    """
    scope = 'admin'


class PublicThrottle(AnonRateThrottle):
    """
    Throttle for public/unauthenticated users.
    Rate: 50 requests per hour per IP
    Applied when user is not authenticated.
    """
    scope = 'public'
    
    def allow_request(self, request, view):
        # Only apply to unauthenticated users
        if request.user and request.user.is_authenticated:
            return True
        return super().allow_request(request, view)

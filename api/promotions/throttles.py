    page_size               = 20
    page_size_query_param   = 'page_size'
    max_page_size           = 100
    ordering                = '-created_at'
    cursor_query_param      = 'cursor'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('next',     self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results',  data),
        ]))


class SubmissionCursorPagination(CursorPagination):
    """Submission feed এর জন্য cursor-based pagination।"""
    page_size               = 20
    max_page_size           = 50
    ordering                = '-submitted_at'
    cursor_query_param      = 'cursor'


# =============================================================================
# api/promotions/throttles.py
# Custom Rate Limiting — Spam ও DDoS protection
# =============================================================================

from rest_framework.throttling import (
    AnonRateThrottle, UserRateThrottle, SimpleRateThrottle
)
from .constants import (
    THROTTLE_SUBMISSION_PER_MINUTE,
    THROTTLE_CAMPAIGN_CREATE_PER_DAY,
    THROTTLE_DISPUTE_PER_DAY,
    THROTTLE_ANON_PER_MINUTE,
)


class AnonBurstThrottle(AnonRateThrottle):
    """Anonymous user এর burst request limit।"""
    scope = 'anon_burst'
    rate  = f'{THROTTLE_ANON_PER_MINUTE}/minute'


class AnonSustainedThrottle(AnonRateThrottle):
    """Anonymous user এর sustained request limit।"""
    scope = 'anon_sustained'
    rate  = '200/day'


class UserBurstThrottle(UserRateThrottle):
    """Authenticated user এর burst limit।"""
    scope = 'user_burst'
    rate  = '60/minute'


class UserSustainedThrottle(UserRateThrottle):
    """Authenticated user এর sustained limit।"""
    scope = 'user_sustained'
    rate  = '5000/day'


class SubmissionThrottle(UserRateThrottle):
    """Task submission এর rate limit — spam prevention।"""
    scope = 'submission'
    rate  = f'{THROTTLE_SUBMISSION_PER_MINUTE}/minute'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        # User + Campaign combination এ throttle করো
        campaign_id = view.kwargs.get('campaign_pk') or request.data.get('campaign')
        ident = f'{request.user.pk}_{campaign_id}'
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class CampaignCreateThrottle(UserRateThrottle):
    """Campaign creation এর daily limit।"""
    scope = 'campaign_create'
    rate  = f'{THROTTLE_CAMPAIGN_CREATE_PER_DAY}/day'


class DisputeThrottle(UserRateThrottle):
    """Dispute submission এর daily limit।"""
    scope = 'dispute'
    rate  = f'{THROTTLE_DISPUTE_PER_DAY}/day'


class WithdrawalThrottle(UserRateThrottle):
    """Withdrawal request এর hourly limit।"""
    scope = 'withdrawal'
    rate  = '3/hour'


class IPBasedThrottle(SimpleRateThrottle):
    """IP address ভিত্তিক throttle — সব request এ apply।"""
    scope = 'ip_based'
    rate  = '200/minute'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


class AdminThrottle(UserRateThrottle):
    """Admin action এর higher limit।"""
    scope = 'admin'
    rate  = '500/minute'

    def allow_request(self, request, view):
        # Admin এর জন্য relaxed throttle
        if request.user and request.user.is_staff:
            return True
        return super().allow_request(request, view)

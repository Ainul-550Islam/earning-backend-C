# api/publisher_tools/dependencies.py
"""Publisher Tools — DRF Dependencies & Injectors."""
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext_lazy as _
from .exceptions import PublisherNotFound, PublisherNotActive, APIRateLimitExceeded
from .constants import CACHE_TTL_SHORT
from django.core.cache import cache


def get_current_publisher(request):
    """Request থেকে current publisher extract করে।"""
    user = request.user
    if not user or not user.is_authenticated:
        raise PublisherNotFound()
    try:
        publisher = user.publisher_profile
        if publisher.status != 'active':
            raise PublisherNotActive()
        return publisher
    except Exception:
        raise PublisherNotFound()


def get_publisher_or_none(request):
    """Publisher না থাকলে None return করে।"""
    try:
        return get_current_publisher(request)
    except Exception:
        return None


def require_verified_publisher(request):
    """KYC verified publisher require করে।"""
    publisher = get_current_publisher(request)
    if not publisher.is_kyc_verified:
        from .exceptions import PublisherKYCRequired
        raise PublisherKYCRequired()
    return publisher


def require_premium_publisher(request):
    """Premium বা Enterprise publisher require করে।"""
    publisher = get_current_publisher(request)
    if publisher.tier not in ('premium', 'enterprise'):
        from .exceptions import TierUpgradeRequired
        raise TierUpgradeRequired()
    return publisher


def get_publisher_from_api_key(request):
    """API key থেকে publisher খোঁজে।"""
    api_key = request.headers.get('X-Publisher-Tools-Key', '')
    if not api_key:
        raise PublisherNotFound()
    from .repository import PublisherRepository
    publisher = PublisherRepository.get_by_api_key(api_key)
    if not publisher:
        raise PublisherNotFound()
    return publisher


def check_rate_limit(key: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
    """Rate limiting check। True = allowed, False = blocked."""
    cache_key = f'rate_limit:{key}'
    count = cache.get(cache_key, 0)
    if count >= max_requests:
        raise APIRateLimitExceeded()
    cache.set(cache_key, count + 1, window_seconds)
    return True


def get_tenant_from_request(request):
    """Request থেকে tenant extract করে।"""
    if hasattr(request, 'tenant'):
        return request.tenant
    try:
        return request.user.publisher_profile.tenant
    except Exception:
        return None


class PublisherRateLimitMixin:
    """ViewSet-এ rate limiting add করার mixin।"""

    def get_rate_limit_key(self, request):
        if request.user.is_authenticated:
            return f'publisher:{request.user.id}'
        return f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'

    def check_rate_limit(self, request):
        key = self.get_rate_limit_key(request)
        check_rate_limit(key, max_requests=120, window_seconds=60)


class PublisherContextMixin:
    """ViewSet-এ publisher context add করার mixin।"""

    def get_publisher_context(self, request):
        return {
            'publisher': get_publisher_or_none(request),
            'is_admin':  request.user.is_staff,
            'request':   request,
        }

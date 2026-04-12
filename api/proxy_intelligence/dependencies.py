"""
Proxy Intelligence Dependencies
================================
Reusable DRF dependencies, permissions, and throttles.
"""
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle


class IsProxyAnalyst(BasePermission):
    """
    Allows access to users with 'proxy_analyst' role or staff.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.is_staff or
            request.user.is_superuser or
            getattr(request.user, 'role', '') in ('proxy_analyst', 'fraud_analyst', 'admin')
        )


class IPCheckThrottle(SimpleRateThrottle):
    """Rate limit for the IP check endpoint."""
    scope = 'ip_check'
    THROTTLE_RATES = {'ip_check': '60/minute'}

    def get_cache_key(self, request, view):
        return f"pi_throttle_{request.user.pk if request.user.is_authenticated else request.META.get('REMOTE_ADDR')}"


def get_client_ip(request) -> str:
    """DRF dependency: extract client IP from request."""
    from .utilities.ip_validator import IPValidator
    return IPValidator.extract_from_request(request)


def get_tenant(request):
    """DRF dependency: get tenant from request."""
    return getattr(request, 'tenant', None)

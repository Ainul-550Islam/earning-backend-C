# api/djoyalty/permissions.py
"""
Djoyalty -- custom DRF permissions.

Security fix:
  - IsPublicAPIClient: API key must come from header ONLY (not query_params or body).
    Passing api_key in URL logs it in server logs, proxies, browser history -- a security leak.
  - IsTenantMember: now actually enforces tenant membership (was always returning True).
"""
from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger(__name__)


class IsAuthenticatedAndActive(BasePermission):
    message = 'Authentication required and account must be active.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class IsLoyaltyAdmin(BasePermission):
    message = 'Loyalty admin access required.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsPublicAPIClient(BasePermission):
    """
    Partner merchant public API -- API key via header only.
    Header: X-Loyalty-API-Key: <key>

    SECURITY: Never accept api_key in query params or POST body.
    Keys in URLs appear in server logs, proxy logs, and browser history.
    """
    message = 'Valid API key required (X-Loyalty-API-Key header).'

    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_LOYALTY_API_KEY')
        if not api_key:
            return False
        return self._validate_api_key(api_key)

    def _validate_api_key(self, api_key: str) -> bool:
        try:
            from .models.campaigns import PartnerMerchant
            return PartnerMerchant.objects.filter(api_key=api_key, is_active=True).exists()
        except Exception as e:
            logger.error('IsPublicAPIClient._validate_api_key error: %s', e)
            return False


class IsTenantMember(BasePermission):
    """
    User must belong to the current request tenant.
    """
    message = 'You are not a member of this tenant.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return True  # No tenant context -- allow
        # Check via Customer record linked to this user
        try:
            from .models.core import Customer
            return Customer.objects.filter(
                user=request.user, tenant=tenant
            ).exists()
        except Exception:
            return False


class IsOwnerOrAdmin(BasePermission):
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        customer = getattr(obj, 'customer', None)
        if customer:
            user = getattr(customer, 'user', None)
            if user:
                return user == request.user
        return False


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')

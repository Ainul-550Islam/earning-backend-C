# api/djoyalty/permissions.py
"""
DRF Custom Permissions for Djoyalty।
Tenant isolation + Role-based access control।
"""

import logging
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser, SAFE_METHODS

logger = logging.getLogger(__name__)


class IsAuthenticatedAndActive(BasePermission):
    """
    Authenticated AND active user।
    Suspended customers block হবে।
    """
    message = 'Authentication required and account must be active.'

    def has_permission(self, request, view):
        return (
            request.user is not None
            and request.user.is_authenticated
            and request.user.is_active
        )


class IsTenantMember(BasePermission):
    """
    User কে request-এর tenant এর member হতে হবে।
    TenantMixin এর সাথে ব্যবহার করতে হবে।
    """
    message = 'You do not have access to this tenant.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Superuser সব tenant দেখতে পারে
        if request.user.is_superuser:
            return True
        # Tenant check — TenantMixin থেকে tenant আসে
        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return True  # Tenant নেই মানে tenant-agnostic endpoint
        # User এর tenant match করে কিনা check
        user_tenant = getattr(request.user, 'tenant', None)
        if user_tenant is None:
            # user model-এ tenant field নাও থাকতে পারে — safe fallback
            return True
        return user_tenant == tenant

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        tenant = getattr(request, 'tenant', None)
        obj_tenant = getattr(obj, 'tenant', None)
        if tenant is None or obj_tenant is None:
            return True
        return obj_tenant == tenant


class IsAdminOrReadOnly(BasePermission):
    """
    Admin হলে সব করতে পারবে।
    অন্যরা শুধু read (GET, HEAD, OPTIONS) করতে পারবে।
    """
    message = 'Only admins can perform write operations.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff or request.user.is_superuser


class IsLoyaltyAdmin(BasePermission):
    """
    Loyalty system admin — staff বা superuser।
    Points adjust, tier override, fraud review এর জন্য।
    """
    message = 'Loyalty admin access required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or request.user.is_superuser


class IsOwnerOrAdmin(BasePermission):
    """
    Object owner অথবা admin।
    Customer নিজের data দেখতে পারবে।
    """
    message = 'You can only access your own data.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        # obj.customer বা obj.user দিয়ে check
        owner = getattr(obj, 'customer', None) or getattr(obj, 'user', None)
        if owner is None:
            return True
        # Customer model এর সাথে user link থাকলে
        user_customer = getattr(request.user, 'loyalty_customer', None)
        if user_customer is None:
            return request.user.is_staff
        return owner == user_customer


class CanEarnPoints(BasePermission):
    """
    Points earn করার permission।
    Suspended বা blocked customer earn করতে পারবে না।
    """
    message = 'You are not eligible to earn loyalty points.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_active:
            return False
        return True


class CanRedeemPoints(BasePermission):
    """
    Points redeem করার permission।
    Minimum balance check এখানে নয়, service-এ।
    """
    message = 'You are not eligible to redeem loyalty points.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_active:
            return False
        return True


class CanTransferPoints(BasePermission):
    """
    Points transfer করার permission।
    """
    message = 'Points transfer is not allowed for your account.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_active:
            return False
        return True


class IsPublicAPIClient(BasePermission):
    """
    Public white-label API — API key দিয়ে authenticate।
    Header: X-Loyalty-API-Key
    """
    message = 'Valid API key required.'

    def has_permission(self, request, view):
        api_key = request.headers.get('X-Loyalty-API-Key', '')
        if not api_key:
            return False
        # API key validation — PartnerMerchant model check করবে
        try:
            from .models.campaigns import PartnerMerchant  # noqa: F401
            partner = PartnerMerchant.objects.filter(
                api_key=api_key, is_active=True
            ).first()
            if partner:
                request.partner = partner
                return True
            return False
        except Exception:
            # Model না থাকলে (migration এ আগে) — safe fallback
            logger.warning('PartnerMerchant model not available for API key check.')
            return False


class IsWebhookReceiver(BasePermission):
    """
    Inbound webhook receiver — HMAC signature check।
    Header: X-Loyalty-Signature
    """
    message = 'Invalid webhook signature.'

    def has_permission(self, request, view):
        signature = request.headers.get('X-Loyalty-Signature', '')
        if not signature:
            return False
        try:
            from .webhooks.webhook_security import verify_signature  # noqa: F401
            return verify_signature(request.body, signature)
        except Exception:
            logger.warning('Webhook signature verification unavailable.')
            return False


class IsFraudReviewer(BasePermission):
    """
    Fraud review করার permission — staff only।
    """
    message = 'Fraud review access required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or request.user.is_superuser


class IsReadOnly(BasePermission):
    """
    শুধু read-only — GET, HEAD, OPTIONS।
    Public endpoint এর জন্য।
    """
    message = 'This endpoint is read-only.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


# ==================== COMBINED PERMISSION SETS ====================

# Customer-facing endpoints
CUSTOMER_PERMISSIONS = [IsAuthenticatedAndActive, IsTenantMember]

# Admin-only endpoints
ADMIN_PERMISSIONS = [IsAuthenticatedAndActive, IsLoyaltyAdmin]

# Read-only public endpoints
PUBLIC_READ_PERMISSIONS = [IsReadOnly]

# Fraud management
FRAUD_PERMISSIONS = [IsAuthenticatedAndActive, IsFraudReviewer]

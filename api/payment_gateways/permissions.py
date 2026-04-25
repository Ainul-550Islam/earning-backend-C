# api/payment_gateways/permissions.py
from rest_framework.permissions import BasePermission

class IsOwnerOrAdmin(BasePermission):
    """User can only access their own resources, or admin can access all."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        user_field = getattr(obj, 'user', None)
        return user_field == request.user

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return request.user.is_authenticated
        return request.user.is_staff

class IsGatewayWebhook(BasePermission):
    """Allow unauthenticated webhook callbacks."""
    def has_permission(self, request, view):
        return True  # Webhooks are signature-verified, not auth-verified

class IsPublisherOrAdmin(BasePermission):
    """Requires active publisher profile."""
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        try:
            return request.user.publisher_profile.status == 'active'
        except Exception:
            return False

class IsAdvertiserOrAdmin(BasePermission):
    """Requires active advertiser profile."""
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        try:
            return request.user.advertiser_profile.status == 'active'
        except Exception:
            return False

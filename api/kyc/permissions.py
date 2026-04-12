# kyc/permissions.py  ── WORLD #1
from rest_framework.permissions import BasePermission


class IsKYCOwner(BasePermission):
    """Only the KYC owner can access"""
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsVerifiedUser(BasePermission):
    """Only KYC-verified users"""
    message = 'KYC verification required.'
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        from .models import KYC
        return KYC.objects.filter(user=request.user, status='verified').exists()


class IsTenantAdmin(BasePermission):
    """Tenant-level admin"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or
            getattr(request.user, 'is_tenant_admin', False)
        )


class KYCAdminOrReadOnly(BasePermission):
    """Admin: full access. Authenticated: read only."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_staff

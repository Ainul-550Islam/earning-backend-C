# api/offer_inventory/permissions.py
from rest_framework.permissions import BasePermission


class IsOfferAdmin(BasePermission):
    """Staff বা offer_admin group।"""
    def has_permission(self, request, view):
        return request.user and (
            request.user.is_staff or
            request.user.groups.filter(name='offer_admin').exists()
        )


class IsTenantUser(BasePermission):
    """Tenant-এর user কিনা।"""
    def has_permission(self, request, view):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return True  # No tenant = global
        return request.user.is_authenticated


class IsVerifiedUser(BasePermission):
    """KYC approved user।"""
    message = 'KYC যাচাই প্রয়োজন।'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        from .models import UserKYC
        return UserKYC.objects.filter(
            user=request.user, status='approved'
        ).exists()

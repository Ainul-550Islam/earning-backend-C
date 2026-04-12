"""
api/monetization_tools/permissions.py
========================================
Custom DRF permission classes for the monetization_tools app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils.translation import gettext_lazy as _


class IsOwnerOrAdmin(BasePermission):
    """
    Allow access if request.user owns the object (obj.user == request.user)
    or if the user is staff/admin.
    """
    message = _("You do not have permission to access this resource.")

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return getattr(obj, 'user', None) == request.user


class IsAdminOrReadOnly(BasePermission):
    """Allow read-only for all authenticated users; write only for admins."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class IsVerifiedUser(BasePermission):
    """User must be KYC-verified (is_verified=True) to perform write actions."""
    message = _("KYC verification required to perform this action.")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'is_verified', False)


class IsTenantMember(BasePermission):
    """
    Object-level permission: object must belong to the same tenant
    as the requesting user.
    """
    message = _("Access restricted to your tenant.")

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        request_tenant = getattr(request, 'tenant', None)
        obj_tenant     = getattr(obj, 'tenant', None)
        if request_tenant is None or obj_tenant is None:
            return True  # no tenant context → allow
        return request_tenant == obj_tenant


class CanAccessOfferwall(BasePermission):
    """
    Users must be authenticated and not blocked to access offerwalls.
    """
    message = _("Your account is not eligible to access offerwalls.")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # block if account_level is 'blocked'
        if getattr(request.user, 'account_level', '') == 'blocked':
            return False
        return True


class CanManageCampaign(BasePermission):
    """
    Only staff/admins can create/edit/delete campaigns.
    Any authenticated user can view.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class CanManageSubscription(BasePermission):
    """
    Users can view/cancel their own subscription.
    Admins can manage all.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


class CanManagePublisherAccount(BasePermission):
    """Only staff or the account owner can manage publisher accounts."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.email == request.user.email

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class CanViewAnalytics(BasePermission):
    """Staff can view all analytics. Regular users can see their own."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class CanManageFraudAlerts(BasePermission):
    """Only staff can view or manage fraud alerts."""
    message = _("Only staff can manage fraud alerts.")

    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CanManagePayouts(BasePermission):
    """
    Users can create/view their own payouts.
    Only staff can approve/reject/mark-paid.
    """
    WRITE_ACTIONS = ('approve', 'reject', 'mark_paid', 'create', 'update',
                     'partial_update', 'destroy')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if view.action in self.WRITE_ACTIONS and view.action != 'create':
            return request.user.is_staff
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return getattr(obj, 'user', None) == request.user


class CanManageReferrals(BasePermission):
    """
    Users can view their own referrals.
    Staff can manage all referral programs.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method not in SAFE_METHODS:
            if view.action in ('create', 'update', 'partial_update', 'destroy'):
                return request.user.is_staff
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        user_attr = getattr(obj, 'user', None) or getattr(obj, 'referrer', None)
        return user_attr == request.user


class CanManageFlashSales(BasePermission):
    """Only admins can create/edit flash sales. All users can view live ones."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class CanManageCoupons(BasePermission):
    """Admins manage coupon definitions. Users can validate/redeem."""
    ADMIN_ACTIONS = ('create', 'update', 'partial_update', 'destroy')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if view.action in self.ADMIN_ACTIONS:
            return request.user.is_staff
        return True


class IsAccountActive(BasePermission):
    """Block users whose account_level is 'blocked'."""
    message = _("Your account has been blocked. Contact support.")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, 'account_level', 'normal') != 'blocked'


class CanManagePostbacks(BasePermission):
    """Only staff/admin can view postback logs."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class CanManageSegments(BasePermission):
    """Only staff can manage user segments."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.is_staff
        return request.user.is_staff

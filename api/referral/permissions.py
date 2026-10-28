# api/referral/permissions.py
# Custom DRF permissions for referral system
# ============================================================

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsReferralAdmin(BasePermission):
    """
    Staff user অথবা referral_admin group member।
    """
    message = 'Referral admin access required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return request.user.groups.filter(name='referral_admin').exists()


class IsReferralModerator(BasePermission):
    """
    Fraud review, suspicious referral management।
    """
    message = 'Referral moderator access required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.is_staff:
            return True
        return request.user.groups.filter(
            name__in=['referral_admin', 'referral_moderator']
        ).exists()


class IsOwnerOrAdmin(BasePermission):
    """
    Object owner অথবা admin।
    """
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'referrer'):
            return obj.referrer == request.user
        return False


class IsReferralProgramActive(BasePermission):
    """
    Referral program active কিনা check করো।
    """
    message = 'Referral program is currently inactive.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Admin always allowed
        if request.user.is_staff:
            return True
        try:
            from django.core.cache import cache
            settings = cache.get('referral_settings')
            if settings is None:
                from api.referral.models import ReferralSettings
                settings = ReferralSettings.objects.first()
            if settings:
                return settings.is_active
        except Exception:
            pass
        return True  # Default: allow


class IsVerifiedUser(BasePermission):
    """
    Email verified user only।
    """
    message = 'Please verify your email to access referral features.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Check email_verified field (if exists)
        if hasattr(request.user, 'email_verified'):
            return request.user.email_verified
        # Check profile verified (if exists)
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            if hasattr(profile, 'is_verified'):
                return profile.is_verified
        return True  # Default: allow if no verification field


class ReadOnly(BasePermission):
    """GET requests only।"""
    def has_permission(self, request, view):
        return request.method in ('GET', 'HEAD', 'OPTIONS')
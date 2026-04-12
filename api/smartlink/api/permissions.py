"""
SmartLink Advanced Permission Classes
Fine-grained access control for publisher, admin, and API key users.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.core.cache import cache


class IsPublisherOrAdmin(BasePermission):
    """Publisher or admin full access."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (getattr(request.user, 'is_publisher', False) or request.user.is_staff)
        )


class IsSmartLinkOwnerOrAdmin(BasePermission):
    """Only the SmartLink owner or admin can modify."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        smartlink = getattr(obj, 'smartlink', obj)
        return getattr(smartlink, 'publisher_id', None) == request.user.pk


class CanAccessSmartLinkData(BasePermission):
    """
    Publisher can only access data for SmartLinks they own.
    Admin can access all.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # Walk up the relation chain to find the smartlink
        sl = obj
        for attr in ('smartlink', 'pool__smartlink', 'click__smartlink'):
            if hasattr(sl, 'smartlink'):
                sl = sl.smartlink
                break
        return getattr(sl, 'publisher_id', None) == request.user.pk


class HasAPIKey(BasePermission):
    """User authenticated via API key (for publisher integrations)."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            isinstance(request.auth, str)  # API key is a string, JWT is a token object
        )


class IsVerifiedPublisher(BasePermission):
    """Only publishers with verified email and active account."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return (
            getattr(request.user, 'is_publisher', False) and
            request.user.is_active and
            getattr(request.user, 'email_verified', True)
        )


class ReadOnlyOrAdmin(BasePermission):
    """Read-only for all authenticated users, write for admin only."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class PublisherRateLimitPermission(BasePermission):
    """
    Block publisher if they are over their allocated SmartLink quota.
    Checked via Redis cache for performance.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if request.method not in ('POST',):
            return True

        # Check SmartLink count quota
        cache_key = f'sl_count:{request.user.pk}'
        count = cache.get(cache_key)
        if count is None:
            from api.smartlink.models import SmartLink
            from api.smartlink.constants import MAX_SMARTLINKS_PER_PUBLISHER
            count = SmartLink.objects.filter(
                publisher=request.user, is_archived=False
            ).count()
            cache.set(cache_key, count, 60)

        from api.smartlink.constants import MAX_SMARTLINKS_PER_PUBLISHER
        return count < MAX_SMARTLINKS_PER_PUBLISHER

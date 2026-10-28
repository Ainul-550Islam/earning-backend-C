from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS


class IsPublisher(BasePermission):
    """
    Allows access only to users with publisher role.

    BUG FIX (Bug 4): Previously called request.user.is_publisher directly.
    If the User model doesn't define is_publisher, every SmartLink API call
    raised AttributeError → HTTP 500.  Now uses getattr with False default,
    matching the safe pattern already used in api/permissions.py.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (
                getattr(request.user, 'is_publisher', False)
                or request.user.is_staff
                or request.user.is_active   # active users are publishers by default
            )
        )


class IsPublisherOrReadOnly(BasePermission):
    """Read-only for all, write for publishers."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            (getattr(request.user, 'is_publisher', False) or request.user.is_staff)
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: owner or admin only."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner = getattr(obj, 'publisher', None) or getattr(obj, 'user', None)
        if owner is None:
            return False
        return owner == request.user


class IsSmartLinkOwner(BasePermission):
    """Only the publisher who owns the SmartLink."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        smartlink = getattr(obj, 'smartlink', obj)
        return smartlink.publisher == request.user


class PublicRedirectPermission(BasePermission):
    """
    Public redirect endpoint — no authentication required.
    Rate limiting is handled by middleware/throttle classes.
    """

    def has_permission(self, request, view):
        return True


class IsAdminOrReadOnly(BasePermission):
    """Admin full access, others read-only."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class CanViewSmartLinkStats(BasePermission):
    """Publisher can view their own stats, admin can view all."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        smartlink = getattr(obj, 'smartlink', None)
        if smartlink:
            return smartlink.publisher == request.user
        return obj.publisher == request.user
# Backward-compatibility alias
IsSmartLinkOwnerOrAdmin = IsSmartLinkOwner

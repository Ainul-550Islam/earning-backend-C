from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS


class IsPublisher(BasePermission):
    """Allows access only to users with publisher role."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_publisher or request.user.is_staff)
        )


class IsPublisherOrReadOnly(BasePermission):
    """Read-only for all, write for publishers."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_publisher or request.user.is_staff)
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

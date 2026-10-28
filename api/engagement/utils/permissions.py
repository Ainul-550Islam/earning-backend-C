# engagement/utils/permissions.py
from rest_framework.permissions import BasePermission


class IsOwnerOrAdmin(BasePermission):
    """Allow access if request.user owns the object or is staff."""

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        owner = getattr(obj, "user", None)
        return owner == request.user


class IsTenantMember(BasePermission):
    """Allow access if user's tenant matches the object's tenant."""

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        user_tenant   = getattr(request.user, "tenant_id", None)
        object_tenant = getattr(obj, "tenant_id", None)
        if object_tenant is None:
            return True
        return user_tenant == object_tenant


class IsAdminOrReadOnly(BasePermission):
    """Safe methods (GET, HEAD, OPTIONS) for any authenticated user; write for admin only."""

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)

"""
Gamification Permissions
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS, IsAdminUser


class IsAdminOrReadOnly(BasePermission):
    """
    Allow read-only access to any authenticated/anonymous user.
    Write access is restricted to admin users.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allow access if the requesting user owns the object
    (obj.user == request.user) or is a staff/admin user.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user and request.user.is_staff:
            return True
        return hasattr(obj, "user") and obj.user_id == request.user.pk

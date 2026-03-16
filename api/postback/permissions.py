from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsPostbackAdmin(BasePermission):
    """Full postback administration – staff or superuser."""
    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))


class IsReadOnlyOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)

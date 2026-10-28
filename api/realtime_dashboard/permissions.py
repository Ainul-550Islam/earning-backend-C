"""
Permission classes for Real-time Dashboard Backend.
"""
from rest_framework.permissions import BasePermission


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    Allow read-only access to unauthenticated requests,
    full access to authenticated requests.

    Use for public dashboards that guests can view but not modify.
    """

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return bool(request.user and request.user.is_authenticated)


class IsDashboardOwner(BasePermission):
    """
    Object-level permission: only the user who created/owns the
    UserDashboard may modify it.

    Applied via `permission_classes = [IsAuthenticated, IsDashboardOwner]`
    on UserDashboardViewSet and checked during retrieve/update/delete.
    """

    def has_object_permission(self, request, view, obj):
        # Read access for any authenticated user
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        # Write access only for the dashboard owner
        return str(obj.user_id) == str(request.user.pk)


class IsAdminOrReadOnly(BasePermission):
    """
    Allow read-only access to any authenticated user,
    full access only to admin/staff users.

    Use for DashboardLayout and other shared configuration models
    that regular users should not be able to create or delete.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_staff

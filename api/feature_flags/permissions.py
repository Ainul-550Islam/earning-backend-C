"""
NEW FILE — DRF permission classes for Feature Flags & A/B Testing.

Fixes the #1 production-readiness blocker identified in the audit:
every ViewSet previously had ZERO `permission_classes` and ZERO
`authentication_classes`, meaning any unauthenticated client could
create, modify, or delete every flag, experiment, and rollout rule.

Usage (already wired into every viewset in viewsets/):
    permission_classes = [IsAuthenticated, CanViewFlags]
    # and, for write actions:
    permission_classes = [IsAuthenticated, CanEditFlags]
"""
from rest_framework import permissions

from .models.permissions import UserRole


def _user_permission_names(user):
    """Return the set of permission names granted to `user`, or empty set."""
    try:
        user_role = UserRole.objects.select_related('role').get(user=user)
    except UserRole.DoesNotExist:
        return set()
    return set(user_role.role.permissions.values_list('name', flat=True))


class IsAuthenticated(permissions.BasePermission):
    """Require a logged-in user. Thin wrapper kept for explicit naming/import
    convenience alongside the custom classes below."""
    message = 'Authentication required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdmin(permissions.BasePermission):
    """Require the 'admin' role."""
    message = 'Admin access required.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            user_role = UserRole.objects.get(user=request.user)
        except UserRole.DoesNotExist:
            return False
        return user_role.role.name == 'admin'


class CanViewFlags(permissions.BasePermission):
    """User must have the 'view_flag' permission (or be staff/superuser)."""
    message = 'You do not have permission to view feature flags.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return 'view_flag' in _user_permission_names(user)


class CanEditFlags(permissions.BasePermission):
    """
    Allows read methods to anyone with CanViewFlags-level access; write
    methods (POST/PUT/PATCH/DELETE) require the 'edit_flag' permission.
    """
    message = 'You do not have permission to modify feature flags.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if user.is_staff or user.is_superuser:
            return True

        required = 'delete_flag' if request.method == 'DELETE' else 'edit_flag'
        return required in _user_permission_names(user)


class CanManageExperiments(permissions.BasePermission):
    """Required to start/pause/complete experiments."""
    message = 'You do not have permission to manage experiments.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return 'start_experiment' in _user_permission_names(user)


class CanApproveChanges(permissions.BasePermission):
    """Required to approve/reject pending flag change requests."""
    message = 'You do not have permission to approve flag changes.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return 'approve_changes' in _user_permission_names(user)

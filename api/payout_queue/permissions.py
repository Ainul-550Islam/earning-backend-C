"""Payout Queue Permissions"""
from rest_framework.permissions import BasePermission


class IsStaffOrSuperuser(BasePermission):
    """Allow only staff or superusers."""
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ))

# =============================================================================
# behavior_analytics/permissions.py
# =============================================================================
"""
Object-level DRF permissions for behavior_analytics.

Design rules:
  - has_permission:  request-level guard (authenticated, correct role).
  - has_object_permission: row-level guard (owns the object OR is staff).
  - Staff/admin always pass object-level checks.
  - We never raise exceptions inside permission classes — return True/False.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwnerOrStaff(BasePermission):
    """
    Allow access to the object owner or any staff/superuser.

    Works for any model that has a `user` FK **or** a nested path with
    a `user` attribute (e.g. ClickMetric → path → user).

    Attribute resolution order:
        1.  obj.user
        2.  obj.path.user
        3.  Deny
    """

    message = "You do not have permission to access this resource."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(
        self, request: Request, view: APIView, obj
    ) -> bool:
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Resolve the owner
        owner = getattr(obj, "user", None)
        if owner is None:
            # Try nested path (e.g. ClickMetric, StayTime)
            path = getattr(obj, "path", None)
            owner = getattr(path, "user", None)

        if owner is None:
            return False

        return owner == request.user


class IsStaffOnly(BasePermission):
    """
    Restricts access to staff users entirely.
    Used for admin-facing analytics endpoints.
    """

    message = "Only staff members can access this endpoint."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsReadOnlyOrStaff(BasePermission):
    """
    Safe (read) methods are allowed for authenticated users.
    Unsafe (write) methods require staff.
    """

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    message = "Write operations require staff permissions."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return request.user.is_staff

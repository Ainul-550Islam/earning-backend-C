# =============================================================================
# version_control/permissions.py
# =============================================================================
"""
DRF permissions for version_control.

Version-check endpoint: public (any client can call it).
Policy & Maintenance management: staff only.
PlatformRedirect read: authenticated users; write: staff only.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


class IsStaffOnly(BasePermission):
    """Only staff / admin users may access this endpoint."""
    message = "Only staff members can perform this action."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class IsStaffOrReadOnly(BasePermission):
    """
    Authenticated users may read (GET/HEAD/OPTIONS).
    Only staff may write (POST/PUT/PATCH/DELETE).
    """
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    message = "Write operations require staff permissions."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return request.user.is_staff


class AllowAny(BasePermission):
    """
    Unrestricted access — used for the public version-check endpoint
    so mobile/web clients can call it without credentials.
    """
    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

# =============================================================================
# auto_mod/permissions.py
# =============================================================================

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


class IsModeratorOrStaff(BasePermission):
    """
    Allow access if the user is staff OR has the 'moderator' group/perm.
    """
    message = "Only moderators or staff members can perform this action."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff:
            return True
        return user.groups.filter(name="moderators").exists()


class IsStaffOnly(BasePermission):
    message = "Only staff members can perform this action."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsOwnerOrModerator(BasePermission):
    """
    For SuspiciousSubmission:
      - The submitter can read their own submission.
      - Moderators and staff can read & write.
    """
    message = "You do not have permission to access this submission."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        user = request.user
        if user.is_staff:
            return True
        if user.groups.filter(name="moderators").exists():
            return True
        # Owners can only read their own submissions
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return getattr(obj, "submitted_by_id", None) == user.pk
        return False


class CanManageRules(BasePermission):
    """Only staff can create/edit/delete moderation rules."""
    message = "Only staff can manage moderation rules."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.is_staff or request.user.groups.filter(name="moderators").exists()
        return request.user.is_staff

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        # System rules are read-only even for staff via API
        if getattr(obj, "is_system", False) and request.method in ("PUT", "PATCH", "DELETE"):
            return False
        return request.user.is_staff

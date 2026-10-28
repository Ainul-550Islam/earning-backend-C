# =============================================================================
# fraud_detection/permissions.py
#
# Custom DRF Permission classes for the Fraud Detection system.
# =============================================================================
from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_perm(request, codename: str) -> bool:
    """Check Django permission or group-based permission."""
    if request.user.is_superuser:
        return True
    perm = f'fraud_detection.{codename}'
    return request.user.has_perm(perm)


# ---------------------------------------------------------------------------
# Core permissions
# ---------------------------------------------------------------------------

class HasFraudDetectionPermission(BasePermission):
    """
    General gate: user must be authenticated AND have at least one
    fraud_detection permission, OR be staff / superuser.
    """
    message = 'You do not have permission to access fraud detection features.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        # Any fraud_detection permission counts
        return any(
            request.user.has_perm(f'fraud_detection.{p}')
            for p in (
                'view_fraudattempt',
                'change_fraudattempt',
                'view_fraudrule',
                'change_fraudrule',
                'view_fraudcase',
                'change_fraudcase',
                'view_fraudalert',
                'change_fraudalert',
                'view_userriskprofile',
                'change_userriskprofile',
            )
        )


class CanManageFraudRules(BasePermission):
    """
    Allows creating, updating, enabling, and disabling fraud rules.
    Required for FraudRuleViewSet write operations.
    """
    message = 'You do not have permission to manage fraud rules.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return _has_perm(request, 'view_fraudrule')
        return _has_perm(request, 'change_fraudrule') or request.user.is_staff


class CanReviewFraudCases(BasePermission):
    """
    Allows reading, commenting, assigning, escalating, and resolving fraud cases.
    Required for FraudCaseViewSet and ReviewAPIView.
    """
    message = 'You do not have permission to review fraud cases.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return _has_perm(request, 'view_fraudcase')
        return _has_perm(request, 'change_fraudcase') or request.user.is_staff


class CanViewRiskProfiles(BasePermission):
    """
    Read-only access to user risk profiles and the risk assessment dashboard.
    """
    message = 'You do not have permission to view risk profiles.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return _has_perm(request, 'view_userriskprofile') or request.user.is_staff


class CanBanUsers(BasePermission):
    """
    Allows the AutoBanAPIView to ban, suspend, restrict, and unban users.
    Restricted to staff/admin roles.
    """
    message = 'You do not have permission to ban or suspend users.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Explicit Django permission OR staff membership
        return _has_perm(request, 'can_ban_users') or request.user.is_staff


class CanManageWhitelist(BasePermission):
    """
    Allows creating, deactivating, and bulk-managing whitelist entries.
    """
    message = 'You do not have permission to manage the fraud whitelist.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return _has_perm(request, 'view_fraudwhitelist') or request.user.is_staff
        return _has_perm(request, 'change_fraudwhitelist') or request.user.is_staff


class IsAdminOrReadOnly(BasePermission):
    """Staff can write; authenticated users can read."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_staff or request.user.is_superuser


class IsOwnerOrStaff(BasePermission):
    """Object-level: owner of a record OR staff."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        # Support objects that have either .user or .user_id
        owner = getattr(obj, 'user', None) or getattr(obj, 'user_id', None)
        if owner is None:
            return False
        user_id = getattr(owner, 'pk', owner)
        return user_id == request.user.pk

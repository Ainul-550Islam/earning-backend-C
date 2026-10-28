# cms/permissions.py
"""
CMS Permissions System

Per-model permission classes for all ViewSets.

Classes:
  - CMSBasePermission        — shared base logic
  - IsOwnerOrAdmin           — owner or staff only
  - IsAdminOrReadOnly        — admin write, anyone read
  - IsAuthenticatedOrReadOnly (re-exported)
  - IsBlogAuthorOrAdmin      — blog author or admin
  - IsContentEditorOrAdmin   — editors & admins
  - IsFinanceAdminOnly       — finance operations
  - IsVerifiedUserOrAdmin    — verified users
  - IsSuperAdminOnly         — superuser only
  - CanManageOffers          — offer managers
  - CanApproveWithdrawals    — finance staff
  - CanManageSurveys         — survey managers
  - CanViewAnalytics         — analysts and admins
  - CanManageMedia           — media managers
  - IsSessionOwner           — session owner only
  - CanManageReferrals       — referral managers
  - IsWorkflowAdmin          — workflow administrators
"""

from rest_framework import permissions
import logging

logger = logging.getLogger('cms.permissions')


# ─────────────────────────────────────────────────────────────────────────────
# BASE PERMISSION
# ─────────────────────────────────────────────────────────────────────────────

class CMSBasePermission(permissions.BasePermission):
    """
    Base CMS permission with shared helpers.
    """

    def _is_staff_or_superuser(self, request) -> bool:
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))

    def _is_authenticated(self, request) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def _is_safe_method(self, request) -> bool:
        return request.method in permissions.SAFE_METHODS


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC PERMISSIONS
# ─────────────────────────────────────────────────────────────────────────────

class IsOwnerOrAdmin(CMSBasePermission):
    """
    Object-level: allow owners to read/edit their own objects.
    Admins have full access.

    Usage:
        permission_classes = [IsOwnerOrAdmin]
    """
    message = "You do not have permission to access this object."

    def has_permission(self, request, view):
        return self._is_authenticated(request)

    def has_object_permission(self, request, view, obj):
        if self._is_staff_or_superuser(request):
            return True
        # Check common owner field names
        for field in ('user', 'author', 'created_by', 'owner', 'uploaded_by'):
            owner = getattr(obj, field, None)
            if owner is not None:
                return owner == request.user
        return False


class IsAdminOrReadOnly(CMSBasePermission):
    """
    Admins can write; anyone (authenticated or not) can read.

    Usage:
        permission_classes = [IsAdminOrReadOnly]
    """
    message = "Only admin users can modify this resource."

    def has_permission(self, request, view):
        if self._is_safe_method(request):
            return True
        return self._is_staff_or_superuser(request)


class IsAuthenticatedOrPublicReadOnly(CMSBasePermission):
    """
    Authenticated users have full access; unauthenticated can only read.
    """

    def has_permission(self, request, view):
        if self._is_safe_method(request):
            return True
        return self._is_authenticated(request)




IsCMSAdmin = IsAdminOrReadOnly


# ─────────────────────────────────────────────────────────────────────────────
# ROLE-BASED PERMISSIONS
# ─────────────────────────────────────────────────────────────────────────────

class IsBlogAuthorOrAdmin(CMSBasePermission):
    """
    Blog authors can create/edit their own posts.
    Admins have full access.

    Usage:
        permission_classes = [IsBlogAuthorOrAdmin]
    """
    message = "Only blog authors or admins can perform this action."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return self._is_safe_method(request)
        if self._is_staff_or_superuser(request):
            return True
        # Check if user has 'blog_author' group or permission
        return (
            request.user.groups.filter(name__in=['blog_author', 'content_editor']).exists()
            or request.user.has_perm('cms.add_blogpost')
        )

    def has_object_permission(self, request, view, obj):
        if self._is_staff_or_superuser(request):
            return True
        if self._is_safe_method(request):
            return True
        author = getattr(obj, 'author', getattr(obj, 'created_by', None))
        return author == request.user


class IsContentEditorOrAdmin(CMSBasePermission):
    """
    Content editors and admins can write; others read.

    Usage:
        permission_classes = [IsContentEditorOrAdmin]
    """
    message = "Only content editors or admins can perform this action."

    def has_permission(self, request, view):
        if self._is_safe_method(request):
            return self._is_authenticated(request)
        if self._is_staff_or_superuser(request):
            return True
        return request.user.groups.filter(
            name__in=['content_editor', 'cms_editor']
        ).exists()


class IsFinanceAdminOnly(CMSBasePermission):
    """
    Only finance admins or superusers can access.

    Usage:
        permission_classes = [IsFinanceAdminOnly]
    """
    message = "Finance admin access required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_staff
            and request.user.groups.filter(name='finance_admin').exists()
        )


class IsVerifiedUserOrAdmin(CMSBasePermission):
    """
    Only verified users (email confirmed) or admins.

    Usage:
        permission_classes = [IsVerifiedUserOrAdmin]
    """
    message = "Please verify your email address to access this feature."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        # Check email verification (using common field names)
        profile = getattr(request.user, 'profile', None)
        if profile:
            return getattr(profile, 'email_verified', False) or getattr(profile, 'is_verified', False)
        return getattr(request.user, 'email_verified', True)  # default allow if no field


class IsSuperAdminOnly(CMSBasePermission):
    """
    Superusers only (e.g., system config, dangerous operations).

    Usage:
        permission_classes = [IsSuperAdminOnly]
    """
    message = "Superuser access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE-SPECIFIC PERMISSIONS
# ─────────────────────────────────────────────────────────────────────────────

class CanManageOffers(CMSBasePermission):
    """
    Permission to manage CPA offers and offerwalls.

    Usage:
        permission_classes = [CanManageOffers]
    """
    message = "Offer management permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        return (
            request.user.groups.filter(name='offer_manager').exists()
            or request.user.has_perm('cms.manage_offers')
        )


class CanApproveWithdrawals(CMSBasePermission):
    """
    Permission to approve/reject withdrawal requests.

    Usage:
        permission_classes = [CanApproveWithdrawals]
    """
    message = "Withdrawal approval permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_staff
            and (
                request.user.groups.filter(name__in=['finance_admin', 'withdrawal_approver']).exists()
                or request.user.has_perm('cms.approve_withdrawal')
            )
        )


class CanManageSurveys(CMSBasePermission):
    """
    Permission to create/edit surveys.

    Usage:
        permission_classes = [CanManageSurveys]
    """
    message = "Survey management permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return self._is_safe_method(request)
        if self._is_staff_or_superuser(request):
            return True
        return request.user.groups.filter(name='survey_manager').exists()


class CanViewAnalytics(CMSBasePermission):
    """
    Permission to view analytics dashboards.

    Usage:
        permission_classes = [CanViewAnalytics]
    """
    message = "Analytics access permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        return request.user.groups.filter(
            name__in=['analyst', 'marketing', 'content_editor']
        ).exists()


class CanManageMedia(CMSBasePermission):
    """
    Permission to upload/edit media files.

    Usage:
        permission_classes = [CanManageMedia]
    """
    message = "Media management permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        return (
            request.user.groups.filter(name__in=['media_manager', 'content_editor']).exists()
            or request.user.has_perm('cms.add_mediafile')
        )

    def has_object_permission(self, request, view, obj):
        if self._is_staff_or_superuser(request):
            return True
        if self._is_safe_method(request):
            return True
        uploader = getattr(obj, 'uploaded_by', getattr(obj, 'created_by', None))
        return uploader == request.user


class IsSessionOwner(CMSBasePermission):
    """
    Only the session owner or admins can view/terminate.

    Usage:
        permission_classes = [IsSessionOwner]
    """
    message = "You can only access your own sessions."

    def has_permission(self, request, view):
        return self._is_authenticated(request)

    def has_object_permission(self, request, view, obj):
        if self._is_staff_or_superuser(request):
            return True
        return obj.user == request.user


class CanManageReferrals(CMSBasePermission):
    """
    Permission to manage referral programs.

    Usage:
        permission_classes = [CanManageReferrals]
    """
    message = "Referral management permission required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        if self._is_safe_method(request):
            return True
        return request.user.groups.filter(name='referral_manager').exists()


class IsWorkflowAdmin(CMSBasePermission):
    """
    Only workflow administrators can manage workflow definitions.

    Usage:
        permission_classes = [IsWorkflowAdmin]
    """
    message = "Workflow administrator access required."

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if request.user.is_superuser:
            return True
        return (
            request.user.is_staff
            and request.user.groups.filter(name='workflow_admin').exists()
        )


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE PERMISSIONS (combine multiple)
# ─────────────────────────────────────────────────────────────────────────────

class IsOwnerOrReadOnly(CMSBasePermission):
    """
    Object owner can write; authenticated users can read.
    """

    def has_permission(self, request, view):
        return self._is_authenticated(request)

    def has_object_permission(self, request, view, obj):
        if self._is_safe_method(request):
            return True
        if self._is_staff_or_superuser(request):
            return True
        for field in ('user', 'author', 'created_by', 'owner'):
            owner = getattr(obj, field, None)
            if owner is not None:
                return owner == request.user
        return False


class IsStaffOrOwnerCreate(CMSBasePermission):
    """
    Staff can do anything; regular users can only create (POST).
    """

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False
        if self._is_staff_or_superuser(request):
            return True
        return request.method == 'POST'

    def has_object_permission(self, request, view, obj):
        if self._is_staff_or_superuser(request):
            return True
        for field in ('user', 'author', 'created_by', 'owner'):
            owner = getattr(obj, field, None)
            if owner is not None:
                return owner == request.user
        return False


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT ALL
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    'CMSBasePermission',
    'IsOwnerOrAdmin',
    'IsAdminOrReadOnly',
    'IsAuthenticatedOrPublicReadOnly',
    'IsBlogAuthorOrAdmin',
    'IsContentEditorOrAdmin',
    'IsFinanceAdminOnly',
    'IsVerifiedUserOrAdmin',
    'IsSuperAdminOnly',
    'CanManageOffers',
    'CanApproveWithdrawals',
    'CanManageSurveys',
    'CanViewAnalytics',
    'CanManageMedia',
    'IsSessionOwner',
    'CanManageReferrals',
    'IsWorkflowAdmin',
    'IsOwnerOrReadOnly',
    'IsStaffOrOwnerCreate',
]

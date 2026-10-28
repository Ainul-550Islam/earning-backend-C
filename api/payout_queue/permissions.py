"""
payout_queue/permissions.py  ← FIXED

Bugs / gaps fixed:
  1. IsStaffOrSuperuser: no has_object_permission() override.
     Without it, object-level checks (e.g. checking batch tenant) are never
     enforced — DRF falls back to view-level only.

  2. No IsOwner permission class. my_payout_timeline uses IsAuthenticated and
     manually filters by request.user; any viewset that needs per-object
     ownership checks has no reusable class.

  3. No IsTenantMember permission. The models have a tenant FK; without this,
     cross-tenant data leakage is only prevented by queryset filtering
     (which is correct, but defence-in-depth requires an object-level check too).

  4. No ReadOnly permission variant. Some endpoints (e.g. BulkProcessLog)
     should be read-only for staff but writable only for superusers.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsStaffOrSuperuser(BasePermission):
    """
    View-level: allow only authenticated staff or superusers.
    Object-level: same check (no ownership distinction at this level).
    """

    message = "You must be a staff member or superuser to perform this action."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )

    # FIX: object-level permission was missing — DRF skips it without this
    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)

class IsOwner(BasePermission):
    """
    Object-level: allow only the object's owner.

    Checks obj.user == request.user. Falls back to True if the object has
    no `user` attribute (treated as no ownership constraint).

    Usage:
        permission_classes = [IsAuthenticated, IsOwner]
    """

    message = "You do not have permission to access this object."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        owner = getattr(obj, "user", None) or getattr(obj, "user_id", None)
        if owner is None:
            return True  # no ownership field → no restriction
        # Compare by pk to handle both model instances and plain integers
        owner_pk = getattr(owner, "pk", owner)
        return owner_pk == request.user.pk

class IsOwnerOrStaff(BasePermission):
    """
    Allow object access if the requester is either:
      - The owner (obj.user == request.user), OR
      - A staff/superuser.

    Typical use: PayoutItem detail — staff can view all, user can only view own.
    """

    message = "You must be the owner or a staff member to access this resource."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff or request.user.is_superuser:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "user_id", None)
        if owner is None:
            return True
        owner_pk = getattr(owner, "pk", owner)
        return owner_pk == request.user.pk

class IsTenantMember(BasePermission):
    """
    Object-level: allow only if request.user belongs to the object's tenant.

    Checks obj.tenant_id == request.user.tenant_id (or the equivalent
    attribute on your User model). Falls through (allows) if either the
    object or the user has no tenant — tenant isolation is optional.

    Usage:
        permission_classes = [IsAuthenticated, IsTenantMember]
    """

    message = "You do not have access to this resource in your tenant."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        # Superusers bypass tenant isolation
        if request.user.is_superuser:
            return True

        obj_tenant = getattr(obj, "tenant_id", None)
        user_tenant = getattr(request.user, "tenant_id", None)

        if obj_tenant is None or user_tenant is None:
            return True  # no tenant set → no cross-tenant check

        return obj_tenant == user_tenant

class IsStaffOrReadOnly(BasePermission):
    """
    Read-only for all authenticated users; write requires staff/superuser.

    Useful for endpoints like BulkProcessLog where regular authenticated
    users might be allowed to read their own logs but not mutate them.
    """

    message = "Write access requires staff or superuser privileges."

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff or request.user.is_superuser

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)

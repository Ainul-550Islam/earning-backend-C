# =============================================================================
# fraud_detection/tenant_permissions.py  — DRF TENANT-AWARE PERMISSIONS
# DRY: Extend existing permissions.py; no duplicate permission logic.
# =============================================================================
from __future__ import annotations
from rest_framework.permissions import BasePermission


class IsOrganisationMember(BasePermission):
    """Allow access only to members of request.organisation."""
    message = "You must be a member of this organisation."

    def has_permission(self, request, view):
        org = getattr(request, "organisation", None)
        if not org:
            return False
        try:
            from api.fraud_detection.models_tenant import OrganisationMember
            return OrganisationMember.objects.filter(
                organisation=org, user=request.user
            ).exists()
        except Exception:
            return False


class IsOrganisationAdmin(BasePermission):
    """Allow access only to admin/owner members."""
    message = "You must be an admin of this organisation."

    def has_permission(self, request, view):
        org = getattr(request, "organisation", None)
        if not org:
            return False
        try:
            from api.fraud_detection.models_tenant import OrganisationMember
            member = OrganisationMember.objects.get(organisation=org, user=request.user)
            return member.is_admin()
        except Exception:
            return False


class IsSameOrganisation(BasePermission):
    """Object-level: object must belong to request.organisation."""
    message = "This resource belongs to a different organisation."

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organisation", None)
        if not org:
            return False
        obj_org = getattr(obj, "organisation", None) or getattr(obj, "org", None)
        return obj_org == org


class OrganisationRateLimitPermission(BasePermission):
    """Enforce plan-based rate limits per organisation."""
    message = "Rate limit exceeded for your plan."

    PLAN_LIMITS = {
        "free":       100,
        "starter":    1_000,
        "growth":     10_000,
        "enterprise": 1_000_000,
    }

    def has_permission(self, request, view):
        org = getattr(request, "organisation", None)
        if not org:
            return True  # no org = fall through to other auth
        from django.core.cache import cache
        from django.utils import timezone
        import datetime
        key   = f"org_rate:{org.pk}:{timezone.now().strftime('%Y%m%d%H')}"
        count = cache.get(key, 0)
        limit = self.PLAN_LIMITS.get(org.plan, 100)
        if count >= limit:
            return False
        cache.set(key, count + 1, timeout=3600)
        return True

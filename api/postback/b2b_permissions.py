"""b2b_permissions.py — DRF permission classes for the B2B system."""
from rest_framework.permissions import BasePermission
from .b2b_models import OrganizationMember


class IsOrganizationMember(BasePermission):
    """Allow only active members of the organisation referenced in the URL."""
    def has_object_permission(self, request, view, obj):
        org = getattr(obj, "organization", obj if hasattr(obj, "members") else None)
        if not org:
            return False
        return OrganizationMember.objects.filter(
            organization=org, user=request.user, status="active"
        ).exists()


class HasAPIKeyScope(BasePermission):
    """Allow requests authenticated via B2BAPIKey with required scope."""
    required_scope = "read"

    def has_permission(self, request, view):
        api_key = getattr(request, "b2b_api_key", None)
        if not api_key:
            return False
        return api_key.has_scope(self.required_scope)


class B2BAPIKeyAuthentication:
    """Minimal DRF authenticator — reads X-API-Key header."""
    keyword = "X-API-Key"

    def authenticate(self, request):
        from .b2b_models import B2BAPIKey
        raw = request.META.get("HTTP_X_API_KEY", "")
        if not raw:
            return None
        key = B2BAPIKey.verify(raw)
        if not key:
            return None
        request.b2b_api_key = key
        return (key.organization.owner, None)

# =============================================================================
# fraud_detection/tenant_middleware.py  — REQUEST-LEVEL TENANT ISOLATION
# DRY: Single place where Organisation is resolved for every request.
# Add to settings: MIDDLEWARE += ['api.fraud_detection.tenant_middleware.TenantMiddleware']
# =============================================================================
from __future__ import annotations
import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)
_ORG_HEADER  = "X-Organisation-Key"
_ORG_ATTR    = "organisation"
_PUBLIC_PATHS = ("/api/health/", "/api/fraud/external/health/", "/admin/")


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves Organisation from X-Organisation-Key header and attaches it to
    request.organisation. Returns 401 for missing/invalid keys on protected paths.
    """

    def process_request(self, request):
        # Skip public paths and admin
        if any(request.path.startswith(p) for p in _PUBLIC_PATHS):
            request.organisation = None
            return None

        api_key = request.headers.get(_ORG_HEADER) or request.GET.get("org_key")
        if not api_key:
            request.organisation = None
            return None  # let views enforce auth themselves

        try:
            from api.fraud_detection.models_tenant import Organisation
            org = Organisation.get_by_api_key(api_key)
            if org is None:
                return JsonResponse(
                    {"error": "Invalid or inactive organisation key", "code": "invalid_org_key"},
                    status=401,
                )
            request.organisation = org
        except Exception as exc:
            logger.error("TenantMiddleware error: %s", exc, exc_info=True)
            request.organisation = None

        return None


def get_current_organisation(request):
    """Helper: return Organisation from request or None."""
    return getattr(request, _ORG_ATTR, None)


def require_organisation(view_func):
    """Decorator: reject request if no organisation is resolved."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, "organisation", None):
            return JsonResponse(
                {"error": "Organisation key required", "code": "no_org"},
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return wrapper

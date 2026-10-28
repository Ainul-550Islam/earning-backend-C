"""
marketplace/tests_utils.py — Test helpers
"""
from api.tenants.models import Tenant


class TenantFromHeaderMiddleware:
    """
    Sets request.tenant from X-Tenant-ID header (test use only).
    In production, real tenant middleware resolves by domain.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            try:
                request.tenant = Tenant.objects.get(pk=tenant_id)
            except (Tenant.DoesNotExist, ValueError):
                request.tenant = None
        else:
            request.tenant = None
        return self.get_response(request)

from .models import Tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        api_key = request.headers.get("X-Tenant-Key") or request.GET.get("tenant_key")
        tenant = None
        if api_key:
            try:
                tenant = Tenant.objects.get(api_key=api_key, is_active=True)
            except Tenant.DoesNotExist:
                pass
        if not tenant:
            host = request.get_host().split(":")[0]
            try:
                tenant = Tenant.objects.get(domain=host, is_active=True)
            except Tenant.DoesNotExist:
                pass
        request.tenant = tenant
        return self.get_response(request)

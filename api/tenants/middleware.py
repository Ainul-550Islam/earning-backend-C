from django.http import JsonResponse
from .models import Tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        api_key = request.headers.get("X-API-Key") or request.GET.get("api_key")
        domain = request.get_host().split(":")[0]

        tenant = None

        if api_key:
            try:
                tenant = Tenant.objects.get(api_key=api_key, is_suspended=False)
            except Tenant.DoesNotExist:
                pass

        if not tenant:
            try:
                tenant = Tenant.objects.get(domain=domain, is_suspended=False)
            except Tenant.DoesNotExist:
                pass

        request.tenant = tenant
        response = self.get_response(request)
        return response

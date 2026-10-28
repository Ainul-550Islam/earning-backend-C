# api/support/middleware.py
import logging
logger = logging.getLogger(__name__)


class SupportTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/support/') and request.user.is_authenticated:
            if not hasattr(request, 'tenant'):
                request.tenant = getattr(request.user, 'tenant', None)
        return self.get_response(request)


class SupportMaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/support/') and not request.path.endswith('/settings/'):
            try:
                from django.core.cache import cache
                maintenance = cache.get('support:maintenance_mode')
                if maintenance is None:
                    from api.support.models import SupportSettings
                    obj, _ = SupportSettings.objects.get_or_create(id=1)
                    maintenance = obj.maintenance_mode
                    cache.set('support:maintenance_mode', maintenance, timeout=60)
                if maintenance and hasattr(request, 'user') and not request.user.is_staff:
                    from django.http import JsonResponse
                    return JsonResponse(
                        {'error': 'maintenance', 'message': 'Support in maintenance.'},
                        status=503
                    )
            except Exception:
                pass
        return self.get_response(request)
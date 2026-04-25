# earning_backend/api/notifications/endpoint.py
"""
Endpoint — Convenience endpoint registration and API meta view.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views import View
from django.utils import timezone


class NotificationAPIMetaView(View):
    """API meta-information endpoint — /api/notifications/meta/"""

    def get(self, request):
        from api.notifications.integration_system.health_check import health_checker
        from api.notifications.tasks_cap import list_tasks
        from api.notifications.plugins import plugin_registry

        return JsonResponse({
            'api': 'Notification System API',
            'version': '1.0.0',
            'timestamp': timezone.now().isoformat(),
            'channels': ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser', 'slack', 'discord'],
            'total_tasks': len(list_tasks()),
            'available_providers': list(plugin_registry.available().keys()),
            'health': health_checker.get_summary().get('overall', 'unknown'),
        })


@require_http_methods(['GET'])
def health_endpoint(request):
    """Quick health check endpoint for load balancers — /api/notifications/health/"""
    try:
        from api.notifications.integration_system.health_check import health_checker
        result = health_checker.check('database')
        status = 200 if result.status.value == 'healthy' else 503
        return JsonResponse({'status': result.status.value, 'timestamp': timezone.now().isoformat()}, status=status)
    except Exception as exc:
        return JsonResponse({'status': 'unhealthy', 'error': str(exc)}, status=503)


@require_http_methods(['GET'])
def version_endpoint(request):
    """API version endpoint."""
    return JsonResponse({'version': '1.0.0', 'module': 'notifications'})

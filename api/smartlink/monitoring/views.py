from django.http import JsonResponse
from django.views import View
from .HealthCheckService import HealthCheckService


class HealthCheckView(View):
    """GET /health/ — System health check endpoint."""

    def get(self, request):
        svc = HealthCheckService()

        # Quick check (no DB queries) for load balancer pings
        if request.GET.get('mode') == 'quick':
            from django.core.cache import cache
            try:
                cache.get('health:ping')
                return JsonResponse({'status': 'ok'})
            except Exception:
                return JsonResponse({'status': 'error'}, status=503)

        result = svc.full_health_check()
        status_code = 200 if result['status'] == 'healthy' else 503
        return JsonResponse(result, status=status_code)


class ReadinessView(View):
    """GET /ready/ — Kubernetes readiness probe."""

    def get(self, request):
        from django.db import connections
        try:
            connections['default'].ensure_connection()
            return JsonResponse({'ready': True})
        except Exception as e:
            return JsonResponse({'ready': False, 'error': str(e)}, status=503)


class LivenessView(View):
    """GET /live/ — Kubernetes liveness probe (fast, no DB)."""

    def get(self, request):
        return JsonResponse({'alive': True})

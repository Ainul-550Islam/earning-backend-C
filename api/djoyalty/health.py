# api/djoyalty/health.py
"""
Health check endpoints for Djoyalty।
Load balancer, Kubernetes liveness/readiness probes এর জন্য।
urls.py এ যোগ করুন:
    path('health/', include('api.djoyalty.health_urls')),
"""
import time
import logging
from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.core.cache import cache

logger = logging.getLogger('djoyalty.health')


class HealthCheckView(View):
    """
    GET /api/djoyalty/health/
    Full system health check।
    """
    def get(self, request):
        checks = {}
        overall_status = 'healthy'
        start = time.monotonic()

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks['database'] = {'status': 'healthy', 'latency_ms': round((time.monotonic() - start) * 1000, 1)}
        except Exception as e:
            checks['database'] = {'status': 'unhealthy', 'error': str(e)}
            overall_status = 'unhealthy'

        # Cache check
        try:
            cache_start = time.monotonic()
            cache.set('djoyalty_health_check', '1', 10)
            val = cache.get('djoyalty_health_check')
            if val != '1':
                raise ValueError('Cache read/write mismatch')
            checks['cache'] = {'status': 'healthy', 'latency_ms': round((time.monotonic() - cache_start) * 1000, 1)}
        except Exception as e:
            checks['cache'] = {'status': 'degraded', 'error': str(e)}
            # Cache degraded is not critical — use warning not error

        # Djoyalty model check
        try:
            from .models.core import Customer
            Customer.objects.exists()
            checks['models'] = {'status': 'healthy'}
        except Exception as e:
            checks['models'] = {'status': 'unhealthy', 'error': str(e)}
            overall_status = 'unhealthy'

        # Celery check (optional — don't fail if Celery not running)
        try:
            from celery.app.control import Control
            checks['celery'] = {'status': 'not_checked'}
        except ImportError:
            checks['celery'] = {'status': 'not_installed'}

        http_status = 200 if overall_status == 'healthy' else 503
        total_ms = round((time.monotonic() - start) * 1000, 1)

        return JsonResponse({
            'status': overall_status,
            'service': 'djoyalty',
            'version': '1.0.0',
            'total_latency_ms': total_ms,
            'checks': checks,
        }, status=http_status)


class LivenessCheckView(View):
    """
    GET /api/djoyalty/health/live/
    Kubernetes liveness probe — just check if process is alive।
    """
    def get(self, request):
        return JsonResponse({'status': 'alive', 'service': 'djoyalty'})


class ReadinessCheckView(View):
    """
    GET /api/djoyalty/health/ready/
    Kubernetes readiness probe — check if ready to serve traffic।
    """
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return JsonResponse({'status': 'ready', 'service': 'djoyalty'})
        except Exception as e:
            logger.error('Readiness check failed: %s', e)
            return JsonResponse({'status': 'not_ready', 'error': str(e)}, status=503)


class PingView(View):
    """GET /api/djoyalty/ping/ — simple ping/pong।"""
    def get(self, request):
        return JsonResponse({'pong': True})

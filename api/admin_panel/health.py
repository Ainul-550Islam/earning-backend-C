# api/admin_panel/health.py
"""Health check endpoint for Railway/Docker load balancer."""
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
import time


class HealthCheckView(View):
    """GET /health/ — returns 200 if healthy, 503 if degraded."""

    def get(self, request):
        checks = {}
        overall = 'healthy'

        # DB
        t = time.monotonic()
        try:
            with connection.cursor() as c:
                c.execute('SELECT 1')
            checks['database'] = {'status': 'ok', 'ms': round((time.monotonic()-t)*1000)}
        except Exception as e:
            checks['database'] = {'status': 'error', 'error': str(e)[:80]}
            overall = 'degraded'

        # Cache
        t = time.monotonic()
        try:
            cache.set('health_probe', 'ok', 5)
            assert cache.get('health_probe') == 'ok'
            checks['cache'] = {'status': 'ok', 'ms': round((time.monotonic()-t)*1000)}
        except Exception as e:
            checks['cache'] = {'status': 'error', 'error': str(e)[:80]}
            overall = 'degraded'

        # Celery (non-blocking)
        try:
            from celery import current_app
            i = current_app.control.inspect(timeout=1)
            workers = i.active()
            checks['celery'] = {'status': 'ok' if workers else 'no_workers',
                                 'workers': len(workers or {})}
        except Exception:
            checks['celery'] = {'status': 'unknown'}

        status_code = 200 if overall == 'healthy' else 503
        return JsonResponse({
            'status': overall,
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'checks': checks,
        }, status=status_code)


class ReadinessView(View):
    """GET /ready/ — returns 200 when app is ready to serve traffic."""

    def get(self, request):
        try:
            with connection.cursor() as c:
                c.execute('SELECT 1')
            return JsonResponse({'status': 'ready', 'timestamp': timezone.now().isoformat()})
        except Exception as e:
            return JsonResponse({'status': 'not_ready', 'error': str(e)[:80]}, status=503)


class LivenessView(View):
    """GET /alive/ — returns 200 if process is alive (no DB check)."""

    def get(self, request):
        return JsonResponse({'status': 'alive', 'timestamp': timezone.now().isoformat()})
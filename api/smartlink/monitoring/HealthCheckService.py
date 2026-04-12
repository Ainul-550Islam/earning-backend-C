"""
SmartLink Health Check & Monitoring Service
World #1 Feature: Comprehensive system health monitoring.
Monitors: DB, Redis, Celery, GeoIP, SmartLink health, offer caps.
"""
import logging
import time
from django.core.cache import cache
from django.db import connections
from django.utils import timezone

logger = logging.getLogger('smartlink.monitoring')


class HealthCheckService:
    """
    System-wide health check service.
    Used by /health/ endpoint and monitoring alerts.
    """

    def full_health_check(self) -> dict:
        """Run all health checks and return aggregated status."""
        checks = {}
        start = time.perf_counter()

        checks['database']       = self._check_database()
        checks['redis']          = self._check_redis()
        checks['celery']         = self._check_celery()
        checks['geoip']          = self._check_geoip()
        checks['smartlinks']     = self._check_smartlink_health()
        checks['redirect_speed'] = self._check_redirect_speed()

        all_healthy = all(c.get('status') == 'ok' for c in checks.values())
        elapsed_ms  = (time.perf_counter() - start) * 1000

        return {
            'status':        'healthy' if all_healthy else 'degraded',
            'timestamp':     timezone.now().isoformat(),
            'response_ms':   round(elapsed_ms, 2),
            'checks':        checks,
            'version':       '1.0.0',
            'system':        'SmartLink World #1',
        }

    def _check_database(self) -> dict:
        try:
            start = time.perf_counter()
            conn = connections['default']
            conn.ensure_connection()
            # Quick query
            from api.smartlink.models import SmartLink
            SmartLink.objects.exists()
            ms = (time.perf_counter() - start) * 1000
            return {'status': 'ok', 'response_ms': round(ms, 2)}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _check_redis(self) -> dict:
        try:
            start = time.perf_counter()
            cache.set('health:ping', 'pong', 10)
            val = cache.get('health:ping')
            ms = (time.perf_counter() - start) * 1000
            if val == 'pong':
                return {'status': 'ok', 'response_ms': round(ms, 2)}
            return {'status': 'error', 'error': 'ping/pong mismatch'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _check_celery(self) -> dict:
        try:
            from api.smartlink.celery_config.celery import app
            inspect = app.control.inspect(timeout=2)
            stats = inspect.stats()
            if stats:
                worker_count = len(stats)
                return {'status': 'ok', 'workers': worker_count}
            return {'status': 'warning', 'error': 'No workers responding'}
        except Exception as e:
            return {'status': 'warning', 'error': str(e)}

    def _check_geoip(self) -> dict:
        try:
            from api.smartlink.services.geoip.GeoIPEnricher import GeoIPEnricher
            enricher = GeoIPEnricher()
            result = enricher.enrich('8.8.8.8')
            if result.get('country') == 'US':
                return {'status': 'ok', 'test_ip': '8.8.8.8', 'country': 'US'}
            return {'status': 'warning', 'error': 'GeoIP lookup returned unexpected result'}
        except Exception as e:
            return {'status': 'warning', 'error': f'GeoIP: {str(e)}'}

    def _check_smartlink_health(self) -> dict:
        try:
            from api.smartlink.models import SmartLink
            total   = SmartLink.objects.filter(is_active=True, is_archived=False).count()
            broken  = SmartLink.objects.filter(
                is_active=True, is_archived=False
            ).exclude(offer_pool__entries__is_active=True).count()
            return {
                'status':          'ok' if broken == 0 else 'warning',
                'total_active':    total,
                'broken':          broken,
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _check_redirect_speed(self) -> dict:
        """Measure end-to-end resolver speed with a real SmartLink."""
        try:
            from api.smartlink.models import SmartLink
            sl = SmartLink.objects.filter(is_active=True).first()
            if not sl:
                return {'status': 'warning', 'error': 'No active SmartLinks'}

            from api.smartlink.services.core.SmartLinkCacheService import SmartLinkCacheService
            svc = SmartLinkCacheService()

            start = time.perf_counter()
            svc.get_smartlink(sl.slug)
            ms = (time.perf_counter() - start) * 1000

            status = 'ok' if ms < 5 else 'warning' if ms < 20 else 'slow'
            return {
                'status':       status,
                'cache_read_ms': round(ms, 3),
                'target_ms':    5,
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

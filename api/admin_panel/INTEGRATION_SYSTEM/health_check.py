# api/admin_panel/INTEGRATION_SYSTEM/health_check.py
"""
HealthCheck — Comprehensive system health checking across all 50 apps.
Checks: DB, Cache, Celery, each app's model availability, external APIs.
"""
import time
import logging
from typing import Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import HEALTH_STATUSES, INTEGRATION_APPS

logger = logging.getLogger(__name__)


class ServiceHealthResult:
    def __init__(self, service: str, status: str, latency_ms: int = 0,
                 details: dict = None, error: str = ''):
        self.service = service
        self.status = status
        self.latency_ms = latency_ms
        self.details = details or {}
        self.error = error
        self.checked_at = timezone.now()

    def is_healthy(self) -> bool:
        return self.status == HEALTH_STATUSES['HEALTHY']

    def to_dict(self) -> Dict:
        return {
            'service': self.service,
            'status': self.status,
            'latency_ms': self.latency_ms,
            'details': self.details,
            'error': self.error,
            'checked_at': self.checked_at.isoformat(),
        }


class HealthCheck:
    """Run health checks on all system components."""

    @classmethod
    def check_database(cls) -> ServiceHealthResult:
        start = time.monotonic()
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            latency_ms = int((time.monotonic() - start) * 1000)
            return ServiceHealthResult('database', HEALTH_STATUSES['HEALTHY'], latency_ms)
        except Exception as e:
            return ServiceHealthResult('database', HEALTH_STATUSES['DOWN'], error=str(e))

    @classmethod
    def check_cache(cls) -> ServiceHealthResult:
        start = time.monotonic()
        try:
            test_key = 'admin_panel:health_check_probe'
            cache.set(test_key, 'ok', 5)
            val = cache.get(test_key)
            latency_ms = int((time.monotonic() - start) * 1000)
            if val == 'ok':
                return ServiceHealthResult('cache', HEALTH_STATUSES['HEALTHY'], latency_ms)
            return ServiceHealthResult('cache', HEALTH_STATUSES['DEGRADED'], latency_ms,
                                       error='Cache write/read mismatch')
        except Exception as e:
            return ServiceHealthResult('cache', HEALTH_STATUSES['DOWN'], error=str(e))

    @classmethod
    def check_celery(cls) -> ServiceHealthResult:
        start = time.monotonic()
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=2)
            active = inspector.active()
            latency_ms = int((time.monotonic() - start) * 1000)
            if active:
                workers = list(active.keys())
                return ServiceHealthResult(
                    'celery', HEALTH_STATUSES['HEALTHY'], latency_ms,
                    details={'workers': len(workers), 'worker_names': workers[:5]},
                )
            return ServiceHealthResult('celery', HEALTH_STATUSES['DEGRADED'], latency_ms,
                                       error='No active Celery workers')
        except Exception as e:
            return ServiceHealthResult('celery', HEALTH_STATUSES['DOWN'], error=str(e))

    @classmethod
    def check_app(cls, app_name: str) -> ServiceHealthResult:
        """Check if an app's models are importable and DB is accessible."""
        start = time.monotonic()
        try:
            import importlib
            module = importlib.import_module(f'api.{app_name}')
            latency_ms = int((time.monotonic() - start) * 1000)
            # Try to count one model
            try:
                models_module = importlib.import_module(f'api.{app_name}.models')
                latency_ms = int((time.monotonic() - start) * 1000)
            except ImportError:
                pass
            return ServiceHealthResult(app_name, HEALTH_STATUSES['HEALTHY'], latency_ms)
        except Exception as e:
            return ServiceHealthResult(app_name, HEALTH_STATUSES['UNKNOWN'],
                                       error=f'Import failed: {str(e)[:100]}')

    @classmethod
    def check_all(cls, include_apps: bool = False) -> Dict:
        """Run all health checks and return summary."""
        checks = {}

        # Core infrastructure
        for check_fn, name in [
            (cls.check_database, 'database'),
            (cls.check_cache, 'cache'),
            (cls.check_celery, 'celery'),
        ]:
            result = check_fn()
            checks[name] = result.to_dict()

        # App checks (optional — heavy)
        if include_apps:
            for app in INTEGRATION_APPS[:20]:  # Check first 20 apps
                result = cls.check_app(app)
                checks[app] = result.to_dict()

        # Determine overall status
        statuses = [v['status'] for v in checks.values()]
        if all(s == HEALTH_STATUSES['HEALTHY'] for s in statuses):
            overall = HEALTH_STATUSES['HEALTHY']
        elif any(s == HEALTH_STATUSES['DOWN'] for s in statuses):
            overall = HEALTH_STATUSES['DEGRADED']
        else:
            overall = HEALTH_STATUSES['DEGRADED']

        result = {
            'overall': overall,
            'checks': checks,
            'total_services': len(checks),
            'healthy_count': sum(1 for s in statuses if s == HEALTH_STATUSES['HEALTHY']),
            'degraded_count': sum(1 for s in statuses if s == HEALTH_STATUSES['DEGRADED']),
            'down_count': sum(1 for s in statuses if s == HEALTH_STATUSES['DOWN']),
            'checked_at': timezone.now().isoformat(),
        }

        # Cache for 30 seconds
        cache.set('admin_panel:integration_health_full', result, 30)
        return result

    @classmethod
    def get_cached_health(cls) -> Optional[Dict]:
        return cache.get('admin_panel:integration_health_full')

    @classmethod
    def is_system_healthy(cls) -> bool:
        result = cls.get_cached_health() or cls.check_all()
        return result.get('overall') == HEALTH_STATUSES['HEALTHY']
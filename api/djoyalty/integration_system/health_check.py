# api/djoyalty/integration_system/health_check.py
"""
Health Check Service -- Integration + System health monitoring।
Monitors: DB, Redis, Celery, all integrations, queues।
World: Production health endpoints (AWS, Kubernetes ready)।
"""
import logging
import time
from typing import Dict, Any
from django.utils import timezone
from .integ_constants import (
    IntegrationStatus, HEALTH_CHECK_INTERVAL, HEALTH_CHECK_TIMEOUT,
    CACHE_KEY_HEALTH_CHECK,
)

logger = logging.getLogger(__name__)


class HealthCheckResult:
    def __init__(self, name: str, healthy: bool, latency_ms: float = 0,
                  message: str = '', details: dict = None):
        self.name = name
        self.healthy = healthy
        self.latency_ms = latency_ms
        self.message = message
        self.details = details or {}
        self.checked_at = timezone.now().isoformat()

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'status': 'healthy' if self.healthy else 'unhealthy',
            'latency_ms': round(self.latency_ms, 2),
            'message': self.message,
            'details': self.details,
            'checked_at': self.checked_at,
        }


class HealthCheckService:
    """
    Comprehensive health check service।

    Usage:
        # Quick check
        result = HealthCheckService.check_all()

        # Individual checks
        db_ok = HealthCheckService.check_database()
        redis_ok = HealthCheckService.check_redis()
    """

    @classmethod
    def check_all(cls, use_cache: bool = True) -> dict:
        """Run all health checks and return combined result।"""
        if use_cache:
            cached = cls._get_cached_result()
            if cached:
                return cached

        start = time.monotonic()

        checks = {
            'database':    cls.check_database(),
            'redis':       cls.check_redis(),
            'celery':      cls.check_celery(),
            'integrations': cls.check_all_integrations(),
            'loyalty_data': cls.check_loyalty_data(),
        }

        total_ms = (time.monotonic() - start) * 1000
        all_healthy = all(
            r.healthy if isinstance(r, HealthCheckResult) else
            all(v.healthy for v in r.values() if isinstance(v, HealthCheckResult))
            for r in checks.values()
        )

        result = {
            'status': 'healthy' if all_healthy else 'degraded',
            'timestamp': timezone.now().isoformat(),
            'total_latency_ms': round(total_ms, 2),
            'checks': {
                name: (
                    check.to_dict() if isinstance(check, HealthCheckResult) else
                    {k: v.to_dict() for k, v in check.items()}
                )
                for name, check in checks.items()
            },
        }

        cls._cache_result(result)
        return result

    @classmethod
    def check_database(cls) -> HealthCheckResult:
        """Check Django database connection।"""
        start = time.monotonic()
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            latency = (time.monotonic() - start) * 1000
            return HealthCheckResult('database', True, latency_ms=latency)
        except Exception as e:
            return HealthCheckResult('database', False,
                                      message=str(e),
                                      latency_ms=(time.monotonic() - start) * 1000)

    @classmethod
    def check_redis(cls) -> HealthCheckResult:
        """Check Redis cache connection।"""
        start = time.monotonic()
        try:
            from django.core.cache import cache
            test_key = 'djoyalty:health:ping'
            cache.set(test_key, 'pong', timeout=10)
            result = cache.get(test_key)
            latency = (time.monotonic() - start) * 1000
            if result == 'pong':
                return HealthCheckResult('redis', True, latency_ms=latency)
            return HealthCheckResult('redis', False, message='Cache read/write failed')
        except Exception as e:
            return HealthCheckResult('redis', False, message=str(e),
                                      latency_ms=(time.monotonic() - start) * 1000)

    @classmethod
    def check_celery(cls) -> HealthCheckResult:
        """Check Celery worker availability।"""
        start = time.monotonic()
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=2.0)
            active = inspect.active()
            latency = (time.monotonic() - start) * 1000
            if active:
                worker_count = len(active)
                return HealthCheckResult(
                    'celery', True, latency_ms=latency,
                    details={'worker_count': worker_count},
                )
            return HealthCheckResult('celery', False, message='No active workers',
                                      latency_ms=latency)
        except Exception as e:
            return HealthCheckResult('celery', False, message=str(e),
                                      latency_ms=(time.monotonic() - start) * 1000)

    @classmethod
    def check_all_integrations(cls) -> Dict[str, HealthCheckResult]:
        """Check all integration health (ping test)।"""
        results = {}
        integrations_to_check = [
            ('bkash',       cls._check_bkash),
            ('nagad',       cls._check_nagad),
            ('sslcommerz',  cls._check_sslcommerz),
            ('sms',         cls._check_sms),
            ('push',        cls._check_push),
            ('email',       cls._check_email),
            ('ocr',         cls._check_ocr),
        ]
        for name, check_fn in integrations_to_check:
            try:
                results[name] = check_fn()
            except Exception as e:
                results[name] = HealthCheckResult(name, False, message=str(e))
        return results

    @classmethod
    def _check_bkash(cls) -> HealthCheckResult:
        from ..integrations.bkash import BkashIntegration
        if not BkashIntegration.is_configured():
            return HealthCheckResult('bkash', True, message='Not configured (optional)')
        start = time.monotonic()
        try:
            bkash = BkashIntegration()
            token = bkash.get_token()
            latency = (time.monotonic() - start) * 1000
            return HealthCheckResult('bkash', bool(token), latency_ms=latency)
        except Exception as e:
            return HealthCheckResult('bkash', False, message=str(e))

    @classmethod
    def _check_nagad(cls) -> HealthCheckResult:
        from ..integrations.nagad import NagadIntegration
        if not NagadIntegration.is_configured():
            return HealthCheckResult('nagad', True, message='Not configured (optional)')
        return HealthCheckResult('nagad', True, message='Configured (ping not available)')

    @classmethod
    def _check_sslcommerz(cls) -> HealthCheckResult:
        from ..integrations.sslcommerz import SSLCommerzIntegration
        configured = SSLCommerzIntegration.is_configured()
        return HealthCheckResult(
            'sslcommerz',
            True,
            message='Configured' if configured else 'Not configured (optional)',
        )

    @classmethod
    def _check_sms(cls) -> HealthCheckResult:
        from ..integrations.sms import BulkSMSBD
        configured = BulkSMSBD.is_configured()
        return HealthCheckResult(
            'sms',
            True,
            message='BulkSMSBD configured' if configured else 'SMS not configured (optional)',
        )

    @classmethod
    def _check_push(cls) -> HealthCheckResult:
        from ..integrations.push_notification import FCMPushService
        configured = FCMPushService.is_configured()
        return HealthCheckResult(
            'push',
            True,
            message='FCM configured' if configured else 'Push not configured (optional)',
        )

    @classmethod
    def _check_email(cls) -> HealthCheckResult:
        from django.conf import settings
        configured = bool(getattr(settings, 'EMAIL_HOST', None) or
                         getattr(settings, 'DJOYALTY_SENDGRID_API_KEY', None))
        return HealthCheckResult(
            'email',
            True,
            message='Email configured' if configured else 'Email not configured',
        )

    @classmethod
    def _check_ocr(cls) -> HealthCheckResult:
        from ..integrations.ocr import GoogleVisionOCR
        configured = GoogleVisionOCR.is_configured()
        return HealthCheckResult(
            'ocr',
            True,
            message='OCR configured' if configured else 'OCR not configured (optional)',
        )

    @classmethod
    def check_loyalty_data(cls) -> HealthCheckResult:
        """Quick loyalty data sanity check।"""
        start = time.monotonic()
        try:
            from ..models.core import Customer
            count = Customer.objects.count()
            latency = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                'loyalty_data', True, latency_ms=latency,
                details={'customer_count': count},
            )
        except Exception as e:
            return HealthCheckResult('loyalty_data', False, message=str(e))

    @classmethod
    def _cache_result(cls, result: dict):
        try:
            from django.core.cache import cache
            cache.set('djoyalty:health:all', result, timeout=HEALTH_CHECK_INTERVAL)
        except Exception:
            pass

    @classmethod
    def _get_cached_result(cls) -> dict:
        try:
            from django.core.cache import cache
            return cache.get('djoyalty:health:all')
        except Exception:
            return None

    @classmethod
    def get_simple_status(cls) -> dict:
        """Simple up/down status for load balancer checks।"""
        try:
            db = cls.check_database()
            return {
                'status': 'ok' if db.healthy else 'error',
                'database': 'ok' if db.healthy else 'error',
            }
        except Exception:
            return {'status': 'error'}

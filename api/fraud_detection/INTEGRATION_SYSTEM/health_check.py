# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/health_check.py
# =============================================================================
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger('fraud_detection.health')


class HealthStatus(Enum):
    HEALTHY   = 'healthy'
    DEGRADED  = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN   = 'unknown'


@dataclass
class HealthCheckResult:
    name        : str
    status      : HealthStatus
    message     : str = ''
    latency_ms  : float = 0.0
    details     : dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'name':       self.name,
            'status':     self.status.value,
            'message':    self.message,
            'latency_ms': round(self.latency_ms, 2),
            'details':    self.details,
        }


# ---------------------------------------------------------------------------
# Built-in checks
# ---------------------------------------------------------------------------

def _check_database() -> HealthCheckResult:
    t0 = time.monotonic()
    try:
        from django.db import connection
        connection.ensure_connection()
        latency = (time.monotonic() - t0) * 1000
        return HealthCheckResult(
            name='database', status=HealthStatus.HEALTHY,
            message='DB connection OK', latency_ms=latency,
        )
    except Exception as exc:
        return HealthCheckResult(
            name='database', status=HealthStatus.UNHEALTHY,
            message=str(exc), latency_ms=(time.monotonic() - t0) * 1000,
        )


def _check_cache() -> HealthCheckResult:
    t0 = time.monotonic()
    try:
        from django.core.cache import cache
        probe = 'fraud_health_probe'
        cache.set(probe, 'ok', 5)
        val  = cache.get(probe)
        latency = (time.monotonic() - t0) * 1000
        if val == 'ok':
            return HealthCheckResult(
                name='cache', status=HealthStatus.HEALTHY,
                message='Cache read/write OK', latency_ms=latency,
            )
        return HealthCheckResult(
            name='cache', status=HealthStatus.DEGRADED,
            message='Cache returned unexpected value', latency_ms=latency,
        )
    except Exception as exc:
        return HealthCheckResult(
            name='cache', status=HealthStatus.UNHEALTHY,
            message=str(exc), latency_ms=(time.monotonic() - t0) * 1000,
        )


def _check_celery() -> HealthCheckResult:
    t0 = time.monotonic()
    try:
        from celery import current_app
        i = current_app.control.inspect(timeout=2)
        stats = i.stats()
        latency = (time.monotonic() - t0) * 1000
        if stats:
            return HealthCheckResult(
                name='celery', status=HealthStatus.HEALTHY,
                message=f'{len(stats)} worker(s) online', latency_ms=latency,
            )
        return HealthCheckResult(
            name='celery', status=HealthStatus.DEGRADED,
            message='No Celery workers responding', latency_ms=latency,
        )
    except Exception as exc:
        return HealthCheckResult(
            name='celery', status=HealthStatus.UNKNOWN,
            message=f'Celery check skipped: {exc}',
            latency_ms=(time.monotonic() - t0) * 1000,
        )


def _check_detectors() -> HealthCheckResult:
    t0 = time.monotonic()
    errors = []
    import importlib
    for name in ('VelocityEngine', 'DeviceFingerprinter', 'VPNProxyDetector'):
        try:
            importlib.import_module(f'api.fraud_detection.detectors.{name}')
        except ImportError as exc:
            errors.append(f'{name}: {exc}')
    latency = (time.monotonic() - t0) * 1000
    if not errors:
        return HealthCheckResult(name='detectors', status=HealthStatus.HEALTHY,
                                 message='All core detectors importable', latency_ms=latency)
    return HealthCheckResult(name='detectors', status=HealthStatus.DEGRADED,
                             message='; '.join(errors), latency_ms=latency)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_BUILTIN_CHECKS: List[Callable[[], HealthCheckResult]] = [
    _check_database,
    _check_cache,
    _check_celery,
    _check_detectors,
]


def run_health_checks(
    extra_checks: Optional[List[Callable[[], HealthCheckResult]]] = None,
) -> Dict[str, object]:
    checks  = _BUILTIN_CHECKS + (extra_checks or [])
    results = []
    for check in checks:
        try:
            results.append(check().to_dict())
        except Exception as exc:
            results.append({'name': getattr(check, '__name__', '?'),
                            'status': 'unknown', 'message': str(exc)})

    statuses = {r['status'] for r in results}
    if 'unhealthy' in statuses:
        overall = 'unhealthy'
    elif 'degraded' in statuses:
        overall = 'degraded'
    else:
        overall = 'healthy'

    return {'overall': overall, 'checks': results}


def get_system_health_status() -> str:
    return run_health_checks()['overall']


def get_health_statistics() -> dict:
    result = run_health_checks()
    checks = result['checks']
    return {
        'overall':  result['overall'],
        'total':    len(checks),
        'healthy':  sum(1 for c in checks if c['status'] == 'healthy'),
        'degraded': sum(1 for c in checks if c['status'] == 'degraded'),
        'unhealthy': sum(1 for c in checks if c['status'] == 'unhealthy'),
        'checks':   checks,
    }


def check_integration_health(integration_name: str) -> dict:
    """Quick single-integration probe."""
    return {
        'integration': integration_name,
        'status':      'unknown',
        'message':     f'No specific check registered for {integration_name!r}',
    }

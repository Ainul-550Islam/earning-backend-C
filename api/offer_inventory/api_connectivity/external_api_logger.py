# api/offer_inventory/api_connectivity/external_api_logger.py
"""
External API Logger.
Logs all outbound API calls for debugging, billing, and compliance.
Tracks latency, errors, and response patterns.
"""
import json
import time
import logging
import hashlib
from functools import wraps
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ExternalAPILog:
    """Structured log entry for an external API call."""

    def __init__(self, service: str, method: str, url: str):
        self.service    = service
        self.method     = method
        self.url        = url
        self.start_time = time.monotonic()
        self.request_id = hashlib.md5(
            f'{service}{url}{time.time()}'.encode()
        ).hexdigest()[:12]

    def record_success(self, status_code: int, response_size: int = 0):
        elapsed = (time.monotonic() - self.start_time) * 1000
        self._persist({
            'service'      : self.service,
            'method'       : self.method,
            'url'          : self.url[:500],
            'status_code'  : status_code,
            'elapsed_ms'   : round(elapsed, 2),
            'response_size': response_size,
            'success'      : True,
            'error'        : None,
            'timestamp'    : timezone.now().isoformat(),
            'request_id'   : self.request_id,
        })
        logger.debug(
            f'ExternalAPI OK | {self.service} {self.method} {self.url[:60]} '
            f'→ {status_code} ({elapsed:.0f}ms)'
        )

    def record_error(self, error: str, status_code: int = 0):
        elapsed = (time.monotonic() - self.start_time) * 1000
        self._persist({
            'service'    : self.service,
            'method'     : self.method,
            'url'        : self.url[:500],
            'status_code': status_code,
            'elapsed_ms' : round(elapsed, 2),
            'success'    : False,
            'error'      : error[:500],
            'timestamp'  : timezone.now().isoformat(),
            'request_id' : self.request_id,
        })
        logger.error(
            f'ExternalAPI FAIL | {self.service} {self.method} {self.url[:60]} '
            f'→ {status_code} ({elapsed:.0f}ms) {error[:100]}'
        )

    def _persist(self, data: dict):
        """Store log in Redis list (last 1000 entries) and optionally DB."""
        list_key = f'ext_api_logs:{self.service}'
        logs     = cache.get(list_key, [])
        logs.append(data)
        cache.set(list_key, logs[-1000:], 86400)  # 24h TTL


class APICallTracker:
    """Analytics for external API call patterns."""

    @staticmethod
    def get_service_stats(service: str, hours: int = 24) -> dict:
        """Get API call stats for a service."""
        logs  = cache.get(f'ext_api_logs:{service}', [])
        since = timezone.now() - __import__('datetime').timedelta(hours=hours)

        recent = [
            l for l in logs
            if l.get('timestamp', '') >= since.isoformat()
        ]

        if not recent:
            return {'service': service, 'calls': 0}

        success = [l for l in recent if l.get('success')]
        failed  = [l for l in recent if not l.get('success')]
        latencies = [l['elapsed_ms'] for l in recent if 'elapsed_ms' in l]

        return {
            'service'      : service,
            'total_calls'  : len(recent),
            'success_count': len(success),
            'error_count'  : len(failed),
            'success_rate' : round(len(success) / len(recent) * 100, 1),
            'avg_latency_ms': round(sum(latencies) / len(latencies), 1) if latencies else 0,
            'max_latency_ms': max(latencies) if latencies else 0,
            'error_codes'  : {
                str(l.get('status_code', 0)): sum(
                    1 for x in failed if x.get('status_code') == l.get('status_code')
                )
                for l in failed
            },
            'hours'        : hours,
        }

    @staticmethod
    def get_all_services_stats() -> list:
        """Stats for all tracked external services."""
        from api.offer_inventory.models import OfferNetwork
        services = list(
            OfferNetwork.objects.filter(status='active').values_list('slug', flat=True)
        ) + ['tapjoy', 'fyber', 'adgem', 'offertoro', 'generic']

        return [
            APICallTracker.get_service_stats(s)
            for s in set(services)
        ]


def log_external_api_call(service: str):
    """
    Decorator to automatically log external API calls.

    Usage:
        @log_external_api_call('tapjoy')
        def fetch_tapjoy_offers(url, params):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            url   = kwargs.get('url', args[0] if args else 'unknown')
            entry = ExternalAPILog(service, 'CALL', str(url))
            try:
                result = func(*args, **kwargs)
                entry.record_success(200)
                return result
            except Exception as e:
                entry.record_error(str(e))
                raise
        return wrapper
    return decorator

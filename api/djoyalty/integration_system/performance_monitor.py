# api/djoyalty/integration_system/performance_monitor.py
"""
Performance Monitor -- Response time & metrics tracking।
Tracks integration call latencies, error rates, throughput।
"""
import logging
import time
import threading
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Dict, List, Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

_metrics_lock = threading.Lock()


class PerformanceMetric:
    """Single performance metric record।"""
    def __init__(self, integration: str, operation: str,
                  duration_ms: float, success: bool,
                  error: str = ''):
        self.integration = integration
        self.operation = operation
        self.duration_ms = duration_ms
        self.success = success
        self.error = error
        self.timestamp = time.time()


class PerformanceMonitor:
    """
    Tracks integration performance metrics।
    Records: latency, error rate, throughput per integration।
    Stores in Redis (ring buffer -- last 1000 per integration)।

    Usage:
        with PerformanceMonitor.track('bkash', 'create_payment') as t:
            result = bkash.create_payment(...)
    """

    _local_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    _thresholds = {
        'fast':   100,    # ms
        'normal': 500,    # ms
        'slow':   2000,   # ms -- alert if exceeded
    }

    @classmethod
    @contextmanager
    def track(cls, integration: str, operation: str):
        """Context manager for performance tracking।"""
        start = time.monotonic()
        success = True
        error = ''
        try:
            yield
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            cls._record(integration, operation, duration_ms, success, error)

    @classmethod
    def _record(cls, integration: str, operation: str,
                 duration_ms: float, success: bool, error: str = ''):
        """Record metric (in-memory + Redis)।"""
        metric = PerformanceMetric(integration, operation, duration_ms, success, error)

        with _metrics_lock:
            cls._local_buffer[f'{integration}:{operation}'].append(metric)

        # Alert on slow calls
        if duration_ms > cls._thresholds['slow']:
            logger.warning(
                'PerformanceMonitor: SLOW call %s.%s %.1fms',
                integration, operation, duration_ms,
            )

        # Store in Redis for persistence
        try:
            cache_key = f'djoyalty:perf:{integration}:{operation}'
            existing = cache.get(cache_key) or {'count': 0, 'total_ms': 0, 'errors': 0}
            existing['count'] += 1
            existing['total_ms'] += duration_ms
            if not success:
                existing['errors'] += 1
            existing['last_ms'] = duration_ms
            cache.set(cache_key, existing, timeout=3600)
        except Exception:
            pass

        if success:
            logger.debug('Perf %s.%s: %.1fms ✓', integration, operation, duration_ms)
        else:
            logger.debug('Perf %s.%s: %.1fms ✗ %s', integration, operation, duration_ms, error)

    @classmethod
    def get_stats(cls, integration: str = '') -> dict:
        """Get performance statistics।"""
        result = {}
        try:
            from django.core.cache import cache
            # Get all keys from local buffer
            for key in list(cls._local_buffer.keys()):
                if integration and not key.startswith(integration):
                    continue
                metrics = list(cls._local_buffer[key])
                if not metrics:
                    continue
                durations = [m.duration_ms for m in metrics]
                errors = sum(1 for m in metrics if not m.success)
                result[key] = {
                    'count': len(metrics),
                    'avg_ms': sum(durations) / len(durations),
                    'min_ms': min(durations),
                    'max_ms': max(durations),
                    'error_rate': f'{errors / len(metrics) * 100:.1f}%',
                    'last_ms': durations[-1] if durations else 0,
                }
        except Exception as e:
            logger.debug('PerformanceMonitor.get_stats error: %s', e)
        return result

    @classmethod
    def get_overall_health(cls) -> str:
        """
        Get overall integration health: 'good' | 'degraded' | 'poor'।
        """
        stats = cls.get_stats()
        if not stats:
            return 'unknown'
        total_errors = 0
        total_calls = 0
        slow_count = 0
        for key, data in stats.items():
            count = data['count']
            total_calls += count
            error_rate = float(data['error_rate'].replace('%', ''))
            total_errors += count * error_rate / 100
            if data['avg_ms'] > cls._thresholds['slow']:
                slow_count += 1
        if total_calls == 0:
            return 'unknown'
        overall_error_rate = total_errors / total_calls * 100
        if overall_error_rate > 20 or slow_count > 3:
            return 'poor'
        elif overall_error_rate > 5 or slow_count > 1:
            return 'degraded'
        return 'good'

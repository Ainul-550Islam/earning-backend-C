# api/support/integrations/performance_monitor.py  — WORLD #1
"""
Performance Monitor — Integration call performance tracking।
Slow calls → alert, metrics → dashboard।
"""
import logging
import time
import functools
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from .integ_constants import PERF_RESPONSE_WARN_MS, PERF_RESPONSE_CRITICAL_MS

logger = logging.getLogger(__name__)


class IntegrationPerformanceMonitor:
    """Track performance of all integration calls."""

    def __init__(self):
        self._lock    = Lock()
        self._metrics = defaultdict(lambda: {
            'calls':     0,
            'total_ms':  0.0,
            'min_ms':    float('inf'),
            'max_ms':    0.0,
            'errors':    0,
            'slow':      0,
            'critical':  0,
        })
        self._recent  = deque(maxlen=500)  # Last 500 calls

    def track(self, adapter: str, method: str):
        """Decorator to track integration call performance."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self._tracked_call(adapter, method, func, *args, **kwargs)
            return wrapper
        return decorator

    def _tracked_call(self, adapter: str, method: str, func: Callable, *args, **kwargs):
        """Execute and track a call."""
        key   = f'{adapter}.{method}'
        start = time.perf_counter()
        error = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = e
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._record(key, elapsed_ms, error)

    def _record(self, key: str, elapsed_ms: float, error: Exception = None):
        """Record call metrics."""
        with self._lock:
            m = self._metrics[key]
            m['calls']    += 1
            m['total_ms'] += elapsed_ms
            m['min_ms']    = min(m['min_ms'], elapsed_ms)
            m['max_ms']    = max(m['max_ms'], elapsed_ms)
            if error:
                m['errors'] += 1
            if elapsed_ms > PERF_RESPONSE_CRITICAL_MS:
                m['critical'] += 1
                logger.error(f'CRITICAL slow integration [{key}]: {elapsed_ms:.0f}ms')
            elif elapsed_ms > PERF_RESPONSE_WARN_MS:
                m['slow'] += 1
                logger.warning(f'Slow integration [{key}]: {elapsed_ms:.0f}ms')
            self._recent.append({'key': key, 'ms': round(elapsed_ms,1), 'error': bool(error)})

    def record(self, key: str, elapsed_ms: float, error: bool = False):
        """Manual record (for non-decorator use)."""
        self._record(key, elapsed_ms, Exception() if error else None)

    def get_summary(self) -> dict:
        """Full metrics summary for admin dashboard."""
        with self._lock:
            summary = {}
            for key, m in self._metrics.items():
                calls = m['calls']
                summary[key] = {
                    'calls':        calls,
                    'avg_ms':       round(m['total_ms']/calls, 1) if calls else 0,
                    'min_ms':       round(m['min_ms'], 1) if m['min_ms'] != float('inf') else 0,
                    'max_ms':       round(m['max_ms'], 1),
                    'error_rate':   round(m['errors']/calls*100, 1) if calls else 0,
                    'slow_count':   m['slow'],
                    'critical_count':m['critical'],
                }
            return summary

    def get_recent(self, limit: int = 50) -> list:
        """Get recent call log."""
        return list(self._recent)[-limit:]

    def get_alerts(self) -> list:
        """Get integration methods with high error rates or slow calls."""
        alerts = []
        with self._lock:
            for key, m in self._metrics.items():
                calls = m['calls']
                if calls < 5:
                    continue
                if m['errors']/calls > 0.1:
                    alerts.append({'key':key,'type':'high_error_rate','rate':round(m['errors']/calls*100,1)})
                if m['critical'] > 0:
                    alerts.append({'key':key,'type':'critical_slow','count':m['critical']})
        return alerts

    def reset(self):
        """Reset all metrics — for testing."""
        with self._lock:
            self._metrics.clear()
            self._recent.clear()


perf_monitor = IntegrationPerformanceMonitor()
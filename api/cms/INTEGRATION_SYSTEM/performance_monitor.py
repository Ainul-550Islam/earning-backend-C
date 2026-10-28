# cms/INTEGRATION_SYSTEM/performance_monitor.py
"""
CMS Performance Monitor — tracks request latency, task duration, DB query counts.
Used by middleware.py and tasks to record performance metrics.
"""
import time
import logging
from typing import Dict, Any, Optional
from collections import defaultdict, deque

logger = logging.getLogger('cms.integration.perf')

# Rolling window of last N measurements per metric
_MAX_SAMPLES = 500
_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_SAMPLES))
_counters: Dict[str, int] = defaultdict(int)


class PerformanceMonitor:
    """
    Lightweight in-process performance monitor.
    Thread-safe for reads; uses deque for O(1) append/eviction.
    """

    # ── Recording ────────────────────────────────────────────────────────────

    @classmethod
    def record_request(cls, path: str, method: str, status_code: int,
                       duration_ms: float, user_id: Optional[int] = None) -> None:
        """Record an HTTP request's performance."""
        _metrics['request_duration_ms'].append(duration_ms)
        _counters['total_requests'] += 1
        if status_code >= 500:
            _counters['server_errors'] += 1
        elif status_code >= 400:
            _counters['client_errors'] += 1
        if duration_ms > 2000:
            _counters['slow_requests'] += 1
            logger.warning(f'[Perf] Slow request: {method} {path} {duration_ms:.0f}ms')

    @classmethod
    def record_task(cls, task_name: str, duration_s: float,
                    success: bool = True) -> None:
        """Record a Celery task's duration."""
        key = f'task_{task_name}_duration_s'
        _metrics[key].append(duration_s)
        _counters[f'task_{task_name}_total'] += 1
        if not success:
            _counters[f'task_{task_name}_failures'] += 1

    @classmethod
    def record_db_query(cls, query_count: int, duration_ms: float) -> None:
        """Record DB query count + duration for a request."""
        _metrics['db_query_count'].append(query_count)
        _metrics['db_query_duration_ms'].append(duration_ms)
        if query_count > 50:
            _counters['n_plus_1_suspects'] += 1

    @classmethod
    def increment(cls, counter_name: str, by: int = 1) -> None:
        _counters[counter_name] += by

    # ── Context manager ───────────────────────────────────────────────────────

    @classmethod
    def timer(cls, metric_name: str):
        """
        Context manager to time a code block:
            with PerformanceMonitor.timer('my_operation'):
                ...
        """
        return _Timer(metric_name)

    # ── Reporting ─────────────────────────────────────────────────────────────

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Return a performance stats snapshot."""
        stats: Dict[str, Any] = {'counters': dict(_counters)}
        for key, samples in _metrics.items():
            if samples:
                lst = list(samples)
                stats[key] = {
                    'count':   len(lst),
                    'avg':     round(sum(lst) / len(lst), 2),
                    'min':     round(min(lst), 2),
                    'max':     round(max(lst), 2),
                    'p95':     round(sorted(lst)[int(len(lst) * 0.95)], 2)
                               if len(lst) >= 20 else None,
                }
        return stats

    @classmethod
    def get_request_p95_ms(cls) -> Optional[float]:
        samples = list(_metrics.get('request_duration_ms', []))
        if len(samples) < 20:
            return None
        return round(sorted(samples)[int(len(samples) * 0.95)], 2)

    @classmethod
    def is_degraded(cls) -> bool:
        """Return True if recent performance indicates degradation."""
        p95 = cls.get_request_p95_ms()
        if p95 and p95 > 3000:
            return True
        errors = _counters.get('server_errors', 0)
        total  = _counters.get('total_requests', 1)
        if errors / total > 0.05:   # > 5% error rate
            return True
        return False

    @classmethod
    def reset(cls) -> None:
        """Clear all metrics. Used in tests."""
        _metrics.clear()
        _counters.clear()


class _Timer:
    """Context manager returned by PerformanceMonitor.timer()."""

    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.monotonic() - self._start) * 1000
        _metrics[self.metric_name].append(elapsed_ms)
        return False

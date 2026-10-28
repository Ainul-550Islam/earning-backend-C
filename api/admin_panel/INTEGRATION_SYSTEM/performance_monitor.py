# api/admin_panel/INTEGRATION_SYSTEM/performance_monitor.py
"""
PerformanceMonitor — Real-time integration performance tracking.
Tracks: response times, throughput, error rates, slow calls, bottlenecks.
"""
import time
import logging
import threading
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class MetricPoint:
    def __init__(self, app: str, action: str, duration_ms: int,
                 success: bool, timestamp: float = None):
        self.app = app
        self.action = action
        self.duration_ms = duration_ms
        self.success = success
        self.timestamp = timestamp or time.monotonic()

    def to_dict(self) -> Dict:
        return {
            'app': self.app,
            'action': self.action,
            'duration_ms': self.duration_ms,
            'success': self.success,
        }


class PerformanceMonitor:
    """Tracks integration call performance metrics in real-time."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._metrics: deque = deque(maxlen=10000)
        self._app_totals: Dict[str, Dict] = defaultdict(lambda: {
            'calls': 0, 'errors': 0, 'total_ms': 0, 'slow_calls': 0
        })
        self.SLOW_THRESHOLD_MS = 500

    def record(self, app: str, action: str, duration_ms: int, success: bool):
        """Record a metric point."""
        point = MetricPoint(app=app, action=action, duration_ms=duration_ms, success=success)
        self._metrics.append(point)
        totals = self._app_totals[app]
        totals['calls'] += 1
        totals['total_ms'] += duration_ms
        if not success:
            totals['errors'] += 1
        if duration_ms >= self.SLOW_THRESHOLD_MS:
            totals['slow_calls'] += 1
            logger.warning(f"[PerfMonitor] SLOW CALL: {app}.{action} took {duration_ms}ms")

    def timed_call(self, app: str, action: str):
        """Context manager for timing a call."""
        class _Timer:
            def __init__(self_, a, ac):
                self_.app = a
                self_.action = ac
                self_.start = None
            def __enter__(self_):
                self_.start = time.monotonic()
                return self_
            def __exit__(self_, exc_type, *args):
                duration_ms = int((time.monotonic() - self_.start) * 1000)
                self.record(self_.app, self_.action, duration_ms, exc_type is None)
        return _Timer(app, action)

    def get_app_stats(self, app: str) -> Dict:
        totals = self._app_totals.get(app, {})
        calls = totals.get('calls', 0)
        avg_ms = totals['total_ms'] / calls if calls else 0
        error_rate = totals['errors'] / calls * 100 if calls else 0
        return {
            'app': app,
            'total_calls': calls,
            'total_errors': totals.get('errors', 0),
            'error_rate_pct': round(error_rate, 2),
            'avg_response_ms': round(avg_ms, 2),
            'slow_calls': totals.get('slow_calls', 0),
        }

    def get_all_stats(self) -> Dict:
        return {app: self.get_app_stats(app) for app in self._app_totals.keys()}

    def get_slowest_calls(self, limit: int = 10) -> List[Dict]:
        recent = list(self._metrics)[-1000:]
        sorted_calls = sorted(recent, key=lambda x: x.duration_ms, reverse=True)
        return [m.to_dict() for m in sorted_calls[:limit]]

    def get_error_rate(self, app: str) -> float:
        totals = self._app_totals.get(app, {})
        calls = totals.get('calls', 0)
        return (totals.get('errors', 0) / calls * 100) if calls else 0.0

    def reset_app(self, app: str) -> bool:
        if app in self._app_totals:
            del self._app_totals[app]
            return True
        return False

    def push_to_cache(self) -> bool:
        """Push summary stats to cache for dashboard."""
        try:
            stats = self.get_all_stats()
            cache.set('admin_panel:perf_stats', stats, 60)
            return True
        except Exception as e:
            logger.error(f"[PerfMonitor] Cache push failed: {e}")
            return False

    def get_dashboard_summary(self) -> Dict:
        """Summary for admin dashboard widget."""
        all_stats = self.get_all_stats()
        total_calls = sum(v['total_calls'] for v in all_stats.values())
        total_errors = sum(v['total_errors'] for v in all_stats.values())
        avg_ms = (
            sum(v['avg_response_ms'] * v['total_calls'] for v in all_stats.values()) / total_calls
            if total_calls else 0
        )
        return {
            'total_calls': total_calls,
            'total_errors': total_errors,
            'global_error_rate': round(total_errors / total_calls * 100, 2) if total_calls else 0,
            'avg_response_ms': round(avg_ms, 2),
            'apps_tracked': len(all_stats),
            'slowest_calls': self.get_slowest_calls(5),
            'per_app': all_stats,
        }


# Global singleton
perf_monitor = PerformanceMonitor()
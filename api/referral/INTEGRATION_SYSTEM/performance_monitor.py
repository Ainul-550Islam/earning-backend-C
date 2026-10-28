# api/referral/INTEGRATION_SYSTEM/performance_monitor.py
# Performance monitoring for referral integration layer
# ============================================================

import time
import logging
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional
from collections import defaultdict, deque
from .integ_constants import (
    PERF_SLOW_QUERY_MS, PERF_CRITICAL_MS,
    PERF_COMMISSION_MAX_MS, PERF_FRAUD_CHECK_MAX_MS,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()


class PerformanceMonitor:
    """
    Tracks performance of referral integration operations.
    Integrates with api/analytics for reporting.
    """

    MAX_SAMPLES = 1000  # Keep last 1000 measurements per operation

    def __init__(self):
        self._timings: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.MAX_SAMPLES))
        self._call_counts: Dict[str, int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._slow_count: int = 0
        self._critical_count: int = 0

    @contextmanager
    def track(self, operation: str, threshold_ms: int = PERF_SLOW_QUERY_MS):
        """Context manager to track operation timing."""
        start = time.time()
        error_occurred = False
        try:
            yield
        except Exception:
            error_occurred = True
            with _lock:
                self._error_counts[operation] += 1
            raise
        finally:
            elapsed_ms = (time.time() - start) * 1000
            with _lock:
                self._timings[operation].append(elapsed_ms)
                self._call_counts[operation] += 1

            if elapsed_ms > PERF_CRITICAL_MS:
                self._critical_count += 1
                logger.error(
                    f'[PerfMonitor] CRITICAL SLOW: {operation} took {elapsed_ms:.0f}ms '
                    f'(threshold: {threshold_ms}ms)'
                )
            elif elapsed_ms > threshold_ms:
                self._slow_count += 1
                logger.warning(
                    f'[PerfMonitor] SLOW: {operation} took {elapsed_ms:.0f}ms'
                )

    def record(self, operation: str, elapsed_ms: float) -> None:
        """Record a timing measurement directly."""
        with _lock:
            self._timings[operation].append(elapsed_ms)
            self._call_counts[operation] += 1

    def get_stats(self, operation: str = None) -> dict:
        """Get performance statistics."""
        if operation:
            return self._get_op_stats(operation)
        return {
            op: self._get_op_stats(op)
            for op in self._timings
        }

    def _get_op_stats(self, operation: str) -> dict:
        timings = list(self._timings.get(operation, []))
        if not timings:
            return {'calls': 0}
        return {
            'calls': self._call_counts[operation],
            'errors': self._error_counts[operation],
            'avg_ms': round(sum(timings) / len(timings), 1),
            'min_ms': round(min(timings), 1),
            'max_ms': round(max(timings), 1),
            'p95_ms': round(sorted(timings)[int(len(timings) * 0.95)], 1) if len(timings) > 20 else None,
        }

    def get_summary(self) -> dict:
        return {
            'total_operations': len(self._timings),
            'slow_operations': self._slow_count,
            'critical_operations': self._critical_count,
            'operations': self.get_stats(),
        }

    def reset(self) -> None:
        with _lock:
            self._timings.clear()
            self._call_counts.clear()
            self._error_counts.clear()
            self._slow_count = 0
            self._critical_count = 0


# Global monitor instance
_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


def track_commission_processing(func):
    """Decorator to track commission processing performance."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_monitor().track('commission_processing', PERF_COMMISSION_MAX_MS):
            return func(*args, **kwargs)
    return wrapper


def track_fraud_check(func):
    """Decorator to track fraud detection performance."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_monitor().track('fraud_check', PERF_FRAUD_CHECK_MAX_MS):
            return func(*args, **kwargs)
    return wrapper
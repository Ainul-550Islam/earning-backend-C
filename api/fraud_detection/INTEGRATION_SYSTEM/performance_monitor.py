# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/performance_monitor.py
# =============================================================================
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

logger = logging.getLogger('fraud_detection.perf')

_MAX_SAMPLES = 1000   # Per-endpoint rolling window


@dataclass
class RequestSample:
    endpoint    : str
    method      : str
    status_code : int
    duration_ms : float
    timestamp   : float = field(default_factory=time.time)
    user_id     : Optional[int] = None
    error       : Optional[str] = None


class PerformanceMonitor:
    """Thread-safe rolling-window performance tracker."""

    def __init__(self, max_samples: int = _MAX_SAMPLES):
        self._max        = max_samples
        self._lock       = threading.Lock()
        self._samples    : Deque[RequestSample] = deque(maxlen=max_samples)
        self._alert_thresholds = {
            'p95_ms':   500.0,
            'error_rate': 0.05,
        }

    def record(self, sample: RequestSample) -> None:
        with self._lock:
            self._samples.append(sample)

    def get_metrics(self) -> dict:
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return {'total': 0}

        durations    = [s.duration_ms for s in samples]
        errors       = [s for s in samples if s.status_code >= 500 or s.error]
        sorted_d     = sorted(durations)
        n            = len(sorted_d)

        def percentile(pct: float) -> float:
            idx = int(pct / 100 * n)
            return sorted_d[min(idx, n - 1)]

        return {
            'total':       n,
            'avg_ms':      round(sum(durations) / n, 2),
            'p50_ms':      round(percentile(50), 2),
            'p95_ms':      round(percentile(95), 2),
            'p99_ms':      round(percentile(99), 2),
            'min_ms':      round(min(durations), 2),
            'max_ms':      round(max(durations), 2),
            'error_count': len(errors),
            'error_rate':  round(len(errors) / n, 4),
        }

    def get_alerts(self) -> List[dict]:
        metrics = self.get_metrics()
        alerts  = []
        if metrics.get('p95_ms', 0) > self._alert_thresholds['p95_ms']:
            alerts.append({
                'type':    'high_latency',
                'message': f"p95 latency {metrics['p95_ms']}ms exceeds threshold",
            })
        if metrics.get('error_rate', 0) > self._alert_thresholds['error_rate']:
            alerts.append({
                'type':    'high_error_rate',
                'message': f"Error rate {metrics['error_rate']:.1%} exceeds threshold",
            })
        return alerts

    def get_statistics(self) -> dict:
        return {**self.get_metrics(), 'alerts': self.get_alerts()}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_monitor : PerformanceMonitor | None = None
_mon_lock = threading.Lock()


def _get_monitor() -> PerformanceMonitor:
    global _monitor
    if _monitor is None:
        with _mon_lock:
            if _monitor is None:
                _monitor = PerformanceMonitor()
    return _monitor


def record_request(
    endpoint    : str,
    method      : str = 'GET',
    status_code : int = 200,
    duration_ms : float = 0.0,
    user_id     : Optional[int] = None,
    error       : Optional[str] = None,
) -> None:
    _get_monitor().record(RequestSample(
        endpoint=endpoint, method=method, status_code=status_code,
        duration_ms=duration_ms, user_id=user_id, error=error,
    ))


def get_performance_metrics() -> dict:
    return _get_monitor().get_metrics()


def get_performance_alerts() -> List[dict]:
    return _get_monitor().get_alerts()


def get_performance_statistics() -> dict:
    return _get_monitor().get_statistics()

# integration_system/performance_monitor.py
"""Performance Monitor — Tracks latency, throughput, error rates for all integrations."""
import logging, threading, time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager
from django.utils import timezone
logger = logging.getLogger(__name__)

class MetricWindow:
    """Sliding window metric collector."""
    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self._data: deque = deque()
        self._lock = threading.Lock()

    def record(self, value: float, success: bool = True):
        now = time.time()
        with self._lock:
            self._data.append((now, value, success))
            cutoff = now - self.window
            while self._data and self._data[0][0] < cutoff:
                self._data.popleft()

    def stats(self) -> Dict:
        with self._lock:
            data = list(self._data)
        if not data:
            return {"count": 0, "avg_ms": 0, "max_ms": 0, "min_ms": 0, "error_rate": 0, "throughput": 0}
        values = [v for _, v, _ in data]
        errors = sum(1 for _, _, s in data if not s)
        elapsed = (data[-1][0] - data[0][0]) or 1
        return {
            "count": len(data), "avg_ms": round(sum(values)/len(values), 2),
            "max_ms": round(max(values), 2), "min_ms": round(min(values), 2),
            "error_rate": round(errors / len(data) * 100, 2),
            "throughput": round(len(data) / elapsed, 2),
        }


class PerformanceMonitor:
    """Central performance monitoring service."""

    ALERT_THRESHOLDS = {
        "avg_latency_ms": 2000,    # Alert if avg > 2s
        "error_rate": 10,          # Alert if error rate > 10%
        "throughput_min": 0.1,     # Alert if throughput < 0.1/s
    }

    def __init__(self):
        self._metrics: Dict[str, MetricWindow] = defaultdict(MetricWindow)
        self._alerts: List[Dict] = []
        self._lock = threading.Lock()

    @contextmanager
    def track(self, operation: str, service: str = ""):
        """Context manager to track an operation's performance."""
        key = f"{service}.{operation}" if service else operation
        start = time.monotonic()
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._metrics[key].record(elapsed_ms, success)
            if elapsed_ms > self.ALERT_THRESHOLDS["avg_latency_ms"]:
                self._raise_alert(key, "high_latency", elapsed_ms)

    def record(self, operation: str, latency_ms: float, success: bool = True, service: str = ""):
        key = f"{service}.{operation}" if service else operation
        self._metrics[key].record(latency_ms, success)

    def get_stats(self, operation: str = None) -> Dict:
        if operation:
            return self._metrics[operation].stats()
        return {k: v.stats() for k, v in self._metrics.items()}

    def get_summary(self) -> Dict:
        stats = self.get_stats()
        critical = [k for k, v in stats.items() if v.get("error_rate", 0) > self.ALERT_THRESHOLDS["error_rate"]]
        return {"operations": len(stats), "critical": critical, "total_alerts": len(self._alerts), "stats": stats}

    def _raise_alert(self, operation: str, alert_type: str, value: float):
        alert = {"operation": operation, "type": alert_type, "value": value, "at": timezone.now().isoformat()}
        self._alerts.append(alert)
        logger.warning(f"PerfMonitor ALERT: {operation} {alert_type} = {value:.2f}")
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-500:]

    def clear(self):
        self._metrics.clear()
        self._alerts.clear()


performance_monitor = PerformanceMonitor()

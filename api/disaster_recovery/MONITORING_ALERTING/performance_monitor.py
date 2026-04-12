"""Performance Monitor — Tracks response times, throughput, error rates."""
import logging, time
from collections import deque
from datetime import datetime
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self, window_size: int = 1000):
        self._response_times = deque(maxlen=window_size)
        self._error_count = 0
        self._request_count = 0

    def record_request(self, duration_ms: float, is_error: bool = False):
        self._response_times.append(duration_ms)
        self._request_count += 1
        if is_error:
            self._error_count += 1

    def get_stats(self) -> dict:
        if not self._response_times:
            return {"status": "no_data"}
        times = sorted(self._response_times)
        n = len(times)
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate_percent": round(self._error_count / max(self._request_count, 1) * 100, 2),
            "avg_ms": round(sum(times) / n, 2),
            "p50_ms": round(times[n // 2], 2),
            "p95_ms": round(times[int(n * 0.95)], 2),
            "p99_ms": round(times[int(n * 0.99)], 2),
            "min_ms": round(times[0], 2),
            "max_ms": round(times[-1], 2),
        }

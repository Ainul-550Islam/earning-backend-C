"""Load Test — tests proxy intelligence under high request volume."""
import time
import threading
import logging

logger = logging.getLogger(__name__)


class ProxyIntelligenceLoadTest:
    """
    Simulates concurrent IP check requests to measure throughput
    and identify performance bottlenecks.
    """
    def __init__(self, target_rps: int = 100, duration_sec: int = 30,
                 tenant=None):
        self.target_rps = target_rps
        self.duration_sec = duration_sec
        self.tenant = tenant
        self.results = []
        self.errors = []
        self._lock = threading.Lock()

    def run(self) -> dict:
        """Execute the load test and return performance metrics."""
        test_ips = [f"192.168.{i//256}.{i%256}" for i in range(100)]
        threads = []
        start_time = time.time()
        request_count = 0

        while time.time() - start_time < self.duration_sec:
            ip = test_ips[request_count % len(test_ips)]
            t = threading.Thread(
                target=self._send_request,
                args=(ip,),
                daemon=True,
            )
            t.start()
            threads.append(t)
            request_count += 1
            time.sleep(1 / self.target_rps)

        for t in threads:
            t.join(timeout=5)

        elapsed = time.time() - start_time
        successful = len([r for r in self.results if r.get("success")])

        return {
            "total_requests": request_count,
            "successful": successful,
            "errors": len(self.errors),
            "duration_sec": round(elapsed, 2),
            "actual_rps": round(request_count / elapsed, 1),
            "avg_latency_ms": round(
                sum(r.get("latency_ms", 0) for r in self.results) /
                max(len(self.results), 1), 2
            ),
        }

    def _send_request(self, ip_address: str):
        try:
            from ..services import IPIntelligenceService
            start = time.time()
            svc = IPIntelligenceService(tenant=self.tenant)
            result = svc.quick_check(ip_address)
            latency = (time.time() - start) * 1000
            with self._lock:
                self.results.append({"success": True, "latency_ms": latency})
        except Exception as e:
            with self._lock:
                self.errors.append(str(e))

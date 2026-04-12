"""
Stress Tests — System behavior under extreme conditions.
"""
import pytest
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock


class TestCircuitBreakerStress:
    """Stress tests for circuit breaker under concurrent load."""

    def test_concurrent_circuit_breaker_calls(self):
        """Circuit breaker must be thread-safe under concurrent access."""
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("stress-test", failure_threshold=10, window_seconds=60)
        success_count = [0]
        error_count = [0]
        lock = threading.Lock()

        def make_call(should_fail: bool):
            try:
                if should_fail:
                    def fn():
                        raise Exception("fail")
                    cb.call(fn)
                else:
                    cb.call(lambda: "ok")
                with lock:
                    success_count[0] += 1
            except Exception:
                with lock:
                    error_count[0] += 1

        threads = []
        for i in range(50):
            t = threading.Thread(target=make_call, args=(i % 3 == 0,))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total = success_count[0] + error_count[0]
        assert total == 50, f"Expected 50 total calls, got {total}"

    def test_alert_manager_concurrent_evaluations(self):
        """Alert manager should handle concurrent metric evaluations."""
        from ..MONITORING_ALERTING.alert_manager import AlertManager
        manager = AlertManager()
        evaluation_count = [0]
        lock = threading.Lock()

        def evaluate_metric():
            manager.evaluate("cpu_percent", 50.0)
            with lock:
                evaluation_count[0] += 1

        threads = [threading.Thread(target=evaluate_metric) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert evaluation_count[0] == 20


class TestRetentionStress:
    """Stress tests for retention policy with large datasets."""

    def test_retention_with_10k_backups(self):
        """GFS retention should handle 10,000 backups efficiently."""
        from ..BACKUP_MANAGEMENT.backup_retention import BackupRetentionManager
        from datetime import timedelta
        mgr = BackupRetentionManager(daily_count=7, weekly_count=4, monthly_count=12)
        backups = [
            MagicMock(id=str(i), created_at=datetime.utcnow() - timedelta(days=i))
            for i in range(10000)
        ]
        start = time.monotonic()
        to_delete = mgr.get_backups_to_delete(backups)
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Retention calc took too long: {elapsed:.2f}s"
        assert len(to_delete) > 0
        assert len(to_delete) + len(backups) - len(to_delete) == 10000

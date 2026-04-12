"""
Failover Tests — Tests for failover detection, execution, and rollback.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestCircuitBreaker:
    """Tests for the circuit breaker pattern."""

    def test_closed_state_allows_calls(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state.value == "closed"

    def test_opens_after_threshold_failures(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
        cb = CircuitBreaker("test", failure_threshold=3, window_seconds=60)
        def failing_fn():
            raise ConnectionError("Service down")
        for _ in range(3):
            with pytest.raises(ConnectionError):
                cb.call(failing_fn)
        assert cb.state.value == "open"
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "should fail fast")

    def test_transitions_to_half_open_after_timeout(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        def failing_fn():
            raise Exception("fail")
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_fn)
        assert cb.state.value == "open"
        time.sleep(1.1)
        assert cb.state.value == "half_open"

    def test_closes_after_success_in_half_open(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        def failing_fn():
            raise Exception("fail")
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_fn)
        time.sleep(1.1)
        cb.call(lambda: "ok")
        cb.call(lambda: "ok")
        assert cb.state.value == "closed"

    def test_force_open_and_close(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
        cb = CircuitBreaker("test")
        cb.force_open()
        assert cb.state.value == "open"
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "ok")
        cb.force_close()
        assert cb.state.value == "closed"
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_get_status_dict(self):
        from ..FAILOVER_MANAGEMENT.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("my-service", failure_threshold=5)
        status = cb.get_status()
        assert status["name"] == "my-service"
        assert status["failure_threshold"] == 5
        assert "state" in status
        assert "failures_in_window" in status


class TestHealthChecker:
    """Tests for the health checker."""

    def test_check_disk_healthy(self):
        from ..FAILOVER_MANAGEMENT.health_checker import HealthChecker
        from ..enums import HealthStatus
        checker = HealthChecker()
        result = checker.check_disk("/", warning_pct=95.0, critical_pct=99.0)
        assert result["status"] in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.CRITICAL]
        assert "total_gb" in result
        assert "used_percent" in result

    def test_check_disk_usage_values(self):
        from ..FAILOVER_MANAGEMENT.health_checker import HealthChecker
        checker = HealthChecker()
        result = checker.check_disk("/")
        assert result["total_gb"] > 0
        assert 0 <= result["used_percent"] <= 100

    def test_check_tcp_unreachable_returns_down(self):
        from ..FAILOVER_MANAGEMENT.health_checker import HealthChecker
        from ..enums import HealthStatus
        checker = HealthChecker()
        result = checker.check_tcp("127.0.0.1", 19999, timeout=1)
        assert result["status"] == HealthStatus.DOWN

    def test_check_all_returns_summary(self):
        from ..FAILOVER_MANAGEMENT.health_checker import HealthChecker
        checker = HealthChecker()
        components = [{"name": "disk", "type": "disk", "path": "/"}]
        result = checker.check_all(components)
        assert "overall" in result
        assert "components" in result
        assert "disk" in result["components"]


class TestFailoverDetector:
    """Tests for automatic failover detection."""

    def test_failure_counter_increments(self):
        from ..FAILOVER_MANAGEMENT.failover_detector import FailoverDetector
        detector = FailoverDetector()
        count = detector.record_failure("db-primary")
        assert count == 1
        count = detector.record_failure("db-primary")
        assert count == 2

    def test_failure_counter_resets(self):
        from ..FAILOVER_MANAGEMENT.failover_detector import FailoverDetector
        detector = FailoverDetector()
        detector.record_failure("db-primary")
        detector.record_failure("db-primary")
        detector.reset_failures("db-primary")
        assert detector._failure_counts.get("db-primary", 0) == 0

    def test_should_not_failover_below_threshold(self):
        from ..FAILOVER_MANAGEMENT.failover_detector import FailoverDetector
        detector = FailoverDetector()
        for _ in range(2):
            detector.record_failure("db-primary")
        assert detector.should_failover("db-primary") is False

    def test_should_failover_at_threshold(self):
        from ..FAILOVER_MANAGEMENT.failover_detector import FailoverDetector
        from ..constants import FAILOVER_HEALTH_CHECK_FAILURES
        detector = FailoverDetector()
        for _ in range(FAILOVER_HEALTH_CHECK_FAILURES):
            detector.record_failure("db-primary")
        assert detector.should_failover("db-primary") is True

    def test_cooldown_prevents_repeated_failover(self):
        from ..FAILOVER_MANAGEMENT.failover_detector import FailoverDetector
        from ..constants import FAILOVER_HEALTH_CHECK_FAILURES
        detector = FailoverDetector()
        for _ in range(FAILOVER_HEALTH_CHECK_FAILURES):
            detector.record_failure("db-primary")
        # First check: should failover
        detector._last_failover["db-primary"] = datetime.utcnow()
        # Second check immediately after: cooldown prevents it
        assert detector.should_failover("db-primary") is False

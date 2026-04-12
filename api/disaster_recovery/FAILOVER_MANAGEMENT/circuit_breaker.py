"""
Circuit Breaker — Stops cascading failures by breaking the circuit when a service fails
"""
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation — requests pass through
    OPEN = "open"           # Service down — requests fail fast
    HALF_OPEN = "half_open" # Recovery test — allow one request through


class CircuitBreakerOpenError(Exception):
    """Raised when a request is rejected because the circuit is open."""
    pass


class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to prevent cascading failures.

    State transitions:
        CLOSED -> OPEN: failure_threshold failures within window
        OPEN -> HALF_OPEN: after recovery_timeout seconds
        HALF_OPEN -> CLOSED: success
        HALF_OPEN -> OPEN: failure
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        window_seconds: int = 60,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds

        self._state = CircuitState.CLOSED
        self._failures: list = []
        self._last_failure_time: datetime = None
        self._opened_at: datetime = None
        self._success_count: int = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._opened_at and (datetime.utcnow() - self._opened_at).total_seconds() >= self.recovery_timeout:
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (recovery window elapsed)")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker."""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit '{self.name}' is OPEN — service unavailable"
            )
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= 2:
                logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
                self._state = CircuitState.CLOSED
                self._failures.clear()
        elif self._state == CircuitState.CLOSED:
            self._failures.clear()

    def _on_failure(self):
        now = datetime.utcnow()
        self._last_failure_time = now
        cutoff = now - timedelta(seconds=self.window_seconds)
        self._failures = [t for t in self._failures if t > cutoff]
        self._failures.append(now)
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failure during recovery)")
            self._state = CircuitState.OPEN
            self._opened_at = now
        elif len(self._failures) >= self.failure_threshold:
            logger.error(f"Circuit {self.name}: CLOSED -> OPEN ({len(self._failures)} failures)")
            self._state = CircuitState.OPEN
            self._opened_at = now

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures_in_window": len(self._failures),
            "failure_threshold": self.failure_threshold,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "opened_at": self._opened_at.isoformat() if self._opened_at else None,
        }

    def force_open(self):
        """Manually open the circuit (e.g., during maintenance)."""
        logger.warning(f"Circuit {self.name}: manually OPENED")
        self._state = CircuitState.OPEN
        self._opened_at = datetime.utcnow()

    def force_close(self):
        """Manually close the circuit after maintenance."""
        logger.info(f"Circuit {self.name}: manually CLOSED")
        self._state = CircuitState.CLOSED
        self._failures.clear()

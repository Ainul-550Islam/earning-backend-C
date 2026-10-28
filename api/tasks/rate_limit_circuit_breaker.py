"""
tasks/rate_limit_circuit_breaker.py
Circuit breaker pattern for rate limiting system.
Automatically opens circuit when failure rate exceeds threshold.
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional, Callable, Any, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class RateLimitCircuitBreaker:
    """
    Circuit breaker for rate limiting system.
    Protects against cascading failures when rate limiter is overwhelmed.
    """

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: Exception = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def _get_cache_key(self, name: str) -> str:
        return f'circuit_breaker_{name}'

    def _load_state(self, name: str):
        """Load circuit breaker state from cache."""
        state_data = cache.get(self._get_cache_key(name))
        if state_data:
            self.failure_count = state_data.get('failure_count', 0)
            self.last_failure_time = state_data.get('last_failure_time')
            self.state = CircuitBreakerState(state_data.get('state', 'closed'))

    def _save_state(self, name: str):
        """Save circuit breaker state to cache."""
        state_data = {
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'state': self.state.value,
            'updated_at': timezone.now().isoformat(),
        }
        cache.set(self._get_cache_key(name), state_data, timeout=3600)  # 1 hour TTL

    def call(self, func: Callable, name: str, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        """
        self._load_state(name)

        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self._save_state(name)
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{name}' is OPEN"
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset failure count
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._reset()
                self._save_state(name)
            elif self.failure_count > 0:
                self.failure_count = 0
                self._save_state(name)

            return result

        except self.expected_exception as e:
            self._record_failure(name)
            raise e

    def _record_failure(self, name: str):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                f"[CIRCUIT_BREAKER] Circuit '{name}' opened after "
                f"{self.failure_count} failures"
            )

        self._save_state(name)

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _reset(self):
        """Reset the circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def get_state(self, name: str) -> Dict:
        """Get current circuit breaker state."""
        self._load_state(name)
        return {
            'name': name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RateLimitCircuitBreakerManager:
    """
    Manager for multiple circuit breakers in the rate limiting system.
    """

    def __init__(self):
        self.breakers = {}

    def get_or_create_breaker(self, name: str,
                             failure_threshold: int = 5,
                             recovery_timeout: int = 60) -> RateLimitCircuitBreaker:
        """Get or create a circuit breaker instance."""
        if name not in self.breakers:
            self.breakers[name] = RateLimitCircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return self.breakers[name]

    def check_rate_limit_with_circuit_breaker(self, limit_type: str, identifier: str) -> Tuple[bool, int]:
        """
        Check rate limit through circuit breaker.
        """
        from .middleware_rate_limit import RateLimitService

        breaker = self.get_or_create_breaker(f'rate_limit_{limit_type}')

        def _check_limit():
            service = RateLimitService()
            return service.check_limit(limit_type, identifier)

        try:
            return breaker.call(_check_limit, f'rate_limit_{limit_type}')
        except CircuitBreakerOpenException:
            # Circuit is open - fail fast
            logger.warning(
                f"[CIRCUIT_BREAKER] Rate limit check failed fast for {limit_type}:{identifier}"
            )
            return False, 0

    def get_all_breaker_states(self) -> Dict[str, Dict]:
        """Get states of all circuit breakers."""
        states = {}
        for name, breaker in self.breakers.items():
            states[name] = breaker.get_state(name)
        return states

    def reset_breaker(self, name: str) -> bool:
        """Manually reset a circuit breaker."""
        if name in self.breakers:
            self.breakers[name]._reset()
            self.breakers[name]._save_state(name)
            logger.info(f"[CIRCUIT_BREAKER] Manually reset breaker '{name}'")
            return True
        return False


# Global circuit breaker manager
circuit_breaker_manager = RateLimitCircuitBreakerManager()


def check_rate_limit_circuit_breaker(limit_type: str, identifier: str) -> Tuple[bool, int]:
    """
    Convenience function to check rate limit with circuit breaker protection.
    """
    return circuit_breaker_manager.check_rate_limit_with_circuit_breaker(limit_type, identifier)
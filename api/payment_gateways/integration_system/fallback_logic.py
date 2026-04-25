# api/payment_gateways/integration_system/fallback_logic.py
# Fallback strategies when integrations fail

import time
import logging
from typing import Callable, Any, List
from .integ_exceptions import FallbackExhaustedError
from .integ_constants import RETRY_CONFIG, Priority

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """
    Defines and executes fallback strategies when integration handlers fail.

    Strategies:
        - retry:      Retry with exponential backoff
        - circuit_breaker: Open circuit after N failures, reset after timeout
        - fallback_fn: Call alternative function on failure
        - log_and_continue: Log error, continue without raising
        - queue_for_retry: Push to retry queue, process later
    """

    def execute_with_retry(self, func: Callable, args: tuple = (),
                            kwargs: dict = None, max_retries: int = 3,
                            delay: float = 1.0, backoff: float = 2.0) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func:        Function to execute
            args:        Positional arguments
            kwargs:      Keyword arguments
            max_retries: Max retry attempts
            delay:       Initial delay in seconds
            backoff:     Multiply delay by this after each failure

        Returns:
            Function result

        Raises:
            FallbackExhaustedError: If all retries fail
        """
        kwargs   = kwargs or {}
        attempts = 0
        last_err = None

        while attempts <= max_retries:
            try:
                result = func(*args, **kwargs)
                if attempts > 0:
                    logger.info(f'{func.__name__}: succeeded after {attempts} retries')
                return result
            except Exception as e:
                last_err = e
                attempts += 1
                if attempts <= max_retries:
                    wait = delay * (backoff ** (attempts - 1))
                    logger.warning(f'{func.__name__}: attempt {attempts} failed ({e}), retrying in {wait:.1f}s')
                    time.sleep(wait)

        raise FallbackExhaustedError(func.__name__, max_retries)

    def execute_with_fallback(self, primary: Callable, fallback: Callable,
                               *args, **kwargs) -> Any:
        """Try primary; if it fails, call fallback."""
        try:
            return primary(*args, **kwargs)
        except Exception as e:
            logger.warning(f'{primary.__name__} failed ({e}), using fallback {fallback.__name__}')
            return fallback(*args, **kwargs)

    def execute_chain(self, funcs: List[Callable], *args, **kwargs) -> Any:
        """Try each function in order until one succeeds."""
        last_error = None
        for func in funcs:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.debug(f'{func.__name__} failed: {e}, trying next')
        raise FallbackExhaustedError('chain', len(funcs))

    def log_and_continue(self, func: Callable, *args, default=None, **kwargs) -> Any:
        """Execute function; on failure log and return default."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f'{func.__name__} failed: {e} — continuing with default={default}')
            return default


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    States:
        CLOSED:   Normal operation, calls go through
        OPEN:     Too many failures, calls blocked, returns fallback immediately
        HALF_OPEN:Testing if service recovered, allows one call through
    """

    from django.core.cache import cache as _cache

    CLOSED    = 'closed'
    OPEN      = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, name: str, failure_threshold: int = 5,
                 reset_timeout: int = 60):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.reset_timeout     = reset_timeout
        self._key_state        = f'cb_state:{name}'
        self._key_failures     = f'cb_failures:{name}'
        self._key_opened_at    = f'cb_opened:{name}'

    def call(self, func: Callable, *args,
              fallback=None, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        state = self._get_state()

        if state == self.OPEN:
            # Check if timeout elapsed (try half-open)
            if self._should_try_reset():
                self._set_state(self.HALF_OPEN)
            else:
                logger.debug(f'CircuitBreaker {self.name} OPEN — using fallback')
                return fallback() if callable(fallback) else fallback

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            if fallback is not None:
                return fallback() if callable(fallback) else fallback
            raise

    def _get_state(self) -> str:
        from django.core.cache import cache
        return cache.get(self._key_state, self.CLOSED)

    def _set_state(self, state: str):
        from django.core.cache import cache
        cache.set(self._key_state, state, self.reset_timeout * 10)

    def _on_success(self):
        from django.core.cache import cache
        cache.set(self._key_failures, 0, 3600)
        self._set_state(self.CLOSED)

    def _on_failure(self):
        from django.core.cache import cache
        failures = (cache.get(self._key_failures, 0) or 0) + 1
        cache.set(self._key_failures, failures, 3600)
        if failures >= self.failure_threshold:
            self._set_state(self.OPEN)
            cache.set(self._key_opened_at, time.time(), self.reset_timeout * 10)
            logger.warning(f'CircuitBreaker {self.name} OPENED after {failures} failures')

    def _should_try_reset(self) -> bool:
        from django.core.cache import cache
        opened_at = cache.get(self._key_opened_at, 0)
        return (time.time() - opened_at) >= self.reset_timeout

    def reset(self):
        from django.core.cache import cache
        cache.delete(self._key_state)
        cache.delete(self._key_failures)
        cache.delete(self._key_opened_at)
        logger.info(f'CircuitBreaker {self.name} manually reset')

    def get_status(self) -> dict:
        from django.core.cache import cache
        return {
            'name':     self.name,
            'state':    self._get_state(),
            'failures': cache.get(self._key_failures, 0),
            'threshold':self.failure_threshold,
        }


# Pre-built circuit breakers for each external app
wallet_cb          = CircuitBreaker('wallet',          failure_threshold=5, reset_timeout=60)
notifications_cb   = CircuitBreaker('notifications',   failure_threshold=10, reset_timeout=30)
fraud_detection_cb = CircuitBreaker('fraud_detection', failure_threshold=3, reset_timeout=120)
postback_engine_cb = CircuitBreaker('postback_engine', failure_threshold=5, reset_timeout=60)
analytics_cb       = CircuitBreaker('analytics',       failure_threshold=20, reset_timeout=30)

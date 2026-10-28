# api/djoyalty/integration_system/fallback_logic.py
"""
Fallback Logic -- Circuit Breaker + Retry + Fallback।
Prevents cascade failures when external services go down।
Pattern: Circuit Breaker (Martin Fowler) + Retry with Exponential Backoff।
"""
import logging
import time
import threading
from functools import wraps
from typing import Any, Callable, Optional, Tuple
from django.core.cache import cache
from .integ_constants import (
    CircuitBreakerState, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY,
    DEFAULT_CIRCUIT_THRESHOLD, DEFAULT_CIRCUIT_TIMEOUT,
    CACHE_KEY_CIRCUIT_BREAKER,
)
from .integ_exceptions import CircuitBreakerOpenError, DjoyaltyIntegrationError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker for external service calls।
    States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED।

    CLOSED: Normal operation
    OPEN: Service is down -- reject calls immediately
    HALF_OPEN: Testing recovery -- allow one call through

    Usage:
        cb = CircuitBreaker('bkash', threshold=5, timeout=60)

        @cb.call
        def make_payment():
            return bkash.create_payment(...)
    """

    def __init__(self, name: str,
                  failure_threshold: int = DEFAULT_CIRCUIT_THRESHOLD,
                  timeout: int = DEFAULT_CIRCUIT_TIMEOUT):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._lock = threading.Lock()

    @property
    def _cache_key(self) -> str:
        return CACHE_KEY_CIRCUIT_BREAKER.format(name=self.name)

    @property
    def _state_data(self) -> dict:
        return cache.get(self._cache_key) or {
            'state': CircuitBreakerState.CLOSED,
            'failure_count': 0,
            'last_failure_at': None,
            'opened_at': None,
        }

    def get_state(self) -> CircuitBreakerState:
        data = self._state_data
        state = data['state']

        if state == CircuitBreakerState.OPEN:
            opened_at = data.get('opened_at', 0)
            if time.time() - opened_at >= self.timeout:
                logger.info('CircuitBreaker[%s]: -> HALF_OPEN', self.name)
                self._set_state(CircuitBreakerState.HALF_OPEN, data)
                return CircuitBreakerState.HALF_OPEN

        return CircuitBreakerState(state)

    def _set_state(self, state: CircuitBreakerState, data: dict = None):
        if data is None:
            data = self._state_data
        data['state'] = state
        if state == CircuitBreakerState.OPEN:
            data['opened_at'] = time.time()
        cache.set(self._cache_key, data, timeout=self.timeout * 10)

    def record_success(self):
        """Record successful call -- reset failure count।"""
        data = self._state_data
        data['failure_count'] = 0
        data['state'] = CircuitBreakerState.CLOSED
        cache.set(self._cache_key, data, timeout=self.timeout * 10)
        logger.debug('CircuitBreaker[%s]: success recorded, CLOSED', self.name)

    def record_failure(self):
        """Record failed call -- increment counter, may open circuit।"""
        with self._lock:
            data = self._state_data
            data['failure_count'] = data.get('failure_count', 0) + 1
            data['last_failure_at'] = time.time()

            if data['failure_count'] >= self.failure_threshold:
                logger.warning(
                    'CircuitBreaker[%s]: %d failures -> OPEN',
                    self.name, data['failure_count']
                )
                data['state'] = CircuitBreakerState.OPEN
                data['opened_at'] = time.time()
            cache.set(self._cache_key, data, timeout=self.timeout * 10)

    def call(self, func: Callable) -> Callable:
        """Decorator to protect a function with circuit breaker।"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            state = self.get_state()

            if state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenError(self.name, retry_after=self.timeout)

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except DjoyaltyIntegrationError as e:
                self.record_failure()
                raise
            except Exception as e:
                self.record_failure()
                raise DjoyaltyIntegrationError(str(e), integration_name=self.name)

        return wrapper

    def is_open(self) -> bool:
        return self.get_state() == CircuitBreakerState.OPEN

    def reset(self):
        """Manually reset circuit breaker।"""
        cache.delete(self._cache_key)
        logger.info('CircuitBreaker[%s]: manually reset', self.name)


class RetryPolicy:
    """
    Retry policy with exponential backoff।

    Usage:
        @RetryPolicy.retry(max_retries=3, exceptions=(requests.exceptions.Timeout,))
        def call_external_api():
            ...
    """

    @staticmethod
    def retry(max_retries: int = DEFAULT_MAX_RETRIES,
               base_delay: float = DEFAULT_RETRY_DELAY,
               exponential: bool = True,
               exceptions: Tuple = (Exception,),
               on_retry: Callable = None):
        """Decorator: retry function on failure।"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(1, max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt == max_retries:
                            break
                        delay = base_delay * (2 ** (attempt - 1)) if exponential else base_delay
                        logger.warning(
                            'RetryPolicy: attempt %d/%d failed for %s, retrying in %.1fs: %s',
                            attempt, max_retries, func.__name__, delay, e
                        )
                        if on_retry:
                            on_retry(attempt, e)
                        time.sleep(delay)
                raise last_exc
            return wrapper
        return decorator

    @staticmethod
    def retry_once(func: Callable) -> Callable:
        """Simple one-retry decorator।"""
        return RetryPolicy.retry(max_retries=2)(func)


class FallbackChain:
    """
    Fallback chain -- try primary, then fallback services।
    E.g. bKash -> Nagad -> Manual cashout।

    Usage:
        chain = FallbackChain('cashout')
        chain.add(send_via_bkash, 'bkash')
        chain.add(send_via_nagad, 'nagad')
        chain.add(queue_for_manual, 'manual')
        result = chain.execute(customer, amount)
    """

    def __init__(self, name: str):
        self.name = name
        self._chain = []

    def add(self, func: Callable, label: str = '') -> 'FallbackChain':
        self._chain.append((label or func.__name__, func))
        return self

    def execute(self, *args, **kwargs) -> Any:
        """Execute chain -- returns first successful result।"""
        errors = []
        for label, func in self._chain:
            try:
                result = func(*args, **kwargs)
                if result:
                    logger.debug('FallbackChain[%s]: %s succeeded', self.name, label)
                    return result
            except Exception as e:
                errors.append(f'{label}: {e}')
                logger.warning('FallbackChain[%s]: %s failed: %s', self.name, label, e)

        logger.error('FallbackChain[%s]: all options failed: %s', self.name, errors)
        raise DjoyaltyIntegrationError(
            f'All fallbacks failed: {"; ".join(errors)}',
            integration_name=self.name,
        )


# ─── Pre-built Circuit Breakers ──────────────────────────────────────────────

bkash_cb    = CircuitBreaker('bkash',    failure_threshold=5, timeout=120)
nagad_cb    = CircuitBreaker('nagad',    failure_threshold=5, timeout=120)
sslcommerz_cb = CircuitBreaker('sslcommerz', failure_threshold=5, timeout=120)
sms_cb      = CircuitBreaker('sms',      failure_threshold=10, timeout=60)
push_cb     = CircuitBreaker('push',     failure_threshold=10, timeout=60)
email_cb    = CircuitBreaker('email',    failure_threshold=5, timeout=120)
ocr_cb      = CircuitBreaker('ocr',      failure_threshold=3, timeout=300)


def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers।"""
    breakers = {
        'bkash': bkash_cb,
        'nagad': nagad_cb,
        'sslcommerz': sslcommerz_cb,
        'sms': sms_cb,
        'push': push_cb,
        'email': email_cb,
        'ocr': ocr_cb,
    }
    return {
        name: {
            'state': cb.get_state(),
            'is_open': cb.is_open(),
        }
        for name, cb in breakers.items()
    }

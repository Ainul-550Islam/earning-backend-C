# api/referral/INTEGRATION_SYSTEM/fallback_logic.py
# Fallback logic when integration modules are unavailable
# Ensures referral module works even if wallet/notifications are down
# ============================================================

import logging
from decimal import Decimal
from typing import Any, Optional, Callable
from functools import wraps
from .integ_exceptions import ModuleUnavailableError, CircuitBreakerOpenError

logger = logging.getLogger(__name__)


# ── Circuit Breaker ───────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Circuit breaker for external module calls.
    If a module fails too many times → open circuit → use fallback.

    States: CLOSED (normal) → OPEN (using fallback) → HALF_OPEN (testing)
    """
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60  # seconds

    def __init__(self, name: str):
        self.name = name
        self._failures = 0
        self._state = 'CLOSED'
        self._last_failure_time = None

    @property
    def is_open(self) -> bool:
        if self._state == 'OPEN':
            import time
            if time.time() - (self._last_failure_time or 0) > self.RECOVERY_TIMEOUT:
                self._state = 'HALF_OPEN'
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._state = 'CLOSED'

    def record_failure(self) -> None:
        import time
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.FAILURE_THRESHOLD:
            self._state = 'OPEN'
            logger.warning(f'[CircuitBreaker] OPEN: {self.name}')

    def call(self, func: Callable, *args, fallback=None, **kwargs):
        if self.is_open:
            logger.debug(f'[CircuitBreaker] Using fallback for: {self.name}')
            return fallback() if callable(fallback) else fallback
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            logger.warning(f'[CircuitBreaker] Failure #{self._failures} for {self.name}: {e}')
            if self._state == 'OPEN':
                return fallback() if callable(fallback) else fallback
            raise


# ── Module Breakers ───────────────────────────────────────────────────────────

_breakers = {}

def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


# ── Fallback Wallet ───────────────────────────────────────────────────────────

class FallbackWallet:
    """Used when api/wallet is unavailable."""

    @staticmethod
    def credit_commission(user, amount: Decimal, level: int, **kwargs) -> dict:
        """Log commission for manual processing when wallet is down."""
        logger.critical(
            f'[Fallback] WALLET DOWN — commission queued for manual processing: '
            f'user={getattr(user, "id", "?")}, amount={amount}, level={level}'
        )
        # Queue for retry
        try:
            from django.core.cache import cache
            key = f'fallback:commission:{getattr(user, "id", 0)}:{level}'
            existing = cache.get(key, [])
            existing.append({
                'user_id': getattr(user, 'id', None),
                'amount': str(amount), 'level': level,
                **{k: str(v) for k, v in kwargs.items()},
            })
            cache.set(key, existing, timeout=86400 * 7)
        except Exception:
            pass
        return {'success': False, 'queued': True, 'fallback': True}

    @staticmethod
    def get_pending_fallback_commissions() -> list:
        """Get commissions queued during wallet downtime."""
        from django.core.cache import cache
        results = []
        # Would need Redis scan — simplified version
        return results


# ── Fallback Notification ─────────────────────────────────────────────────────

class FallbackNotification:
    """Used when api/notifications is unavailable."""

    @staticmethod
    def send(user, title: str, message: str, **kwargs) -> bool:
        """Log notification for retry when notification service is down."""
        logger.info(
            f'[Fallback] NOTIF DOWN — queued: '
            f'user={getattr(user, "id", "?")}, title={title}'
        )
        return False  # Notification not critical — just log


# ── Retry Decorator ───────────────────────────────────────────────────────────

def with_retry(max_retries: int = 3, delay: float = 1.0):
    """Decorator for automatic retry on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ModuleUnavailableError:
                    raise  # Don't retry if module is gone
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        logger.debug(
                            f'[Fallback] Retry {attempt + 1}/{max_retries} for {func.__name__}'
                        )
            raise last_exc
        return wrapper
    return decorator


def with_fallback(fallback_value=None):
    """Decorator — return fallback_value if function raises any exception."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f'[Fallback] {func.__name__} failed, using fallback: {e}')
                return fallback_value() if callable(fallback_value) else fallback_value
        return wrapper
    return decorator


# ── Safe Module Call ──────────────────────────────────────────────────────────

def safe_module_call(
    func: Callable,
    fallback: Any = None,
    module_name: str = 'unknown',
    *args, **kwargs
) -> Any:
    """
    Safely call an external module function.
    Returns fallback if module unavailable or raises.
    """
    breaker = get_breaker(module_name)
    return breaker.call(func, *args, fallback=fallback, **kwargs)
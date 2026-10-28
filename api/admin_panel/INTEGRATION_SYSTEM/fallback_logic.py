# api/admin_panel/INTEGRATION_SYSTEM/fallback_logic.py
"""
FallbackLogic — Circuit breaker and graceful degradation.
When an app is down, fallback to cache, defaults, or safe no-ops.
"""
import logging
import time
from typing import Any, Callable, Dict, Optional
from django.core.cache import cache
from .integ_constants import HEALTH_STATUSES

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker pattern — stops calling a failing service.
    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)
    """
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, app_name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max: int = 2):
        self.app_name = app_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._state = self.CLOSED
        self._failures = 0
        self._last_failure_time = 0
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def call(self, func: Callable, *args, fallback=None, **kwargs) -> Any:
        """Call function with circuit breaker protection."""
        state = self.state
        if state == self.OPEN:
            logger.warning(f"[CircuitBreaker] OPEN for {self.app_name} — returning fallback")
            return fallback() if callable(fallback) else fallback

        if state == self.HALF_OPEN and self._half_open_calls >= self.half_open_max:
            logger.warning(f"[CircuitBreaker] HALF_OPEN call limit for {self.app_name}")
            return fallback() if callable(fallback) else fallback

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            if self._state == self.OPEN:
                logger.error(f"[CircuitBreaker] {self.app_name} OPENED after {self._failures} failures")
            if fallback is not None:
                return fallback() if callable(fallback) else fallback
            raise

    def _on_success(self):
        self._failures = 0
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED
            logger.info(f"[CircuitBreaker] {self.app_name} RECOVERED → CLOSED")

    def _on_failure(self):
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failures >= self.failure_threshold:
            self._state = self.OPEN

    def reset(self):
        self._state = self.CLOSED
        self._failures = 0

    def is_open(self) -> bool:
        return self.state == self.OPEN

    def to_dict(self) -> Dict:
        return {
            'app': self.app_name,
            'state': self.state,
            'failures': self._failures,
            'threshold': self.failure_threshold,
        }


class FallbackManager:
    """
    Manages fallback strategies for all apps.
    Returns safe defaults when an app is unavailable.
    """
    _circuit_breakers: Dict[str, CircuitBreaker] = {}

    @classmethod
    def get_breaker(cls, app_name: str) -> CircuitBreaker:
        if app_name not in cls._circuit_breakers:
            cls._circuit_breakers[app_name] = CircuitBreaker(app_name)
        return cls._circuit_breakers[app_name]

    @classmethod
    def safe_call(cls, app_name: str, func: Callable, fallback=None, *args, **kwargs) -> Any:
        """Call a function with circuit breaker + fallback."""
        breaker = cls.get_breaker(app_name)
        return breaker.call(func, *args, fallback=fallback, **kwargs)

    @classmethod
    def get_cached_or_default(cls, cache_key: str, default: Any = None, ttl: int = 300) -> Any:
        """Return cached value or default if cache miss."""
        value = cache.get(cache_key)
        if value is not None:
            return value
        return default

    @classmethod
    def get_breaker_states(cls) -> Dict:
        return {app: cb.to_dict() for app, cb in cls._circuit_breakers.items()}

    @classmethod
    def reset_breaker(cls, app_name: str) -> bool:
        if app_name in cls._circuit_breakers:
            cls._circuit_breakers[app_name].reset()
            return True
        return False

    # ==================== SAFE DEFAULTS ====================

    @staticmethod
    def safe_wallet_balance(user_id: Any) -> Dict:
        """Return cached or default wallet balance."""
        cache_key = f'wallet:balance:{user_id}'
        cached = cache.get(cache_key)
        return cached or {'balance': 0.0, 'is_cached': True, 'note': 'Wallet service unavailable'}

    @staticmethod
    def safe_user_status(user_id: Any) -> Dict:
        """Return cached or default user status."""
        cache_key = f'user:status:{user_id}'
        cached = cache.get(cache_key)
        return cached or {'is_active': None, 'note': 'User service unavailable'}

    @staticmethod
    def safe_fraud_score(user_id: Any) -> Dict:
        """Return default fraud score when fraud service unavailable."""
        return {'score': 0, 'level': 'unknown', 'note': 'Fraud detection unavailable — manual review required'}

    @staticmethod
    def safe_feature_flag(flag_key: str, default: bool = False) -> bool:
        """Return cached flag or default when config service unavailable."""
        cache_key = f'admin_panel:feature_flag:{flag_key}'
        value = cache.get(cache_key)
        return value if value is not None else default

    @staticmethod
    def safe_system_config(config_key: str, default: Any = None) -> Any:
        """Return cached config or default when config unavailable."""
        cache_key = f'admin_panel:config:{config_key}'
        value = cache.get(cache_key)
        return value if value is not None else default
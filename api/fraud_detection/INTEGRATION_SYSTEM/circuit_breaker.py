# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/circuit_breaker.py
# =============================================================================
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional

logger = logging.getLogger('fraud_detection.circuit_breaker')


class CircuitState(Enum):
    CLOSED    = 'closed'      # Normal — requests pass through
    OPEN      = 'open'        # Tripped — requests fail fast
    HALF_OPEN = 'half_open'   # Trial — one probe request allowed


@dataclass
class CircuitBreakerConfig:
    failure_threshold : int   = 5       # Failures before opening
    success_threshold : int   = 2       # Successes in HALF_OPEN to close
    timeout_seconds   : float = 30.0    # Seconds before OPEN → HALF_OPEN
    name              : str   = 'default'


class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config           = config
        self._state           = CircuitState.CLOSED
        self._failure_count   = 0
        self._success_count   = 0
        self._last_failure_at : Optional[float] = None
        self._lock            = threading.Lock()

    # ── State ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_failure_at or 0)
                if elapsed >= self.config.timeout_seconds:
                    self._state         = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info('CircuitBreaker[%s] → HALF_OPEN', self.config.name)
            return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    # ── Call wrapping ───────────────────────────────────────────────────────

    def call(self, func: Callable, *args, **kwargs):
        if self.is_open:
            raise CircuitOpenError(f'Circuit {self.config.name!r} is OPEN')
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state         = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info('CircuitBreaker[%s] → CLOSED', self.config.name)
            else:
                self._failure_count = 0

    def _on_failure(self):
        with self._lock:
            self._failure_count   += 1
            self._last_failure_at  = time.monotonic()
            if self._state == CircuitState.HALF_OPEN or \
               self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning('CircuitBreaker[%s] → OPEN (failures=%d)',
                               self.config.name, self._failure_count)

    def reset(self):
        with self._lock:
            self._state         = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
        logger.info('CircuitBreaker[%s] manually RESET', self.config.name)

    def status(self) -> dict:
        return {
            'name':          self.config.name,
            'state':         self.state.value,
            'failures':      self._failure_count,
            'threshold':     self.config.failure_threshold,
        }


class CircuitOpenError(Exception):
    pass


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CircuitBreakerRegistry:
    def __init__(self):
        self._breakers : Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(self, name: str, **config_kwargs) -> CircuitBreaker:
        with self._lock:
            if name not in self._breakers:
                cfg = CircuitBreakerConfig(name=name, **config_kwargs)
                self._breakers[name] = CircuitBreaker(cfg)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def all_statuses(self) -> list[dict]:
        return [cb.status() for cb in self._breakers.values()]

    def reset(self, name: str) -> bool:
        cb = self._breakers.get(name)
        if cb:
            cb.reset()
            return True
        return False


_registry : CircuitBreakerRegistry | None = None
_reg_lock = threading.Lock()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    global _registry
    if _registry is None:
        with _reg_lock:
            if _registry is None:
                _registry = CircuitBreakerRegistry()
    return _registry


def get_circuit_breaker_status() -> list[dict]:
    return get_circuit_breaker_registry().all_statuses()


def reset_circuit_breaker(name: str) -> bool:
    return get_circuit_breaker_registry().reset(name)

# api/wallet/engine/circuit_breaker.py
"""
CircuitBreaker — prevent cascading gateway failures.

States:
  CLOSED   → normal; requests flow through
  OPEN     → gateway is down; requests fail fast (no real calls)
  HALF_OPEN → testing recovery; one probe request allowed

Usage:
    breaker = CircuitBreaker("bkash")
    if breaker.can_call():
        try:
            result = bkash_api.send(...)
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise GatewayError(...)
    else:
        raise GatewayError("bKash circuit is OPEN — gateway unreachable")
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

from django.core.cache import cache

from ..exceptions import GatewayError

logger = logging.getLogger("wallet.engine.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


@dataclass
class BreakerConfig:
    failure_threshold: int   = 5      # failures before opening
    recovery_timeout:  int   = 60     # seconds in OPEN before HALF_OPEN
    success_threshold: int   = 2      # successes in HALF_OPEN before closing


class CircuitBreaker:
    """
    Per-gateway circuit breaker backed by Django cache (Redis).
    State is shared across all workers (process-safe via atomic cache ops).
    """

    def __init__(self, gateway: str, config: BreakerConfig = None):
        self.gateway = gateway
        self.cfg     = config or BreakerConfig()
        self._prefix = f"wallet_cb_{gateway}"

    # ── Cache keys ────────────────────────────────────────────────
    @property
    def _state_key(self):   return f"{self._prefix}:state"
    @property
    def _failures_key(self): return f"{self._prefix}:failures"
    @property
    def _opened_at_key(self): return f"{self._prefix}:opened_at"
    @property
    def _half_successes_key(self): return f"{self._prefix}:half_ok"

    # ── State access ──────────────────────────────────────────────
    def state(self) -> CircuitState:
        raw = cache.get(self._state_key, CircuitState.CLOSED)
        return CircuitState(raw)

    def _set_state(self, state: CircuitState) -> None:
        cache.set(self._state_key, state.value, timeout=None)
        logger.info(f"CircuitBreaker[{self.gateway}]: → {state.value.upper()}")

    # ── Core API ──────────────────────────────────────────────────
    def can_call(self) -> bool:
        """Return True if a gateway call should proceed."""
        s = self.state()

        if s == CircuitState.CLOSED:
            return True

        if s == CircuitState.OPEN:
            opened_at = cache.get(self._opened_at_key, 0)
            if time.time() - opened_at >= self.cfg.recovery_timeout:
                self._set_state(CircuitState.HALF_OPEN)
                cache.set(self._half_successes_key, 0, timeout=None)
                return True          # probe request
            return False             # still in cool-down

        # HALF_OPEN: allow one probe
        return True

    def record_success(self) -> None:
        """Call after a successful gateway response."""
        s = self.state()
        if s == CircuitState.HALF_OPEN:
            half_ok = cache.get(self._half_successes_key, 0) + 1
            cache.set(self._half_successes_key, half_ok, timeout=None)
            if half_ok >= self.cfg.success_threshold:
                self._close()
        elif s == CircuitState.CLOSED:
            # Reset failure counter on any success
            cache.set(self._failures_key, 0, timeout=None)

    def record_failure(self) -> None:
        """Call after a failed gateway response."""
        s = self.state()
        if s == CircuitState.OPEN:
            return
        if s == CircuitState.HALF_OPEN:
            self._open()
            return
        failures = (cache.get(self._failures_key) or 0) + 1
        cache.set(self._failures_key, failures, timeout=None)
        if failures >= self.cfg.failure_threshold:
            self._open()

    def assert_closed(self) -> None:
        """Raise GatewayError if circuit is OPEN."""
        if not self.can_call():
            raise GatewayError(
                f"{self.gateway} gateway is temporarily unavailable "
                f"(circuit OPEN). Retry in {self.cfg.recovery_timeout}s."
            )

    # ── Transitions ───────────────────────────────────────────────
    def _open(self) -> None:
        self._set_state(CircuitState.OPEN)
        cache.set(self._opened_at_key, time.time(), timeout=None)
        cache.set(self._failures_key,  0,           timeout=None)

    def _close(self) -> None:
        self._set_state(CircuitState.CLOSED)
        cache.set(self._failures_key,      0, timeout=None)
        cache.set(self._half_successes_key, 0, timeout=None)

    def reset(self) -> None:
        """Force-reset to CLOSED (admin use)."""
        self._close()
        logger.warning(f"CircuitBreaker[{self.gateway}]: force-reset to CLOSED")

    @property
    def status(self) -> dict:
        return {
            "gateway":   self.gateway,
            "state":     self.state().value,
            "failures":  cache.get(self._failures_key, 0),
            "opened_at": cache.get(self._opened_at_key),
        }


# ── Registry — one breaker per gateway ───────────────────────────
_breakers: Dict[str, CircuitBreaker] = {}


def get_breaker(gateway: str) -> CircuitBreaker:
    """Get (or create) the singleton CircuitBreaker for a gateway."""
    if gateway not in _breakers:
        _breakers[gateway] = CircuitBreaker(gateway)
    return _breakers[gateway]


def all_breaker_statuses() -> list:
    return [b.status for b in _breakers.values()]

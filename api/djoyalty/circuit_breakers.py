# api/djoyalty/circuit_breakers.py
"""
Djoyalty Circuit Breakers -- Per-service circuit breaker registry।
Prevents cascade failures when external services (bKash, Nagad, SMS) go down।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
import time
import threading
from enum import Enum
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CBState(Enum):
    CLOSED   = 'closed'    # Normal operation
    OPEN     = 'open'      # Failing -- reject calls
    HALF_OPEN = 'half_open' # Testing recovery


class CircuitBreaker:
    """
    Per-service circuit breaker with Redis-backed state।
    State survives process restarts (stored in Redis)।

    Usage:
        cb = get_circuit_breaker('bkash')
        if cb.is_open():
            raise ServiceUnavailableError('bKash is down')
        try:
            result = call_bkash_api()
            cb.record_success()
        except Exception as e:
            cb.record_failure()
            raise
    """

    def __init__(self, service_name: str = None, name: str = None, failure_threshold: int = 5,
                 timeout: int = 60, recovery_timeout: int = None, half_open_calls: int = 1):
        self.service = service_name
        self.failure_threshold = failure_threshold
        self.timeout = recovery_timeout or timeout  # seconds before trying again
        self.half_open_calls = half_open_calls
        self._key = f'djoyalty:cb:{service_name}'
        self._lock = threading.Lock()

    def _get_state(self) -> dict:
        """Get state from Redis."""
        try:
            state = cache.get(self._key)
            if state is None:
                return {'state': CBState.CLOSED.value, 'failures': 0, 'opened_at': None}
            return state
        except Exception:
            return {'state': CBState.CLOSED.value, 'failures': 0, 'opened_at': None}

    def _set_state(self, state: dict):
        """Save state to Redis (no expiry -- circuit state persists)."""
        try:
            cache.set(self._key, state, timeout=None)
        except Exception as e:
            logger.debug('CircuitBreaker._set_state error: %s', e)

    def get_state(self) -> CBState:
        state_dict = self._get_state()
        state_str = state_dict.get('state', CBState.CLOSED.value)

        # Auto-transition OPEN -> HALF_OPEN after timeout
        if state_str == CBState.OPEN.value:
            opened_at = state_dict.get('opened_at')
            if opened_at and (time.time() - opened_at) > self.timeout:
                self._transition_to(CBState.HALF_OPEN)
                return CBState.HALF_OPEN

        return CBState(state_str)

    def is_open(self) -> bool:
        return self.get_state() == CBState.OPEN

    def is_closed(self) -> bool:
        return self.get_state() == CBState.CLOSED

    def is_half_open(self) -> bool:
        return self.get_state() == CBState.HALF_OPEN

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            state_dict = self._get_state()
            if state_dict.get('state') in (CBState.HALF_OPEN.value, CBState.OPEN.value):
                # Recovery! Close the circuit
                self._transition_to(CBState.CLOSED)
                logger.info('CircuitBreaker [%s]: RECOVERED -> CLOSED', self.service)
            else:
                # Reset failure count on success
                state_dict['failures'] = 0
                self._set_state(state_dict)

    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            state_dict = self._get_state()
            failures = state_dict.get('failures', 0) + 1
            state_dict['failures'] = failures

            if state_dict.get('state') == CBState.HALF_OPEN.value:
                # Failed during recovery -- reopen
                self._transition_to(CBState.OPEN)
                logger.warning('CircuitBreaker [%s]: HALF_OPEN failed -> OPEN', self.service)
            elif failures >= self.failure_threshold:
                # Threshold exceeded -- open circuit
                self._transition_to(CBState.OPEN)
                logger.error(
                    'CircuitBreaker [%s]: %d failures -> OPEN (retry after %ds)',
                    self.service, failures, self.timeout,
                )
            else:
                self._set_state(state_dict)

    def _transition_to(self, new_state: CBState):
        state_dict = self._get_state()
        state_dict['state'] = new_state.value
        if new_state == CBState.OPEN:
            state_dict['opened_at'] = time.time()
        elif new_state == CBState.CLOSED:
            state_dict['failures'] = 0
            state_dict['opened_at'] = None
        self._set_state(state_dict)

    def reset(self):
        """Manually reset circuit to CLOSED state."""
        self._transition_to(CBState.CLOSED)
        logger.info('CircuitBreaker [%s]: manually reset to CLOSED', self.service)

    def get_info(self) -> dict:
        state_dict = self._get_state()
        return {
            'service': self.service,
            'state': state_dict.get('state'),
            'failures': state_dict.get('failures', 0),
            'threshold': self.failure_threshold,
            'timeout_seconds': self.timeout,
            'opened_at': state_dict.get('opened_at'),
        }


# ─── Registry ────────────────────────────────────────────────────────────────

_breakers: dict = {}
_breaker_lock = threading.Lock()


def get_circuit_breaker(service_name: str, failure_threshold: int = 5,
                         timeout: int = 60) -> CircuitBreaker:
    """Get or create a circuit breaker for a service."""
    with _breaker_lock:
        if service_name not in _breakers:
            _breakers[service_name] = CircuitBreaker(
                service_name,
                failure_threshold=failure_threshold,
                timeout=timeout,
            )
        return _breakers[service_name]


def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers -- for monitoring dashboard."""
    return {name: cb.get_info() for name, cb in _breakers.items()}


# Pre-create breakers for known services
_known_services = [
    ('bkash', 5, 60),
    ('nagad', 5, 60),
    ('sslcommerz', 5, 120),
    ('sms', 10, 30),
    ('email', 10, 60),
    ('fcm_push', 10, 30),
    ('openai', 3, 300),
    ('cpalead', 5, 60),
]

for _svc, _thresh, _timeout in _known_services:
    get_circuit_breaker(_svc, _thresh, _timeout)

# api/support/integrations/fallback_logic.py  — WORLD #1
"""
Fallback Logic — Integration fail হলে graceful fallback।
Circuit breaker + retry + degraded mode।
"""
import logging
import time
import functools
from collections import defaultdict
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern for integration calls.
    If an integration fails N times → open circuit → use fallback.
    
    States: closed (normal) → open (failing) → half-open (testing)
    """
    CLOSED    = 'closed'
    OPEN      = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self._lock             = Lock()
        self._state            = self.CLOSED
        self._failure_count    = 0
        self._last_failure     = None
        self._success_count    = 0

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if self._last_failure and time.time() - self._last_failure > self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info(f'Circuit [{self.name}]: OPEN → HALF_OPEN')
            return self._state

    def call(self, func: Callable, *args, fallback=None, **kwargs):
        """Execute function with circuit breaker."""
        state = self.state
        if state == self.OPEN:
            logger.warning(f'Circuit [{self.name}] is OPEN. Using fallback.')
            return fallback() if callable(fallback) else fallback

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            logger.error(f'Circuit [{self.name}] failure ({self._failure_count}/{self.failure_threshold}): {e}')
            if callable(fallback):
                return fallback()
            return fallback

    def _on_success(self):
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._state          = self.CLOSED
                self._failure_count  = 0
                logger.info(f'Circuit [{self.name}]: HALF_OPEN → CLOSED')
            self._success_count += 1

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure   = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.error(f'Circuit [{self.name}]: CLOSED → OPEN after {self._failure_count} failures')

    def get_status(self) -> dict:
        return {'name': self.name, 'state': self.state, 'failures': self._failure_count, 'successes': self._success_count}


class SupportFallbackManager:
    """
    Manages fallback behavior when integrations are unavailable.
    Ensures support system continues working even if wallet/fraud/etc. are down.
    """

    def __init__(self):
        self._circuits = {
            'wallet':        CircuitBreaker('wallet', failure_threshold=5, recovery_timeout=60),
            'fraud':         CircuitBreaker('fraud', failure_threshold=10, recovery_timeout=30),
            'postback':      CircuitBreaker('postback', failure_threshold=5, recovery_timeout=120),
            'notifications': CircuitBreaker('notifications', failure_threshold=10, recovery_timeout=60),
            'kyc':           CircuitBreaker('kyc', failure_threshold=5, recovery_timeout=60),
        }

    def get_wallet_balance(self, user) -> dict:
        """Get wallet balance with fallback."""
        def call_wallet():
            from .integ_adapter import wallet_adapter
            return wallet_adapter.get_balance(user)
        return self._circuits['wallet'].call(
            call_wallet,
            fallback={'available':0,'pending':0,'frozen':0,'total_earned':0,'error':'Wallet service unavailable'}
        )

    def get_fraud_risk(self, user) -> dict:
        """Get fraud risk with fallback (assume safe if unavailable)."""
        def call_fraud():
            from .integ_adapter import fraud_adapter
            return fraud_adapter.get_risk_score(user)
        return self._circuits['fraud'].call(
            call_fraud,
            fallback={'score':0,'is_high_risk':False,'is_flagged':False,'warning':'Fraud service unavailable — assuming safe'}
        )

    def send_notification(self, user, title: str, body: str) -> bool:
        """Send notification with fallback to email."""
        def call_notify():
            from .integ_adapter import notifications_adapter
            return notifications_adapter.send(user, title, body)
        def fallback():
            try:
                from django.core.mail import send_mail
                from django.conf import settings as ds
                send_mail(title, body, getattr(ds,'DEFAULT_FROM_EMAIL','support@site.com'), [user.email], fail_silently=True)
                logger.info(f'Fallback email sent to {user.email}')
                return True
            except Exception:
                logger.error(f'All notification methods failed for user {user.id}')
                return False
        return self._circuits['notifications'].call(call_notify, fallback=fallback)

    def verify_offer(self, user, offer_id: str, click_id: str) -> dict:
        """Verify offer with fallback to manual review."""
        def call_verify():
            from .integ_adapter import postback_adapter
            return postback_adapter.verify_offer_completion(user, offer_id, click_id)
        return self._circuits['postback'].call(
            call_verify,
            fallback={'found':False,'confidence':0.0,'status':'service_unavailable','details':['Verification service unavailable — manual review required.']}
        )

    def get_circuit_status(self) -> dict:
        """Get all circuit breaker statuses."""
        return {name: cb.get_status() for name, cb in self._circuits.items()}


fallback_manager = SupportFallbackManager()
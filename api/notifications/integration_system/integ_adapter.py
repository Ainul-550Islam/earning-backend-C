# integration_system/integ_adapter.py
"""
Integration Adapter — Base adapter pattern for all external services.

Every external service integration (FCM, SendGrid, bKash, CPAlead, etc.)
must implement BaseAdapter. Provides:
  - Unified interface (send, receive, validate, transform)
  - Built-in retry with exponential backoff
  - Connection pooling hooks
  - Health check contract
  - Performance metrics collection
  - Circuit breaker pattern

Usage:
    class bKashAdapter(BaseAdapter):
        name = 'bkash'

        def _do_send(self, payload, **kwargs):
            # actual bKash API call
            return {'success': True, 'transaction_id': 'xxx'}

        def health_check(self):
            return HealthStatus.HEALTHY
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from .integ_constants import (
    HealthStatus, IntegStatus, RetryConfig, Timeouts
)
from .integ_exceptions import (
    IntegrationTimeout, RateLimitExceeded,
    ServiceUnavailable, FallbackFailed,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker State
# ---------------------------------------------------------------------------

class CircuitState:
    CLOSED   = 'closed'    # Normal operation
    OPEN     = 'open'      # Failing — block requests
    HALF_OPEN = 'half_open' # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    State machine:
      CLOSED → OPEN (after failure_threshold failures)
      OPEN → HALF_OPEN (after recovery_timeout seconds)
      HALF_OPEN → CLOSED (success) or OPEN (failure)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if self.last_failure_time and \
                   (timezone.now() - self.last_failure_time).seconds >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f'CircuitBreaker: → HALF_OPEN')
                    return True
                return False
            # HALF_OPEN: allow one test request
            return True

    def record_success(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info('CircuitBreaker: → CLOSED (recovered)')
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = timezone.now()
            self.success_count = 0
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    self.state = CircuitState.OPEN
                    logger.warning(
                        f'CircuitBreaker: → OPEN after {self.failure_count} failures'
                    )

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Base Adapter
# ---------------------------------------------------------------------------

class BaseAdapter(ABC):
    """
    Abstract base class for all external service adapters.

    Subclasses implement _do_send() and health_check().
    Everything else (retry, circuit breaker, metrics) is handled here.
    """

    name: str = 'base'
    timeout: int = Timeouts.HTTP_REQUEST
    max_retries: int = RetryConfig.MAX_RETRIES

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._circuit_breaker = CircuitBreaker()
        self._metrics: Dict[str, Any] = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'total_latency_ms': 0,
            'last_call_at': None,
        }
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self):
        """Override to set up connections, clients, etc."""
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, payload: Dict, **kwargs) -> Dict:
        """
        Send a request through this adapter with retry + circuit breaker.

        Returns:
            Dict with 'success', 'status', 'data', 'error', 'attempts'.
        """
        if not self._circuit_breaker.can_execute():
            raise ServiceUnavailable(self.name)

        attempts = 0
        last_error = ''

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            start_ms = time.monotonic() * 1000

            try:
                result = self._do_send(payload, **kwargs)
                latency = time.monotonic() * 1000 - start_ms

                self._record_success(latency)
                result['attempts'] = attempts
                result['latency_ms'] = round(latency, 2)
                return result

            except RateLimitExceeded as exc:
                self._record_failure(str(exc))
                logger.warning(f'{self.name}: rate limited on attempt {attempt}')
                retry_after = exc.details.get('retry_after', 60)
                if attempt < self.max_retries:
                    time.sleep(retry_after)
                last_error = str(exc)

            except IntegrationTimeout:
                self._record_failure('timeout')
                logger.warning(f'{self.name}: timeout on attempt {attempt}')
                last_error = 'timeout'
                if attempt < self.max_retries:
                    time.sleep(self._backoff_delay(attempt))

            except ServiceUnavailable:
                self._record_failure('service_unavailable')
                last_error = 'service_unavailable'
                break  # Don't retry unavailable service

            except Exception as exc:
                self._record_failure(str(exc))
                logger.error(f'{self.name}: error on attempt {attempt}: {exc}')
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(self._backoff_delay(attempt))

        return {
            'success': False,
            'status': IntegStatus.FAILED,
            'data': {},
            'error': last_error,
            'attempts': attempts,
        }

    def receive(self, data: Dict, **kwargs) -> Dict:
        """Process inbound data (webhooks, callbacks). Override as needed."""
        return self._do_receive(data, **kwargs)

    def validate(self, data: Dict, schema: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """Validate data against schema. Returns (is_valid, errors)."""
        return self._do_validate(data, schema)

    def transform(self, data: Dict, direction: str = 'outbound') -> Dict:
        """Transform data format. direction: 'outbound' | 'inbound'."""
        return self._do_transform(data, direction)

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Check if the external service is reachable. Return HealthStatus."""
        pass

    def is_available(self) -> bool:
        """Quick availability check."""
        try:
            status = self.health_check()
            return status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Override hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _do_send(self, payload: Dict, **kwargs) -> Dict:
        """Implement the actual send logic. Must return dict with 'success' key."""
        pass

    def _do_receive(self, data: Dict, **kwargs) -> Dict:
        """Override to implement inbound data processing."""
        return {'success': True, 'data': data}

    def _do_validate(self, data: Dict, schema: Optional[Dict]) -> Tuple[bool, List[str]]:
        """Override to implement validation logic."""
        return True, []

    def _do_transform(self, data: Dict, direction: str) -> Dict:
        """Override to implement data transformation."""
        return data

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _record_success(self, latency_ms: float):
        self._circuit_breaker.record_success()
        with self._lock:
            self._metrics['total_calls'] += 1
            self._metrics['successful_calls'] += 1
            self._metrics['total_latency_ms'] += latency_ms
            self._metrics['last_call_at'] = timezone.now().isoformat()

    def _record_failure(self, error: str):
        self._circuit_breaker.record_failure()
        with self._lock:
            self._metrics['total_calls'] += 1
            self._metrics['failed_calls'] += 1
            self._metrics['last_call_at'] = timezone.now().isoformat()

    def get_metrics(self) -> Dict:
        with self._lock:
            m = dict(self._metrics)
        total = m['total_calls'] or 1
        m['success_rate'] = round(m['successful_calls'] / total * 100, 2)
        m['avg_latency_ms'] = round(m['total_latency_ms'] / max(m['successful_calls'], 1), 2)
        m['circuit_state'] = self._circuit_breaker.state
        m['adapter'] = self.name
        return m

    @staticmethod
    def _backoff_delay(attempt: int) -> int:
        """Exponential backoff: 60s, 120s, 240s ... capped at 3600s."""
        import random
        base = RetryConfig.BASE_BACKOFF_SECONDS * (RetryConfig.BACKOFF_MULTIPLIER ** (attempt - 1))
        delay = min(base, RetryConfig.MAX_BACKOFF_SECONDS)
        jitter = random.uniform(0, delay * RetryConfig.JITTER_FACTOR)
        return int(delay + jitter)


# ---------------------------------------------------------------------------
# Notification Adapter (bridges notifications → integration system)
# ---------------------------------------------------------------------------

class NotificationIntegrationAdapter(BaseAdapter):
    """
    Adapter that connects the notifications app to the integration system.
    Allows other modules (wallet, tasks, etc.) to trigger notifications
    without direct imports.
    """

    name = 'notifications'

    def _do_send(self, payload: Dict, **kwargs) -> Dict:
        """
        payload keys:
            user_id        — target user PK
            notification_type — e.g. 'withdrawal_success'
            title          — notification title
            message        — notification body
            channel        — 'in_app' | 'push' | 'email' | 'sms' | 'all'
            priority       — 'low' | 'medium' | 'high' | 'critical'
            metadata       — dict of extra data
        """
        try:
            from django.contrib.auth import get_user_model
            from notifications.services import notification_service

            User = get_user_model()
            user = User.objects.get(pk=payload['user_id'])

            notification = notification_service.create_notification(
                user=user,
                title=payload.get('title', ''),
                message=payload.get('message', ''),
                notification_type=payload.get('notification_type', 'announcement'),
                channel=payload.get('channel', 'in_app'),
                priority=payload.get('priority', 'medium'),
                metadata=payload.get('metadata', {}),
            )

            if notification:
                success = notification_service.send_notification(notification)
                return {
                    'success': success,
                    'status': IntegStatus.SUCCESS if success else IntegStatus.FAILED,
                    'data': {'notification_id': notification.pk},
                    'error': '',
                }
            return {'success': False, 'status': IntegStatus.FAILED, 'data': {}, 'error': 'create failed'}

        except Exception as exc:
            raise ServiceUnavailable('notifications') from exc

    def health_check(self) -> HealthStatus:
        try:
            from notifications.models import Notification
            Notification.objects.first()
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY


class WalletIntegrationAdapter(BaseAdapter):
    """Bridges wallet module operations to the integration system."""

    name = 'wallet'

    def _do_send(self, payload: Dict, **kwargs) -> Dict:
        """
        payload keys: user_id, amount, transaction_type, description, metadata
        """
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=payload['user_id'])

            # Dynamic import to avoid hard coupling
            wallet_module = __import__('wallet.services', fromlist=['WalletService'])
            wallet_service = getattr(wallet_module, 'wallet_service', None)

            if not wallet_service:
                return {'success': False, 'status': IntegStatus.FAILED,
                        'data': {}, 'error': 'WalletService not available'}

            result = wallet_service.credit(
                user=user,
                amount=payload.get('amount', 0),
                transaction_type=payload.get('transaction_type', 'credit'),
                description=payload.get('description', ''),
                metadata=payload.get('metadata', {}),
            )
            return {
                'success': result.get('success', False),
                'status': IntegStatus.SUCCESS if result.get('success') else IntegStatus.FAILED,
                'data': result,
                'error': result.get('error', ''),
            }
        except Exception as exc:
            return {'success': False, 'status': IntegStatus.FAILED, 'data': {}, 'error': str(exc)}

    def health_check(self) -> HealthStatus:
        try:
            import importlib
            importlib.import_module('wallet.models')
            return HealthStatus.HEALTHY
        except ImportError:
            return HealthStatus.UNKNOWN
        except Exception:
            return HealthStatus.UNHEALTHY

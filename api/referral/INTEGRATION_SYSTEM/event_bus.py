# api/referral/INTEGRATION_SYSTEM/event_bus.py
# Lightweight pub/sub event bus for referral module
# Decouples referral from other modules — publish events, don't call directly
# ============================================================

import logging
import threading
from typing import Any, Callable, Dict, List, Optional
from .integ_constants import QUEUE_REFERRAL_HIGH, QUEUE_REFERRAL_NORMAL, QUEUE_REFERRAL_LOW
from .integ_exceptions import EventBusError

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class ReferralEventBus:
    """
    Lightweight in-process event bus.
    For high-traffic: delegates to Celery task queue.
    For low-traffic: runs handlers synchronously (or async via thread).

    Usage:
        bus = get_event_bus()
        bus.publish('task.completed', user=user, task=task, earned_amount=100)
        bus.subscribe('task.completed', my_handler)
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._middleware: List[Callable] = []
        self._dead_letter: List[dict] = []    # Failed events
        self._published_count = 0
        self._failed_count = 0

    # ── Subscribe ──────────────────────────────────────────────────────────

    def subscribe(self, event: str, handler: Callable, priority: int = 0) -> None:
        """Subscribe a handler to an event."""
        with _lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            # Priority ordering: higher priority runs first
            self._subscribers[event].append((priority, handler))
            self._subscribers[event].sort(key=lambda x: -x[0])

    def unsubscribe(self, event: str, handler: Callable) -> bool:
        """Unsubscribe a handler."""
        with _lock:
            if event not in self._subscribers:
                return False
            before = len(self._subscribers[event])
            self._subscribers[event] = [
                (p, h) for p, h in self._subscribers[event] if h != handler
            ]
            return len(self._subscribers[event]) < before

    def subscribe_once(self, event: str, handler: Callable) -> None:
        """Subscribe to event — handler runs once then unsubscribes."""
        def _once_wrapper(**kwargs):
            self.unsubscribe(event, _once_wrapper)
            return handler(**kwargs)
        self.subscribe(event, _once_wrapper)

    # ── Publish ───────────────────────────────────────────────────────────

    def publish(self, event: str, async_mode: bool = True, **kwargs) -> int:
        """
        Publish an event to all subscribers.
        async_mode=True → uses Celery if available, else thread.
        async_mode=False → synchronous (for tests/simple use).
        Returns count of handlers called.
        """
        handlers = self._get_handlers(event)
        if not handlers:
            return 0

        # Apply middleware
        for mw in self._middleware:
            try:
                kwargs = mw(event=event, **kwargs) or kwargs
            except Exception as e:
                logger.warning(f'[EventBus] Middleware error: {e}')

        self._published_count += 1
        called = 0

        if async_mode:
            called = self._dispatch_async(event, handlers, kwargs)
        else:
            called = self._dispatch_sync(event, handlers, kwargs)

        logger.debug(
            f'[EventBus] Published: {event} → {called}/{len(handlers)} handlers'
        )
        return called

    def publish_to_queue(
        self, event: str,
        queue: str = QUEUE_REFERRAL_NORMAL,
        **kwargs
    ) -> bool:
        """
        Publish event to Celery queue for high-traffic processing.
        Falls back to direct dispatch if Celery unavailable.
        """
        try:
            from api.referral.INTEGRATION_SYSTEM.message_queue import (
                ReferralMessageQueue
            )
            mq = ReferralMessageQueue()
            return mq.enqueue(event=event, queue=queue, **kwargs)
        except Exception:
            # Fallback to sync dispatch
            return self.publish(event, async_mode=False, **kwargs) > 0

    # ── Middleware ────────────────────────────────────────────────────────

    def add_middleware(self, middleware: Callable) -> None:
        """Add event middleware (runs before handlers)."""
        self._middleware.append(middleware)

    # ── Dead Letter ───────────────────────────────────────────────────────

    def get_dead_letters(self) -> List[dict]:
        """Get failed events for inspection."""
        return list(self._dead_letter)

    def retry_dead_letters(self) -> int:
        """Retry all failed events."""
        retried = 0
        for item in list(self._dead_letter):
            event = item['event']
            kwargs = item['kwargs']
            if self.publish(event, async_mode=False, **kwargs) > 0:
                self._dead_letter.remove(item)
                retried += 1
        return retried

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            'events_registered': len(self._subscribers),
            'total_subscribers': sum(len(v) for v in self._subscribers.values()),
            'published_count': self._published_count,
            'failed_count': self._failed_count,
            'dead_letters': len(self._dead_letter),
        }

    # ── Private ───────────────────────────────────────────────────────────

    def _get_handlers(self, event: str) -> List[Callable]:
        handlers = []
        # Exact match
        for _, h in self._subscribers.get(event, []):
            handlers.append(h)
        # Wildcard: 'task.*' matches 'task.completed'
        parts = event.split('.')
        for i in range(len(parts)):
            wildcard = '.'.join(parts[:i] + ['*'])
            for _, h in self._subscribers.get(wildcard, []):
                if h not in handlers:
                    handlers.append(h)
        return handlers

    def _dispatch_sync(self, event: str, handlers: List[Callable], kwargs: dict) -> int:
        called = 0
        for handler in handlers:
            try:
                handler(event=event, **kwargs)
                called += 1
            except Exception as e:
                self._failed_count += 1
                self._dead_letter.append({
                    'event': event,
                    'handler': handler.__name__,
                    'kwargs': kwargs,
                    'error': str(e),
                })
                logger.error(f'[EventBus] Handler error {handler.__name__}: {e}')
        return called

    def _dispatch_async(self, event: str, handlers: List[Callable], kwargs: dict) -> int:
        """Try Celery first, fallback to thread."""
        try:
            from api.referral.INTEGRATION_SYSTEM.message_queue import (
                ReferralMessageQueue
            )
            mq = ReferralMessageQueue()
            if mq.is_available():
                mq.enqueue_handlers(event=event, handlers=handlers, kwargs=kwargs)
                return len(handlers)
        except Exception:
            pass

        # Thread fallback
        def _run():
            self._dispatch_sync(event, handlers, kwargs)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return len(handlers)


# ── Built-in Middleware ───────────────────────────────────────────────────────

def logging_middleware(event: str, **kwargs) -> dict:
    """Log all events passing through the bus."""
    logger.debug(f'[EventBus] Event: {event} kwargs={list(kwargs.keys())}')
    return kwargs


def tenant_middleware(event: str, **kwargs) -> dict:
    """Inject tenant context into events."""
    user = kwargs.get('user')
    if user and not kwargs.get('tenant'):
        kwargs['tenant'] = getattr(user, 'tenant', None)
    return kwargs


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_event_bus(bus: 'ReferralEventBus') -> None:
    """
    Register all event → handler mappings.
    Called during app.ready() via integ_handler.py
    """
    from .integ_handler import (
        handle_task_completed, handle_offer_completed,
        handle_withdrawal_approved, handle_user_registered,
        handle_fraud_confirmed, handle_user_tier_upgraded,
    )
    from .integ_constants import (
        EVENT_TASK_COMPLETED, EVENT_OFFER_COMPLETED,
        EVENT_WITHDRAWAL_APPROVED, EVENT_USER_REGISTERED,
        EVENT_FRAUD_CONFIRMED, EVENT_USER_TIER_UPGRADED,
    )

    bus.add_middleware(logging_middleware)
    bus.add_middleware(tenant_middleware)

    bus.subscribe(EVENT_TASK_COMPLETED,      handle_task_completed,      priority=10)
    bus.subscribe(EVENT_OFFER_COMPLETED,     handle_offer_completed,     priority=10)
    bus.subscribe(EVENT_WITHDRAWAL_APPROVED, handle_withdrawal_approved, priority=5)
    bus.subscribe(EVENT_USER_REGISTERED,     handle_user_registered,     priority=10)
    bus.subscribe(EVENT_FRAUD_CONFIRMED,     handle_fraud_confirmed,     priority=10)
    bus.subscribe(EVENT_USER_TIER_UPGRADED,  handle_user_tier_upgraded,  priority=3)

    logger.info('[EventBus] Setup complete — 6 events registered')


# ── Global Singleton ──────────────────────────────────────────────────────────

_bus: Optional['ReferralEventBus'] = None


def get_event_bus() -> 'ReferralEventBus':
    global _bus
    if _bus is None:
        _bus = ReferralEventBus()
    return _bus
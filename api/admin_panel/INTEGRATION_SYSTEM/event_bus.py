# api/admin_panel/INTEGRATION_SYSTEM/event_bus.py
"""
EventBus — Async event distribution across all 50 apps.

Pub/Sub pattern for admin_panel events.
Supports in-process (sync), Celery (async), Redis Pub/Sub, and Channels (WebSocket).

Usage:
    from api.admin_panel.INTEGRATION_SYSTEM.event_bus import EventBus

    # Publish
    EventBus.publish('user.banned', payload={'user_id': 123}, async_mode=True)

    # Subscribe
    @EventBus.subscribe('wallet.withdrawal_requested')
    def on_withdrawal(event_type, payload, **kwargs):
        ...
"""
import json
import logging
from typing import Callable, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import INTEGRATION_EVENTS, TIMEOUTS, QUEUE_NAMES

logger = logging.getLogger(__name__)


class EventEnvelope:
    """Wraps an event with metadata for routing and tracing."""

    def __init__(self, event_type: str, payload: dict, source: str = 'admin_panel', correlation_id: str = ''):
        import uuid
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.correlation_id = correlation_id or self.event_id
        self.created_at = timezone.now()
        self.attempt = 0

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'payload': self.payload,
            'source': self.source,
            'correlation_id': self.correlation_id,
            'created_at': self.created_at.isoformat(),
            'attempt': self.attempt,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict) -> 'EventEnvelope':
        env = cls(
            event_type=data['event_type'],
            payload=data.get('payload', {}),
            source=data.get('source', ''),
            correlation_id=data.get('correlation_id', ''),
        )
        env.event_id = data.get('event_id', env.event_id)
        env.attempt = data.get('attempt', 0)
        return env


class EventBusMeta(type):
    _instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


class EventBus(metaclass=EventBusMeta):
    """
    Async event bus for the admin panel.
    Subscriptions are per-process (in-memory) + Celery for cross-process delivery.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._middleware: List[Callable] = []
        self._published_count = 0
        self._failed_count = 0

    # ==================== PUBLISH ====================

    def publish(
        self,
        event_type: str,
        payload: Optional[Dict] = None,
        source: str = 'admin_panel',
        async_mode: bool = False,
        correlation_id: str = '',
        priority: str = 'standard',
    ) -> str:
        """
        Publish an event.

        Args:
            event_type:     e.g. 'user.banned', 'wallet.credited'
            payload:        Event data
            source:         Which app is firing the event
            async_mode:     True = use Celery, False = synchronous
            correlation_id: Tracing ID
            priority:       'high' | 'standard' | 'bulk'

        Returns:
            event_id (str)
        """
        envelope = EventEnvelope(
            event_type=event_type,
            payload=payload or {},
            source=source,
            correlation_id=correlation_id,
        )

        logger.debug(f"[EventBus] Publish: {event_type} from={source} async={async_mode}")

        # Run middleware
        for mw in self._middleware:
            try:
                envelope = mw(envelope) or envelope
            except Exception as e:
                logger.warning(f"[EventBus] Middleware error: {e}")

        if async_mode:
            self._publish_async(envelope, priority)
        else:
            self._publish_sync(envelope)

        # Store in recent events cache
        self._record_event(envelope)
        self._published_count += 1
        return envelope.event_id

    def _publish_sync(self, envelope: EventEnvelope):
        """Deliver event synchronously to in-process subscribers."""
        handlers = self._subscribers.get(envelope.event_type, [])
        wildcard = self._subscribers.get('*', [])
        all_handlers = handlers + wildcard

        for handler in all_handlers:
            try:
                handler(event_type=envelope.event_type, payload=envelope.payload, envelope=envelope)
            except Exception as e:
                self._failed_count += 1
                logger.error(f"[EventBus] Handler error for {envelope.event_type}: {e}")

        # Also fire Django signal
        try:
            from .integ_signals import integration_event
            integration_event.send(
                sender=envelope.source,
                event_type=envelope.event_type,
                payload=envelope.payload,
            )
        except Exception as e:
            logger.debug(f"[EventBus] Signal fire failed: {e}")

    def _publish_async(self, envelope: EventEnvelope, priority: str = 'standard'):
        """Deliver event asynchronously via Celery."""
        try:
            from celery import current_app
            queue = {
                'high': QUEUE_NAMES['HIGH_PRIORITY'],
                'standard': QUEUE_NAMES['STANDARD'],
                'bulk': QUEUE_NAMES['BULK'],
            }.get(priority, QUEUE_NAMES['STANDARD'])

            current_app.send_task(
                'api.admin_panel.tasks.process_integration_event',
                args=[envelope.to_dict()],
                queue=queue,
            )
        except Exception as e:
            logger.warning(f"[EventBus] Celery async failed, falling back to sync: {e}")
            self._publish_sync(envelope)

    def _record_event(self, envelope: EventEnvelope):
        """Store recent events in cache for admin monitoring."""
        try:
            key = 'admin_panel:event_bus:recent'
            events = cache.get(key) or []
            events.insert(0, {
                'id': envelope.event_id,
                'type': envelope.event_type,
                'source': envelope.source,
                'ts': envelope.created_at.isoformat(),
            })
            cache.set(key, events[:200], TIMEOUTS['CACHE_TTL_MEDIUM'])
        except Exception:
            pass

    # ==================== SUBSCRIBE ====================

    def subscribe(self, event_type: str) -> Callable:
        """
        Decorator to subscribe a function to an event.

        @EventBus.subscribe('user.banned')
        def on_user_banned(event_type, payload, **kwargs):
            ...
        """
        def decorator(func: Callable) -> Callable:
            self._register_subscriber(event_type, func)
            return func
        return decorator

    def on(self, event_type: str, handler: Callable) -> None:
        """Register handler imperatively."""
        self._register_subscriber(event_type, handler)

    def off(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe a handler."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def _register_subscriber(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"[EventBus] Subscribed: {handler.__name__} to {event_type}")

    # ==================== MIDDLEWARE ====================

    def use(self, middleware_func: Callable) -> None:
        """Add middleware that transforms/validates events before delivery."""
        self._middleware.append(middleware_func)

    # ==================== MONITORING ====================

    def get_stats(self) -> Dict:
        return {
            'published': self._published_count,
            'failed': self._failed_count,
            'subscriber_count': sum(len(v) for v in self._subscribers.values()),
            'event_types_subscribed': list(self._subscribers.keys()),
        }

    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        events = cache.get('admin_panel:event_bus:recent') or []
        return events[:limit]

    def clear_subscribers(self, event_type: Optional[str] = None):
        if event_type:
            self._subscribers.pop(event_type, None)
        else:
            self._subscribers.clear()

    def __repr__(self) -> str:
        return f"<EventBus subscribers={len(self._subscribers)} published={self._published_count}>"


# Global singleton
event_bus = EventBus()

# ==================== BUILT-IN SUBSCRIBERS ====================

@event_bus.subscribe('user.banned')
def _auto_clear_user_cache(event_type, payload, **kwargs):
    """Auto-clear user cache on ban."""
    user_id = payload.get('user_id')
    if user_id:
        cache.delete(f'admin_panel:user_profile:{user_id}')
        cache.delete(f'fraud:user_risk:{user_id}')

@event_bus.subscribe('system.maintenance_started')
def _set_maintenance_cache(event_type, payload, **kwargs):
    cache.set('admin_panel:maintenance_mode_active', True, 86400)
    cache.set('admin_panel:maintenance_message', payload.get('message', ''), 86400)

@event_bus.subscribe('system.config_updated')
def _clear_config_cache(event_type, payload, **kwargs):
    key = payload.get('config_key')
    if key:
        cache.delete(f'admin_panel:config:{key}')
    cache.delete('admin_panel:config_all')

@event_bus.subscribe('wallet.withdrawal_approved')
def _update_payout_stats(event_type, payload, **kwargs):
    cache.delete('admin_panel:wallet_overview')
    cache.delete('admin_panel:system_kpis')
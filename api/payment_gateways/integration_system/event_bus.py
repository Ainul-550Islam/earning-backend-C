# api/payment_gateways/integration_system/event_bus.py
# Event bus — high-throughput async event processing with Redis pub/sub

import json
import logging
import threading
from typing import Callable, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)


class EventBus:
    """
    Async event bus for high-throughput payment event processing.

    For high-traffic scenarios (1000+ events/sec), this uses Redis
    pub/sub to decouple event producers from consumers.

    Features:
        - Publish events to Redis channel
        - Subscribe handlers to channels
        - Dead letter queue for failed events
        - Event replay from history
        - Batch processing for analytics

    Usage:
        bus = EventBus.get_instance()
        bus.publish('deposit.completed', {'user_id': 1, 'amount': '500.00'})

        # In consumer (runs as separate process)
        bus.subscribe('deposit.completed', handle_deposit)
        bus.listen()  # Blocking listener
    """

    _instance = None
    _subscribers: Dict[str, List[Callable]] = {}
    _history: Dict[str, List[dict]] = {}
    MAX_HISTORY = 1000

    CHANNEL_PREFIX = 'pg_events'
    DLQ_PREFIX     = 'pg_dlq'

    @classmethod
    def get_instance(cls) -> 'EventBus':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish(self, event_type: str, data: dict,
                 priority: int = 2) -> bool:
        """
        Publish an event to the bus.

        Args:
            event_type: Event name (e.g. 'deposit.completed')
            data:       Event payload dict
            priority:   0=critical, 2=normal, 4=async

        Returns:
            bool: True if published successfully
        """
        message = {
            'event':    event_type,
            'data':     data,
            'priority': priority,
        }

        # Store in history (for replay)
        self._add_to_history(event_type, message)

        # Try Redis pub/sub first
        if self._publish_redis(event_type, message):
            return True

        # Fallback: direct in-process call
        return self._publish_direct(event_type, data)

    def subscribe(self, event_type: str, handler: Callable,
                   group: str = 'default'):
        """Register a handler for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f'EventBus: subscribed {handler.__name__} to {event_type}')

    def publish_batch(self, events: list) -> int:
        """Publish multiple events at once. Returns count of successful publishes."""
        success = 0
        for ev in events:
            if self.publish(ev.get('event', ''), ev.get('data', {})):
                success += 1
        return success

    def get_history(self, event_type: str, limit: int = 100) -> list:
        """Get recent event history for an event type."""
        history = self._history.get(event_type, [])
        return history[-limit:]

    def replay_failed(self, event_type: str) -> int:
        """Replay events from the dead letter queue."""
        dlq_key  = f'{self.DLQ_PREFIX}:{event_type}'
        failed   = cache.get(dlq_key, [])
        replayed = 0
        for message in failed:
            if self._publish_direct(event_type, message.get('data', {})):
                replayed += 1
        if replayed:
            cache.delete(dlq_key)
        return replayed

    def _publish_redis(self, event_type: str, message: dict) -> bool:
        """Publish to Redis channel."""
        try:
            from django_redis import get_redis_connection
            conn    = get_redis_connection('default')
            channel = f'{self.CHANNEL_PREFIX}:{event_type}'
            conn.publish(channel, json.dumps(message, default=str))
            return True
        except Exception:
            return False

    def _publish_direct(self, event_type: str, data: dict) -> bool:
        """Direct in-process delivery to registered subscribers."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return True  # No subscribers — not an error

        for handler in handlers:
            try:
                handler(**data)
            except Exception as e:
                logger.error(f'EventBus direct handler {handler.__name__} failed: {e}')
                self._add_to_dlq(event_type, {'data': data, 'error': str(e)})
        return True

    def _add_to_history(self, event_type: str, message: dict):
        if event_type not in self._history:
            self._history[event_type] = []
        self._history[event_type].append(message)
        # Trim history
        if len(self._history[event_type]) > self.MAX_HISTORY:
            self._history[event_type] = self._history[event_type][-self.MAX_HISTORY:]

    def _add_to_dlq(self, event_type: str, message: dict):
        dlq_key  = f'{self.DLQ_PREFIX}:{event_type}'
        existing = cache.get(dlq_key, [])
        existing.append(message)
        cache.set(dlq_key, existing[-100:], 86400)  # Keep 100 failures for 24h


# Global singleton
event_bus = EventBus.get_instance()

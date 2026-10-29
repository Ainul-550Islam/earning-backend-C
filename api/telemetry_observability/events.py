"""
Internal event bus for Telemetry Observability.

WIRING:
  signals.py  → publish_event(EventType.METRIC_RECORDED, {...})
  hooks.py    → subscribes callbacks to EventBus on app startup
  webhooks.py → subscribes WebhookManager.dispatch() to ALERT_* events

Usage (producer side — e.g. signals.py):
    from .events import publish_event, EventType
    publish_event(EventType.ALERT_TRIGGERED, {'alert_id': instance.id})

Usage (consumer side — e.g. apps.py ready()):
    from .events import event_bus, EventType
    event_bus.subscribe(EventType.ALERT_TRIGGERED, my_callback)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types — mirrors Django signal set (but decoupled)
# ---------------------------------------------------------------------------

class EventType(Enum):
    """All event types emitted by the telemetry system."""
    METRIC_RECORDED      = 'metric_recorded'
    LOG_RECORDED         = 'log_recorded'
    TRACE_STARTED        = 'trace_started'
    TRACE_FINISHED       = 'trace_finished'
    ALERT_TRIGGERED      = 'alert_triggered'
    ALERT_ACKNOWLEDGED   = 'alert_acknowledged'
    ALERT_RESOLVED       = 'alert_resolved'
    HEALTH_STATUS_CHANGED = 'health_status_changed'
    DASHBOARD_UPDATED    = 'dashboard_updated'


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event:
    """Immutable value object representing a single emitted event."""

    __slots__ = ('event_type', 'data', 'timestamp', 'metadata')

    def __init__(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.data       = data
        self.timestamp  = timestamp or datetime.now(timezone.utc)
        self.metadata   = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'data':       self.data,
            'timestamp':  self.timestamp.isoformat(),
            'metadata':   self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def __repr__(self) -> str:
        return f'<Event {self.event_type.value} at {self.timestamp}>'


# ---------------------------------------------------------------------------
# EventBus — singleton
# ---------------------------------------------------------------------------

class EventBus:
    """
    Thread-safe singleton publish/subscribe event bus.

    Subscribers are called synchronously in the publish() call.
    Subscriber exceptions are caught and logged — they never break the bus.
    """

    _instance: Optional['EventBus'] = None

    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
            cls._instance = inst
        return cls._instance

    # -- subscription --

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Register callback for event_type. Duplicate registrations are ignored."""
        bucket = self._subscribers.setdefault(event_type, [])
        if callback not in bucket:
            bucket.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> bool:
        """Remove callback. Returns True if it was found."""
        bucket = self._subscribers.get(event_type, [])
        if callback in bucket:
            bucket.remove(callback)
            return True
        return False

    def reset(self) -> None:
        """Remove all subscribers. Useful in tests."""
        self._subscribers.clear()

    # -- publishing --

    def publish(self, event: Event) -> None:
        """
        Dispatch event to all registered subscribers.
        Subscriber exceptions are swallowed and logged.
        """
        for callback in list(self._subscribers.get(event.event_type, [])):
            try:
                callback(event)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    'EventBus subscriber %s raised for %s: %s',
                    callback.__qualname__, event.event_type.value, exc,
                )

    def get_subscriber_count(self, event_type: EventType) -> int:
        return len(self._subscribers.get(event_type, []))

    def __repr__(self) -> str:
        total = sum(len(v) for v in self._subscribers.values())
        return f'<EventBus subscribers={total}>'


# ---------------------------------------------------------------------------
# Module-level singleton + convenience helpers
# ---------------------------------------------------------------------------

event_bus = EventBus()


def publish_event(
    event_type: EventType,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Convenience helper — publish without constructing Event manually.

    Used in signals.py:
        publish_event(EventType.METRIC_RECORDED, {'metric_id': instance.pk})
    """
    event_bus.publish(Event(event_type, data, metadata=metadata))


def subscribe_to_event(
    event_type: EventType,
    callback: Callable[[Event], None],
) -> None:
    """
    Convenience helper — subscribe without accessing event_bus directly.

    Used in apps.py ready():
        subscribe_to_event(EventType.ALERT_TRIGGERED, notify_ops_team)
    """
    event_bus.subscribe(event_type, callback)

# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/event_bus.py
#
# Lightweight in-process event bus.  Subscribers register for EventType
# values; the bus dispatches Event objects to all matching handlers.
# For production, replace _dispatch with a Celery / Redis Pub-Sub call.
# =============================================================================
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import auto, Enum
from typing import Any, Callable, Dict, List

logger = logging.getLogger('fraud_detection.event_bus')


# ---------------------------------------------------------------------------
# EventType
# ---------------------------------------------------------------------------

class EventType(Enum):
    FRAUD_DETECTED          = auto()
    HIGH_RISK_SCORE         = auto()
    AUTO_BAN_TRIGGERED      = auto()
    AUTO_FLAG_TRIGGERED     = auto()
    CASE_OPENED             = auto()
    CASE_RESOLVED           = auto()
    CASE_ESCALATED          = auto()
    ALERT_CREATED           = auto()
    ALERT_RESOLVED          = auto()
    RULE_TRIGGERED          = auto()
    WHITELIST_UPDATED       = auto()
    RISK_PROFILE_UPDATED    = auto()
    DEVICE_FINGERPRINT_NEW  = auto()
    IP_BLACKLISTED          = auto()
    NOTIFICATION_SENT       = auto()
    INTEGRATION_HEALTH_CHANGE = auto()
    SYSTEM_ERROR            = auto()


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

@dataclass
class Event:
    event_type  : EventType
    payload     : Dict[str, Any] = field(default_factory=dict)
    source      : str            = 'fraud_detection'
    timestamp   : datetime       = field(default_factory=datetime.utcnow)
    correlation_id: str          = ''

    def to_dict(self) -> dict:
        return {
            'event_type':     self.event_type.name,
            'payload':        self.payload,
            'source':         self.source,
            'timestamp':      self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
        }


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

Handler = Callable[[Event], None]


class EventBus:
    """Thread-safe in-process publish / subscribe bus."""

    def __init__(self):
        self._lock:     threading.Lock              = threading.Lock()
        self._handlers: Dict[EventType, List[Handler]] = {}

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)
        logger.debug('Subscribed %s → %s', event_type.name, handler.__name__)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    'EventBus handler %s raised for %s: %s',
                    getattr(handler, '__name__', handler),
                    event.event_type.name,
                    exc,
                    exc_info=True,
                )

    def publish_async(self, event: Event) -> None:
        t = threading.Thread(target=self.publish, args=(event,), daemon=True)
        t.start()

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()

    def handler_count(self, event_type: EventType) -> int:
        return len(self._handlers.get(event_type, []))


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus

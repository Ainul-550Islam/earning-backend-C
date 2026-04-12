"""
events.py
──────────
Domain event definitions and event bus for Postback Engine.
Domain events are fired AFTER a state change has been committed to DB.
Unlike Django signals (sync), events can be dispatched async via Celery.

Event hierarchy:
  PostbackEvent
    ├── PostbackReceivedEvent
    ├── PostbackValidatedEvent
    ├── PostbackRejectedEvent
    ├── PostbackDuplicateEvent
    └── PostbackFailedEvent

  ConversionEvent
    ├── ConversionCreatedEvent
    ├── ConversionApprovedEvent
    ├── ConversionReversedEvent
    └── ConversionCreditedEvent

  FraudEvent
    ├── FraudDetectedEvent
    └── IPAutoBlockedEvent

  ClickEvent
    ├── ClickTrackedEvent
    └── ClickConvertedEvent
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Base Event ─────────────────────────────────────────────────────────────────

@dataclass
class BaseEvent:
    """Base domain event."""
    event_type: str = ""
    occurred_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": self.metadata,
        }


# ── Postback Events ────────────────────────────────────────────────────────────

@dataclass
class PostbackReceivedEvent(BaseEvent):
    event_type: str = "postback.received"
    raw_log_id: str = ""
    network_key: str = ""
    lead_id: str = ""
    source_ip: str = ""


@dataclass
class PostbackValidatedEvent(BaseEvent):
    event_type: str = "postback.validated"
    raw_log_id: str = ""
    network_key: str = ""


@dataclass
class PostbackRejectedEvent(BaseEvent):
    event_type: str = "postback.rejected"
    raw_log_id: str = ""
    network_key: str = ""
    rejection_reason: str = ""
    detail: str = ""


@dataclass
class PostbackDuplicateEvent(BaseEvent):
    event_type: str = "postback.duplicate"
    raw_log_id: str = ""
    network_key: str = ""
    lead_id: str = ""


@dataclass
class PostbackFailedEvent(BaseEvent):
    event_type: str = "postback.failed"
    raw_log_id: str = ""
    error: str = ""
    retry_count: int = 0


# ── Conversion Events ──────────────────────────────────────────────────────────

@dataclass
class ConversionCreatedEvent(BaseEvent):
    event_type: str = "conversion.created"
    conversion_id: str = ""
    user_id: str = ""
    offer_id: str = ""
    network_key: str = ""
    payout_usd: float = 0.0
    points_awarded: int = 0


@dataclass
class ConversionApprovedEvent(BaseEvent):
    event_type: str = "conversion.approved"
    conversion_id: str = ""
    user_id: str = ""


@dataclass
class ConversionReversedEvent(BaseEvent):
    event_type: str = "conversion.reversed"
    conversion_id: str = ""
    user_id: str = ""
    reason: str = ""
    amount_clawed_back: float = 0.0


@dataclass
class ConversionCreditedEvent(BaseEvent):
    event_type: str = "conversion.credited"
    conversion_id: str = ""
    user_id: str = ""
    wallet_transaction_id: str = ""
    amount_usd: float = 0.0
    points: int = 0


# ── Fraud Events ───────────────────────────────────────────────────────────────

@dataclass
class FraudDetectedEvent(BaseEvent):
    event_type: str = "fraud.detected"
    fraud_log_id: str = ""
    fraud_type: str = ""
    fraud_score: float = 0.0
    source_ip: str = ""
    network_key: str = ""
    auto_blocked: bool = False


@dataclass
class IPAutoBlockedEvent(BaseEvent):
    event_type: str = "fraud.ip_blocked"
    ip_address: str = ""
    reason: str = ""


# ── Click Events ───────────────────────────────────────────────────────────────

@dataclass
class ClickTrackedEvent(BaseEvent):
    event_type: str = "click.tracked"
    click_id: str = ""
    user_id: str = ""
    offer_id: str = ""
    network_key: str = ""
    ip_address: str = ""
    country: str = ""


@dataclass
class ClickConvertedEvent(BaseEvent):
    event_type: str = "click.converted"
    click_id: str = ""
    conversion_id: str = ""
    time_to_convert_seconds: int = 0


# ── Event Bus ──────────────────────────────────────────────────────────────────

class EventBus:
    """
    Simple synchronous event bus.
    Dispatches events to all registered handlers.
    For async dispatch, handlers can enqueue Celery tasks.
    """

    def __init__(self):
        self._handlers: Dict[str, List] = {}

    def subscribe(self, event_type: str, handler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: BaseEvent) -> None:
        """Publish an event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])
        handlers += self._handlers.get("*", [])  # wildcard handlers
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    "EventBus: handler %s failed for event %s: %s",
                    handler.__name__, event.event_type, exc,
                )

    def clear(self) -> None:
        """Clear all handlers (useful in tests)."""
        self._handlers.clear()


# Module-level event bus singleton
event_bus = EventBus()


# ── Event factory helpers ──────────────────────────────────────────────────────

def emit_postback_received(raw_log) -> None:
    event_bus.publish(PostbackReceivedEvent(
        raw_log_id=str(raw_log.id),
        network_key=raw_log.network.network_key if raw_log.network else "",
        lead_id=raw_log.lead_id or "",
        source_ip=raw_log.source_ip or "",
    ))


def emit_conversion_created(conversion) -> None:
    event_bus.publish(ConversionCreatedEvent(
        conversion_id=str(conversion.id),
        user_id=str(conversion.user_id),
        offer_id=conversion.offer_id or "",
        network_key=conversion.network.network_key if conversion.network else "",
        payout_usd=float(conversion.actual_payout),
        points_awarded=conversion.points_awarded,
    ))


def emit_fraud_detected(fraud_log) -> None:
    event_bus.publish(FraudDetectedEvent(
        fraud_log_id=str(fraud_log.id),
        fraud_type=fraud_log.fraud_type,
        fraud_score=fraud_log.fraud_score,
        source_ip=fraud_log.source_ip or "",
        network_key=fraud_log.network.network_key if fraud_log.network else "",
        auto_blocked=fraud_log.is_auto_blocked,
    ))

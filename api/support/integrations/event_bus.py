# api/support/integrations/event_bus.py  — WORLD #1
"""
Event Bus — support system-এর internal pub/sub system।
Ticket events fire → handlers execute → other apps react.
Thread-safe, async-compatible, with Celery fallback.
"""
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone

from .integ_constants import *

logger = logging.getLogger(__name__)


class SupportEventBus:
    """
    Async-capable event bus for support system.
    
    Publish:
        bus.publish('support.ticket.created', ticket=ticket, user=user)
    
    Subscribe:
        @bus.on('support.ticket.created')
        def handle_new_ticket(event_type, ticket, user, **kwargs):
            ...
    """
    _lock = threading.Lock()

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._wildcard: List[Callable]             = []   # handlers that receive ALL events
        self._history:  List[dict]                 = []   # last 100 events for debugging
        self._history_max                          = 100

    # ── Subscribe ─────────────────────────────────────────
    def on(self, event_type: str):
        """Decorator to register event handler."""
        def decorator(func: Callable) -> Callable:
            self.subscribe(event_type, func)
            return func
        return decorator

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe a handler to an event type."""
        with self._lock:
            if event_type == '*':
                self._wildcard.append(handler)
            else:
                self._handlers[event_type].append(handler)
        logger.debug(f'EventBus: handler subscribed to {event_type}')

    def subscribe_all(self, handler: Callable) -> None:
        """Subscribe to all events (wildcard)."""
        self.subscribe('*', handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler."""
        with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]

    # ── Publish ───────────────────────────────────────────
    def publish(self, event_type: str, async_mode: bool = False, **data) -> List[Any]:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Event identifier (e.g. 'support.ticket.created')
            async_mode: If True, run via Celery (non-blocking)
            **data:     Event payload
        
        Returns: List of handler results (sync mode only)
        """
        event = {
            'type':       event_type,
            'data':       data,
            'timestamp':  timezone.now().isoformat(),
        }

        # Record to history
        self._add_to_history(event)

        if async_mode:
            self._publish_async(event_type, data)
            return []

        return self._publish_sync(event_type, data)

    def _publish_sync(self, event_type: str, data: dict) -> List[Any]:
        """Synchronous publish — blocks until all handlers complete."""
        results  = []
        handlers = self._handlers.get(event_type, []) + self._wildcard

        for handler in handlers:
            try:
                result = handler(event_type=event_type, **data)
                results.append(result)
            except Exception as e:
                logger.error(f'EventBus handler error [{event_type}] in {handler.__name__}: {e}')

        if handlers:
            logger.debug(f'EventBus: {event_type} dispatched to {len(handlers)} handlers')
        return results

    def _publish_async(self, event_type: str, data: dict) -> None:
        """Async publish via Celery if available, else sync fallback."""
        try:
            from .message_queue import message_queue
            message_queue.enqueue(event_type, data)
        except Exception:
            # Celery unavailable — sync fallback
            self._publish_sync(event_type, data)

    def _add_to_history(self, event: dict) -> None:
        """Keep last N events for debugging."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history.pop(0)

    # ── Query ─────────────────────────────────────────────
    def get_recent_events(self, event_type: str = None, limit: int = 10) -> list:
        """Get recent events from history."""
        events = self._history[-limit:]
        if event_type:
            events = [e for e in events if e['type'] == event_type]
        return list(reversed(events))

    def get_handler_count(self, event_type: str) -> int:
        """Get number of handlers for an event."""
        return len(self._handlers.get(event_type, []))

    def list_subscriptions(self) -> dict:
        """List all registered event subscriptions."""
        return {
            event: [h.__name__ for h in handlers]
            for event, handlers in self._handlers.items()
        }


# ── Singleton ─────────────────────────────────────────
event_bus = SupportEventBus()


# ── Pre-registered handlers ────────────────────────────
@event_bus.on(EVT_TICKET_CREATED)
def on_ticket_created(event_type, ticket=None, **kwargs):
    """When ticket created: notify, setup SLA, check fraud, track analytics."""
    if not ticket:
        return
    try:
        from .integ_adapter import notifications_adapter, analytics_adapter, fraud_adapter
        # 1. Notify user
        notifications_adapter.send_ticket_event(ticket, EVT_TICKET_CREATED)
        # 2. Check fraud risk (log only — don't block creation)
        risk = fraud_adapter.get_risk_score(ticket.user)
        if risk.get('is_critical'):
            logger.warning(f'Critical risk user {ticket.user.id} created ticket {ticket.ticket_id}')
        # 3. Track analytics
        analytics_adapter.track_support_event('ticket_created', ticket=ticket)
    except Exception as e:
        logger.error(f'on_ticket_created handler failed: {e}')


@event_bus.on(EVT_TICKET_RESOLVED)
def on_ticket_resolved(event_type, ticket=None, **kwargs):
    """When ticket resolved: notify user, schedule CSAT, track."""
    if not ticket:
        return
    try:
        from .integ_adapter import notifications_adapter, analytics_adapter
        notifications_adapter.send_ticket_event(ticket, EVT_TICKET_RESOLVED)
        analytics_adapter.track_support_event('ticket_resolved', ticket=ticket)
    except Exception as e:
        logger.error(f'on_ticket_resolved handler failed: {e}')


@event_bus.on(EVT_OFFER_DISPUTE_APPROVED)
def on_offer_dispute_approved(event_type, dispute=None, ticket=None, **kwargs):
    """When offer dispute approved: credit wallet, notify user."""
    if not dispute:
        return
    try:
        from .integ_adapter import wallet_adapter, notifications_adapter
        from decimal import Decimal
        # Credit wallet
        ticket_id = ticket.ticket_id if ticket else ''
        ok = wallet_adapter.credit(
            dispute.user,
            Decimal(str(dispute.expected_amount)),
            f'Offer dispute approved: {dispute.offer_id}',
            ticket_id=ticket_id,
        )
        if ok:
            notifications_adapter.send(
                dispute.user,
                f'Dispute Approved — {dispute.expected_amount} Credits Added!',
                f'Your offer dispute for "{dispute.offer_name or dispute.offer_id}" '
                f'has been approved. {dispute.expected_amount} credits have been added.',
                data={'type': 'dispute_approved', 'offer_id': dispute.offer_id},
            )
    except Exception as e:
        logger.error(f'on_offer_dispute_approved handler failed: {e}')


@event_bus.on(EVT_TICKET_SLA_BREACH)
def on_sla_breach(event_type, ticket=None, breach_type: str = '', **kwargs):
    """When SLA breaches: escalate ticket, notify assigned agent."""
    if not ticket:
        return
    try:
        from .integ_adapter import analytics_adapter
        analytics_adapter.track_support_event(
            'sla_breach',
            ticket=ticket,
            breach_type=breach_type,
        )
    except Exception as e:
        logger.error(f'on_sla_breach handler failed: {e}')
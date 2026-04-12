# api/publisher_tools/events.py
"""Publisher Tools — Event system. Business events publish ও subscribe।"""
import logging
from typing import Callable, Dict, List
from django.dispatch import Signal
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Django Signals (Custom Events) ────────────────────────────────────────────
publisher_approved      = Signal()
publisher_suspended     = Signal()
publisher_tier_changed  = Signal()
site_verified           = Signal()
site_approved           = Signal()
site_rejected           = Signal()
app_approved            = Signal()
app_rejected            = Signal()
ad_unit_created         = Signal()
earning_finalized       = Signal()
invoice_paid            = Signal()
invoice_generated       = Signal()
payout_requested        = Signal()
fraud_detected          = Signal()
quality_alert_raised    = Signal()
ab_test_winner_declared = Signal()
revenue_milestone_reached = Signal()

# ── Event Bus (in-memory pub/sub) ─────────────────────────────────────────────
_event_handlers: Dict[str, List[Callable]] = {}


def subscribe(event_name: str, handler: Callable):
    """Event subscribe করে।"""
    if event_name not in _event_handlers:
        _event_handlers[event_name] = []
    _event_handlers[event_name].append(handler)


def publish(event_name: str, **data):
    """Event publish করে — সব subscribers notify হয়।"""
    handlers = _event_handlers.get(event_name, [])
    for handler in handlers:
        try:
            handler(event_name=event_name, timestamp=timezone.now(), **data)
        except Exception as e:
            logger.error(f'Event handler error [{event_name}]: {e}')


# ── Standard Event Publishers ──────────────────────────────────────────────────
def emit_publisher_approved(publisher):
    publisher_approved.send(sender=publisher.__class__, publisher=publisher)
    publish('publisher.approved', publisher_id=publisher.publisher_id)
    from .webhooks.webhook_manager import send_webhook_event
    send_webhook_event(publisher, 'publisher.approved', {'publisher_id': publisher.publisher_id, 'tier': publisher.tier})


def emit_publisher_suspended(publisher, reason: str = ''):
    publisher_suspended.send(sender=publisher.__class__, publisher=publisher, reason=reason)
    publish('publisher.suspended', publisher_id=publisher.publisher_id, reason=reason)
    from .webhooks.webhook_manager import send_webhook_event
    send_webhook_event(publisher, 'publisher.suspended', {'publisher_id': publisher.publisher_id, 'reason': reason})


def emit_invoice_paid(invoice):
    invoice_paid.send(sender=invoice.__class__, invoice=invoice)
    publish('invoice.paid', invoice_number=invoice.invoice_number, amount=float(invoice.net_payable))
    from .webhooks.webhook_manager import send_webhook_event, build_invoice_event_payload
    send_webhook_event(invoice.publisher, 'invoice.paid', build_invoice_event_payload(invoice))


def emit_fraud_detected(log):
    fraud_detected.send(sender=log.__class__, log=log)
    publish('fraud.detected', publisher_id=log.publisher.publisher_id, score=log.fraud_score, type=log.traffic_type)
    if log.severity in ('high', 'critical'):
        from .webhooks.webhook_manager import send_webhook_event
        send_webhook_event(log.publisher, 'fraud.high_risk_detected', {
            'traffic_type': log.traffic_type, 'fraud_score': log.fraud_score, 'severity': log.severity,
        })


def emit_site_verified(site):
    site_verified.send(sender=site.__class__, site=site)
    publish('site.verified', site_id=site.site_id, domain=site.domain)


def emit_revenue_milestone(publisher, milestone_amount: float):
    revenue_milestone_reached.send(sender=publisher.__class__, publisher=publisher, milestone=milestone_amount)
    publish('revenue.milestone', publisher_id=publisher.publisher_id, milestone=milestone_amount)
    from .webhooks.webhook_manager import send_webhook_event
    send_webhook_event(publisher, 'performance.milestone', {'milestone_amount': milestone_amount, 'total_revenue': float(publisher.total_revenue)})


def emit_ab_test_winner(test, variant):
    ab_test_winner_declared.send(sender=test.__class__, test=test, winner=variant)
    publish('ab_test.winner', test_id=test.test_id, winner_id=str(variant.id))
    from .webhooks.webhook_manager import send_webhook_event
    send_webhook_event(test.publisher, 'ab_test.winner_declared', {'test_id': test.test_id, 'winner_variant': variant.name})

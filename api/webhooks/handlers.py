# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
api/webhooks/handlers.py

Named handler functions for InboundWebhookRoute.handler_function.

InboundEventRouter._get_handler_function() resolves a route's bare
handler_function name (e.g. "handle_payment_intent") against this module.
Add new handlers here and reference them by name (no dotted path needed)
when configuring an InboundWebhookRoute.

Each handler receives:
    payload:    dict  - the inbound webhook payload
    headers:    dict  - HTTP headers from the inbound request
    route_id:   str   - the InboundWebhookRoute id that matched
    log_id:     str   - the InboundWebhookLog id for this delivery
    inbound_id: str   - the InboundWebhook (source config) id

These are intentionally thin: real business logic (crediting a wallet,
flagging fraud, etc.) lives in the owning app (payment_gateways, wallet,
fraud_detection, ...) and should be called from here once those apps are
available in this deployment - see HANDOFF_NEXT_CHAT.md.
"""
import logging

logger = logging.getLogger("ainul.webhooks.handlers")


def handle_payment_intent(payload=None, headers=None, route_id=None, log_id=None, inbound_id=None, **kwargs):
    """Handle a `payment_intent.*` inbound event (e.g. Stripe-style gateways)."""
    logger.info(
        "handle_payment_intent: route=%s log=%s inbound=%s",
        route_id, log_id, inbound_id,
    )
    return True


def handle_payment(payload=None, headers=None, route_id=None, log_id=None, inbound_id=None, **kwargs):
    """Handle a generic `payment.*` inbound event."""
    logger.info(
        "handle_payment: route=%s log=%s inbound=%s",
        route_id, log_id, inbound_id,
    )
    return True

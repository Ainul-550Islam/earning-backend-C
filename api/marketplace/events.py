"""
marketplace/events.py — Domain Events (publish/subscribe)
==========================================================
Simple in-process event bus. Plug in Celery or Redis pub/sub
by replacing _dispatch() implementation.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_handlers: Dict[str, List[Callable]] = {}


def on(event_name: str):
    """Decorator — register a handler for an event."""
    def decorator(fn: Callable):
        _handlers.setdefault(event_name, []).append(fn)
        return fn
    return decorator


def emit(event_name: str, **payload):
    """Emit an event and call all registered handlers."""
    handlers = _handlers.get(event_name, [])
    for handler in handlers:
        try:
            handler(**payload)
        except Exception as e:
            logger.error("[marketplace:events] Handler %s failed for %s: %s", handler, event_name, e)


# ── Built-in events ───────────────────────────────────────────
ORDER_PLACED       = "marketplace.order.placed"
ORDER_CONFIRMED    = "marketplace.order.confirmed"
ORDER_SHIPPED      = "marketplace.order.shipped"
ORDER_DELIVERED    = "marketplace.order.delivered"
ORDER_CANCELLED    = "marketplace.order.cancelled"
PAYMENT_SUCCESS    = "marketplace.payment.success"
PAYMENT_FAILED     = "marketplace.payment.failed"
REFUND_REQUESTED   = "marketplace.refund.requested"
REFUND_APPROVED    = "marketplace.refund.approved"
ESCROW_RELEASED    = "marketplace.escrow.released"
SELLER_VERIFIED    = "marketplace.seller.verified"
REVIEW_POSTED      = "marketplace.review.posted"
LOW_STOCK          = "marketplace.inventory.low_stock"


# ── Example built-in handlers ─────────────────────────────────
@on(ORDER_PLACED)
def _log_order_placed(order=None, **_):
    if order:
        logger.info("[marketplace] Order placed: %s", order.order_number)


@on(SELLER_VERIFIED)
def _log_seller_verified(seller=None, **_):
    if seller:
        logger.info("[marketplace] Seller verified: %s", seller.store_name)

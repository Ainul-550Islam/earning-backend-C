"""
WEBHOOKS/event_dispatcher.py — Event → Webhook Bridge
"""
import logging
from api.marketplace.events import on, ORDER_PLACED, ORDER_DELIVERED, ORDER_CONFIRMED
from api.marketplace.events import ORDER_SHIPPED, ORDER_CANCELLED, PAYMENT_SUCCESS
from api.marketplace.events import REFUND_REQUESTED, SELLER_VERIFIED, REVIEW_POSTED
from .order_webhook import fire_order_event
from .seller_webhook import fire_seller_event

logger = logging.getLogger(__name__)


@on(ORDER_PLACED)
def _on_order_placed(order=None, **_):
    if order:
        fire_order_event(order.tenant, "order.placed", order)
        logger.debug("[Dispatcher] order.placed → %s", order.order_number)


@on(ORDER_CONFIRMED)
def _on_order_confirmed(order=None, **_):
    if order:
        fire_order_event(order.tenant, "order.confirmed", order)


@on(ORDER_SHIPPED)
def _on_order_shipped(order=None, **_):
    if order:
        fire_order_event(order.tenant, "order.shipped", order)


@on(ORDER_DELIVERED)
def _on_order_delivered(order=None, **_):
    if order:
        fire_order_event(order.tenant, "order.delivered", order)


@on(ORDER_CANCELLED)
def _on_order_cancelled(order=None, **_):
    if order:
        fire_order_event(order.tenant, "order.cancelled", order)


@on(PAYMENT_SUCCESS)
def _on_payment_success(order=None, transaction=None, **_):
    if order:
        from .payment_webhook import fire_payment_event
        try:
            fire_payment_event(order.tenant, "payment.success", order, transaction)
        except Exception as e:
            logger.error("[Dispatcher] payment.success error: %s", e)


@on(SELLER_VERIFIED)
def _on_seller_verified(seller=None, **_):
    if seller:
        fire_seller_event(seller.tenant, "seller.verified", seller)


@on(REFUND_REQUESTED)
def _on_refund_requested(dispute=None, **_):
    if dispute:
        from .shipping_webhook import fire_refund_event
        try:
            fire_refund_event(dispute.tenant, "refund.requested", dispute)
        except Exception as e:
            logger.error("[Dispatcher] refund.requested error: %s", e)

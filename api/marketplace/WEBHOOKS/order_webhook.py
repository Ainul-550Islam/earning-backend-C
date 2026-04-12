"""
WEBHOOKS/order_webhook.py — Order event webhooks
"""
from .webhook_manager import WebhookDispatcher


ORDER_EVENTS = {
    "order.placed":    "Fired when a new order is created",
    "order.confirmed": "Fired when seller confirms the order",
    "order.shipped":   "Fired when order is shipped",
    "order.delivered": "Fired when order is marked delivered",
    "order.cancelled": "Fired when order is cancelled",
}


def fire_order_event(tenant, event: str, order):
    if not hasattr(tenant, "webhook_url") or not tenant.webhook_url:
        return
    dispatcher = WebhookDispatcher(secret=str(tenant.api_key))
    data = {
        "order_number": order.order_number,
        "status": order.status,
        "total": str(order.total_price),
        "user_id": order.user_id,
    }
    dispatcher.dispatch(tenant.webhook_url, event, data)

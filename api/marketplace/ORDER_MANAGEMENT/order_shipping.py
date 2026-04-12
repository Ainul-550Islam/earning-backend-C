"""ORDER_MANAGEMENT/order_shipping.py — Shipping Assignment for Orders"""
from api.marketplace.models import Order, OrderTracking
from api.marketplace.enums import TrackingEvent


def assign_courier(order: Order, courier_name: str, tracking_number: str,
                   assigned_by=None) -> OrderTracking:
    """Assign a courier to an order and add tracking event."""
    order.status = "shipped"
    order.save(update_fields=["status"])
    return OrderTracking.objects.create(
        tenant=order.tenant, order=order,
        event=TrackingEvent.PICKED_UP,
        description=f"Picked up by {courier_name}",
        courier_name=courier_name,
        tracking_number=tracking_number,
        created_by=assigned_by,
    )


def get_shipping_info(order: Order) -> dict:
    last_tracking = order.tracking_events.order_by("-occurred_at").first()
    return {
        "shipping_name": order.shipping_name,
        "shipping_phone": order.shipping_phone,
        "address": order.shipping_address,
        "city": order.shipping_city,
        "courier": last_tracking.courier_name if last_tracking else "",
        "tracking_number": last_tracking.tracking_number if last_tracking else "",
        "last_status": last_tracking.event if last_tracking else "pending",
    }

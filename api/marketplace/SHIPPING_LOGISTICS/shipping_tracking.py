"""
SHIPPING_LOGISTICS/shipping_tracking.py — Real-Time Shipment Tracking
"""
from api.marketplace.models import Order, OrderTracking
from api.marketplace.enums import TrackingEvent
import logging

logger = logging.getLogger(__name__)


def get_order_tracking_timeline(order: Order) -> list:
    events = order.tracking_events.order_by("occurred_at")
    return [
        {
            "event":          e.event,
            "description":    e.description,
            "location":       e.location,
            "courier":        e.courier_name,
            "tracking_number":e.tracking_number,
            "time":           e.occurred_at.isoformat(),
        }
        for e in events
    ]


def sync_courier_tracking(order: Order) -> dict:
    """Pull latest tracking from courier API and update OrderTracking."""
    last_event = order.tracking_events.order_by("-occurred_at").first()
    courier    = last_event.courier_name if last_event else ""
    tracking   = last_event.tracking_number if last_event else ""
    if not courier or not tracking:
        return {"synced": False, "reason": "no courier info"}
    status = get_live_status(courier, tracking)
    if status.get("status") != "error":
        OrderTracking.objects.get_or_create(
            order=order, event=TrackingEvent.IN_TRANSIT,
            defaults={
                "tenant": order.tenant,
                "description": status.get("message", "In transit"),
                "courier_name": courier,
                "tracking_number": tracking,
            }
        )
    return status


def get_live_status(courier: str, tracking_number: str) -> dict:
    try:
        from api.marketplace.SHIPPING_LOGISTICS.courier_integration import get_live_tracking
        return get_live_tracking(courier, tracking_number)
    except Exception as e:
        logger.error("[TrackingSync] %s: %s", tracking_number, e)
        return {"status": "error", "message": str(e)}

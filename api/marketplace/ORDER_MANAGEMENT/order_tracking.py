"""
ORDER_MANAGEMENT/order_tracking.py — Order Tracking Event Management
"""
from django.utils import timezone
from api.marketplace.models import Order, OrderTracking
from api.marketplace.enums import TrackingEvent, OrderStatus


TRACKING_STATUS_LABELS = {
    TrackingEvent.ORDER_PLACED:       "Order Placed",
    TrackingEvent.PAYMENT_CONFIRMED:  "Payment Confirmed",
    TrackingEvent.SELLER_CONFIRMED:   "Seller Confirmed",
    TrackingEvent.PACKED:             "Order Packed",
    TrackingEvent.PICKED_UP:          "Picked Up by Courier",
    TrackingEvent.IN_TRANSIT:         "In Transit",
    TrackingEvent.OUT_FOR_DELIVERY:   "Out for Delivery",
    TrackingEvent.DELIVERED:          "Delivered",
    TrackingEvent.DELIVERY_FAILED:    "Delivery Failed",
    TrackingEvent.RETURN_INITIATED:   "Return Initiated",
    TrackingEvent.RETURNED:           "Returned to Seller",
}


def add_tracking_event(order: Order, event: str, description: str = "",
                       courier: str = "", tracking_number: str = "",
                       location: str = "", created_by=None) -> OrderTracking:
    """Add a new tracking event to an order."""
    return OrderTracking.objects.create(
        tenant=order.tenant, order=order, event=event,
        description=description or TRACKING_STATUS_LABELS.get(event, event),
        location=location, courier_name=courier, tracking_number=tracking_number,
        occurred_at=timezone.now(), created_by=created_by,
    )


def latest_status(order: Order) -> dict:
    last = order.tracking_events.order_by("-occurred_at").first()
    if not last:
        return {"event": TrackingEvent.ORDER_PLACED, "label": "Order Placed", "time": None}
    return {
        "event":    last.event,
        "label":    TRACKING_STATUS_LABELS.get(last.event, last.event),
        "time":     last.occurred_at.isoformat(),
        "location": last.location,
        "courier":  last.courier_name,
        "tracking": last.tracking_number,
    }


def get_full_timeline(order: Order) -> list:
    events = order.tracking_events.order_by("occurred_at")
    return [
        {
            "event":       e.event,
            "label":       TRACKING_STATUS_LABELS.get(e.event, e.event),
            "description": e.description,
            "location":    e.location,
            "courier":     e.courier_name,
            "tracking_no": e.tracking_number,
            "time":        e.occurred_at.strftime("%Y-%m-%d %H:%M"),
        }
        for e in events
    ]


def update_tracking_from_courier(order: Order, courier_status: str, tracking_no: str,
                                  courier_name: str = "", location: str = "") -> OrderTracking:
    """Map courier API status to internal tracking event."""
    courier_to_event = {
        "picked_up":        TrackingEvent.PICKED_UP,
        "in_transit":       TrackingEvent.IN_TRANSIT,
        "out_for_delivery": TrackingEvent.OUT_FOR_DELIVERY,
        "delivered":        TrackingEvent.DELIVERED,
        "failed":           TrackingEvent.DELIVERY_FAILED,
        "returned":         TrackingEvent.RETURNED,
    }
    event = courier_to_event.get(courier_status.lower(), TrackingEvent.IN_TRANSIT)
    return add_tracking_event(
        order, event,
        description=f"Courier update: {courier_status}",
        courier=courier_name, tracking_number=tracking_no,
        location=location,
    )


def expected_delivery_date(order: Order) -> str:
    """Estimate delivery date based on zone and ship date."""
    from api.marketplace.SHIPPING_LOGISTICS.shipping_zone import get_zone_for_city
    zone     = get_zone_for_city(order.shipping_city)
    ship_evt = order.tracking_events.filter(event=TrackingEvent.PICKED_UP).first()
    if not ship_evt:
        return "Pending shipment"
    days_map = {"inside_dhaka": 1, "divisional": 2, "outside_dhaka": 3, "remote": 6}
    days     = days_map.get(zone, 3)
    eta      = ship_evt.occurred_at + timezone.timedelta(days=days)
    return eta.strftime("%d %B %Y")

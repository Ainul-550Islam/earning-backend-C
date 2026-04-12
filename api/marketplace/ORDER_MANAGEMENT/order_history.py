"""ORDER_MANAGEMENT/order_history.py — Order History & Timeline"""
from api.marketplace.models import Order, OrderTracking
from api.marketplace.enums import OrderStatus


def get_order_history(user, tenant, limit=50) -> list:
    orders = (
        Order.objects.filter(user=user, tenant=tenant)
        .prefetch_related("items", "tracking_events")
        .order_by("-created_at")[:limit]
    )
    return [
        {
            "order_number": o.order_number,
            "status": o.status,
            "total": str(o.total_price),
            "items": o.items.count(),
            "date": o.created_at.strftime("%Y-%m-%d"),
            "last_event": o.tracking_events.order_by("-occurred_at").values_list("event", flat=True).first(),
        }
        for o in orders
    ]


def get_full_timeline(order: Order) -> list:
    return [
        {
            "event": t.event,
            "description": t.description,
            "location": t.location,
            "time": t.occurred_at.isoformat(),
        }
        for t in order.tracking_events.order_by("occurred_at")
    ]

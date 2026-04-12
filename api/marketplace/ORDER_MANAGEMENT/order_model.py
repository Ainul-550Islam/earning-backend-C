"""order_model.py — Order helpers"""
from api.marketplace.models import Order
from api.marketplace.enums import OrderStatus


def get_user_orders(user, tenant, status=None):
    qs = Order.objects.filter(user=user, tenant=tenant)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-created_at")


def get_order_summary(order: Order) -> dict:
    return {
        "order_number": order.order_number,
        "status": order.status,
        "total_price": str(order.total_price),
        "item_count": order.items.count(),
        "is_paid": order.is_paid,
        "created_at": order.created_at.isoformat(),
    }

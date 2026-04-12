"""
DATABASE_MODELS/order_table.py — Order Table Reference & Queries
"""
from api.marketplace.models import Order, OrderItem, OrderTracking
from api.marketplace.enums import OrderStatus
from django.db.models import Sum, Count, Q
from django.utils import timezone


def get_order_by_number(order_number: str, tenant=None) -> Order:
    qs = Order.objects.prefetch_related("items","tracking_events").select_related("user")
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.get(order_number=order_number)


def orders_by_status(tenant, status: str) -> list:
    return list(
        Order.objects.filter(tenant=tenant, status=status)
        .select_related("user")
        .order_by("-created_at")
    )


def today_orders(tenant) -> dict:
    today = timezone.now().date()
    qs    = Order.objects.filter(tenant=tenant, created_at__date=today)
    agg   = qs.aggregate(count=Count("id"), revenue=Sum("total_price"))
    return {"count": agg["count"] or 0, "revenue": str(agg["revenue"] or 0)}


def fulfillment_rate(tenant, days: int = 30) -> float:
    since   = timezone.now() - timezone.timedelta(days=days)
    total   = Order.objects.filter(tenant=tenant, created_at__gte=since).count()
    delivered = Order.objects.filter(tenant=tenant, created_at__gte=since, status=OrderStatus.DELIVERED).count()
    return round(delivered / total * 100, 1) if total else 0


def orders_needing_action(tenant) -> dict:
    return {
        "pending_confirmation": Order.objects.filter(tenant=tenant, status=OrderStatus.PENDING).count(),
        "overdue_shipping":     Order.objects.filter(
            tenant=tenant, status=OrderStatus.CONFIRMED,
            created_at__lt=timezone.now() - timezone.timedelta(hours=48)
        ).count(),
    }


__all__ = [
    "Order","OrderItem","OrderTracking",
    "get_order_by_number","orders_by_status","today_orders",
    "fulfillment_rate","orders_needing_action",
]

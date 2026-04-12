"""
MARKETPLACE_ANALYTICS/buyer_analytics.py — Buyer Behaviour Analytics
"""
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone


def buyer_overview(tenant, days: int = 30) -> dict:
    from api.marketplace.models import Order
    from api.marketplace.enums import OrderStatus
    since = timezone.now() - timezone.timedelta(days=days)
    orders = Order.objects.filter(tenant=tenant, created_at__gte=since)
    agg = orders.aggregate(
        total_buyers=Count("user", distinct=True),
        total_orders=Count("id"),
        total_revenue=Sum("total_price"),
        avg_order_value=Avg("total_price"),
    )
    new_buyers = orders.filter(
        user__marketplace_orders__count=1
    ).values("user").distinct().count()
    return {
        "total_buyers":    agg["total_buyers"] or 0,
        "new_buyers":      new_buyers,
        "total_orders":    agg["total_orders"] or 0,
        "avg_order_value": str(round(agg["avg_order_value"] or 0, 2)),
        "total_revenue":   str(agg["total_revenue"] or 0),
        "orders_per_buyer":round((agg["total_orders"] or 0) / max(1, agg["total_buyers"] or 1), 2),
    }


def buyer_ltv(tenant, top_n: int = 20) -> list:
    """Top buyers by Lifetime Value."""
    from api.marketplace.models import Order
    return list(
        Order.objects.filter(tenant=tenant, status="delivered")
        .values("user__username", "user__email")
        .annotate(total_spend=Sum("total_price"), orders=Count("id"))
        .order_by("-total_spend")[:top_n]
    )


def repeat_purchase_rate(tenant, days: int = 90) -> dict:
    from api.marketplace.models import Order
    since = timezone.now() - timezone.timedelta(days=days)
    total_buyers = Order.objects.filter(tenant=tenant, created_at__gte=since).values("user").distinct().count()
    repeat_buyers = (
        Order.objects.filter(tenant=tenant, created_at__gte=since)
        .values("user")
        .annotate(cnt=Count("id"))
        .filter(cnt__gte=2)
        .count()
    )
    rate = round(repeat_buyers / total_buyers * 100, 1) if total_buyers else 0
    return {"total_buyers": total_buyers, "repeat_buyers": repeat_buyers, "repeat_rate_pct": rate}


def buyer_geo_breakdown(tenant) -> list:
    from api.marketplace.models import Order
    return list(
        Order.objects.filter(tenant=tenant)
        .values("shipping_city","shipping_district")
        .annotate(count=Count("id"), revenue=Sum("total_price"))
        .order_by("-count")[:20]
    )

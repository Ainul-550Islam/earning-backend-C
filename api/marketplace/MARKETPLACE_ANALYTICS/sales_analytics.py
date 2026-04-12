"""MARKETPLACE_ANALYTICS/sales_analytics.py — Sales KPIs"""
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDay, TruncMonth
from api.marketplace.models import Order, OrderItem
from api.marketplace.enums import OrderStatus


def sales_summary(tenant, from_date, to_date) -> dict:
    orders = Order.objects.filter(
        tenant=tenant, status=OrderStatus.DELIVERED,
        created_at__date__range=[from_date, to_date]
    )
    return {
        "total_orders": orders.count(),
        "total_revenue": str(orders.aggregate(t=Sum("total_price"))["t"] or 0),
        "avg_order_value": str(orders.aggregate(avg=Avg("total_price"))["avg"] or 0),
    }


def daily_revenue(tenant, from_date, to_date) -> list:
    return (
        Order.objects.filter(
            tenant=tenant, status=OrderStatus.DELIVERED,
            created_at__date__range=[from_date, to_date]
        )
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_price"), orders=Count("id"))
        .order_by("day")
    )


def monthly_revenue(tenant, year: int) -> list:
    return (
        Order.objects.filter(tenant=tenant, status=OrderStatus.DELIVERED,
                             created_at__year=year)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(revenue=Sum("total_price"), orders=Count("id"))
        .order_by("month")
    )

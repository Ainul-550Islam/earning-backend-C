"""MARKETPLACE_ANALYTICS/revenue_analytics.py — Revenue breakdown"""
from django.db.models import Sum
from api.marketplace.models import OrderItem, SellerPayout


def revenue_by_category(tenant) -> list:
    return (
        OrderItem.objects.filter(tenant=tenant)
        .values("variant__product__category__name")
        .annotate(revenue=Sum("subtotal"))
        .order_by("-revenue")
    )


def platform_commission_collected(tenant) -> dict:
    agg = OrderItem.objects.filter(tenant=tenant).aggregate(
        total_commission=Sum("commission_amount"),
        total_revenue=Sum("subtotal"),
    )
    return {
        "commission": str(agg["total_commission"] or 0),
        "gross_revenue": str(agg["total_revenue"] or 0),
    }

"""
MARKETPLACE_ANALYTICS/category_analytics.py — Category Performance Analytics
"""
from django.db.models import Sum, Count, Avg


def category_revenue(tenant, limit: int = 20) -> list:
    from api.marketplace.models import OrderItem
    return list(
        OrderItem.objects.filter(tenant=tenant)
        .values("variant__product__category__name","variant__product__category__id")
        .annotate(revenue=Sum("subtotal"), orders=Count("order",distinct=True), units=Sum("quantity"))
        .order_by("-revenue")[:limit]
    )


def category_conversion_rate(tenant) -> list:
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    from api.marketplace.models import Order
    # Views vs purchases per category
    views = (
        AppEvent.objects.filter(tenant=tenant, event_type="category_view")
        .values("properties__category_id")
        .annotate(view_count=Count("id"))
    )
    return [{"category_id": v.get("properties__category_id"), "views": v["view_count"]} for v in views]


def top_categories_by_rating(tenant, limit: int = 10) -> list:
    from api.marketplace.models import Product
    return list(
        Product.objects.filter(tenant=tenant, status="active")
        .values("category__name")
        .annotate(avg_rating=Avg("average_rating"), product_count=Count("id"))
        .filter(product_count__gte=3)
        .order_by("-avg_rating")[:limit]
    )

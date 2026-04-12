"""
CATEGORY_TAXONOMY/category_analytics.py — Category Performance Analytics
"""
from django.db.models import Sum, Count, Avg
from api.marketplace.models import Category, Product, OrderItem


def category_performance(tenant) -> list:
    """Revenue and order performance per category."""
    return list(
        OrderItem.objects.filter(tenant=tenant)
        .values("variant__product__category__id","variant__product__category__name")
        .annotate(
            revenue=Sum("subtotal"),
            orders=Count("order", distinct=True),
            units=Sum("quantity"),
        )
        .order_by("-revenue")[:20]
    )


def category_product_stats(category: Category) -> dict:
    products = Product.objects.filter(category=category, status="active")
    agg = products.aggregate(
        count=Count("id"),
        avg_price=Avg("base_price"),
        avg_rating=Avg("average_rating"),
        total_sales=Sum("total_sales"),
    )
    return {
        "name":        category.name,
        "products":    agg["count"] or 0,
        "avg_price":   str(round(agg["avg_price"] or 0, 2)),
        "avg_rating":  round(agg["avg_rating"] or 0, 2),
        "total_sales": agg["total_sales"] or 0,
    }


def trending_categories(tenant, days: int = 7) -> list:
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        OrderItem.objects.filter(tenant=tenant, created_at__gte=since)
        .values("variant__product__category__name","variant__product__category__slug")
        .annotate(orders=Count("order",distinct=True), revenue=Sum("subtotal"))
        .order_by("-orders")[:10]
    )


def category_conversion_rates(tenant) -> list:
    """Rough conversion estimate: views vs orders per category."""
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    from django.db.models.functions import Cast
    from django.db.models import FloatField

    views = dict(
        AppEvent.objects.filter(tenant=tenant, event_type="category_view")
        .values("properties__category_slug")
        .annotate(v=Count("id"))
        .values_list("properties__category_slug","v")
    )
    orders_per_cat = dict(
        OrderItem.objects.filter(tenant=tenant)
        .values("variant__product__category__slug")
        .annotate(o=Count("order",distinct=True))
        .values_list("variant__product__category__slug","o")
    )
    result = []
    for slug, view_count in views.items():
        if not slug:
            continue
        order_count = orders_per_cat.get(slug, 0)
        result.append({
            "category_slug": slug,
            "views":         view_count,
            "orders":        order_count,
            "conversion_pct":round(order_count / view_count * 100, 2) if view_count else 0,
        })
    return sorted(result, key=lambda x: x["orders"], reverse=True)[:15]

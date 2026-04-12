"""
MARKETPLACE_ANALYTICS/product_analytics.py — Product Performance Analytics
"""
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from api.marketplace.models import Product, OrderItem


def top_selling_products(tenant, limit: int = 10, days: int = None) -> list:
    qs = OrderItem.objects.filter(tenant=tenant)
    if days:
        since = timezone.now() - timezone.timedelta(days=days)
        qs    = qs.filter(created_at__gte=since)
    return list(
        qs.values("variant__product__id","variant__product__name","variant__product__slug")
        .annotate(units_sold=Sum("quantity"), revenue=Sum("subtotal"), orders=Count("order",distinct=True))
        .order_by("-units_sold")[:limit]
    )


def top_rated_products(tenant, min_reviews: int = 5, limit: int = 10) -> list:
    return list(
        Product.objects.filter(tenant=tenant, status="active", review_count__gte=min_reviews)
        .order_by("-average_rating","-review_count")
        .values("id","name","slug","average_rating","review_count","total_sales")[:limit]
    )


def newly_listed(tenant, days: int = 7, limit: int = 20) -> list:
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        Product.objects.filter(tenant=tenant, status="active", created_at__gte=since)
        .order_by("-created_at")
        .values("id","name","slug","base_price","sale_price","created_at")[:limit]
    )


def products_with_no_sales(tenant, days: int = 30) -> list:
    """Products that have never sold — potential dead inventory."""
    sold_ids = (
        OrderItem.objects.filter(tenant=tenant)
        .values_list("variant__product_id", flat=True)
        .distinct()
    )
    return list(
        Product.objects.filter(tenant=tenant, status="active")
        .exclude(pk__in=sold_ids)
        .values("id","name","slug","created_at")
        .order_by("-created_at")[:50]
    )


def product_view_to_purchase_ratio(tenant, days: int = 7) -> list:
    """Estimate how many views lead to a purchase for each product."""
    from api.marketplace.MOBILE_MARKETPLACE.mobile_analytics import AppEvent
    views = dict(
        AppEvent.objects.filter(tenant=tenant, event_type="product_view",
                                created_at__gte=timezone.now()-timezone.timedelta(days=days))
        .values("properties__product_id").annotate(v=Count("id"))
        .values_list("properties__product_id","v")
    )
    since   = timezone.now() - timezone.timedelta(days=days)
    orders  = dict(
        OrderItem.objects.filter(tenant=tenant, created_at__gte=since)
        .values("variant__product_id").annotate(o=Count("order",distinct=True))
        .values_list("variant__product_id","o")
    )
    result = []
    for pid_str, view_count in views.items():
        try:
            pid = int(pid_str) if pid_str else None
        except (TypeError, ValueError):
            continue
        if not pid:
            continue
        order_count = orders.get(pid, 0)
        result.append({
            "product_id":    pid,
            "views":         view_count,
            "purchases":     order_count,
            "conversion_pct":round(order_count / view_count * 100, 2) if view_count else 0,
        })
    return sorted(result, key=lambda x: x["conversion_pct"], reverse=True)[:20]

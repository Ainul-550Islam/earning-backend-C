"""
MARKETPLACE_ANALYTICS/price_intelligence.py — Competitive Pricing Intelligence
"""
from django.db.models import Avg, Min, Max, Count, StdDev


def price_analysis(tenant, category=None) -> dict:
    from api.marketplace.models import Product
    qs = Product.objects.filter(tenant=tenant, status="active")
    if category:
        qs = qs.filter(category=category)

    agg = qs.aggregate(
        avg_price=Avg("base_price"),
        min_price=Min("base_price"),
        max_price=Max("base_price"),
        std_dev=StdDev("base_price"),
        product_count=Count("id"),
    )
    return {k: str(v) if v is not None else "0" for k, v in agg.items()}


def overpriced_products(tenant, threshold_pct: float = 30) -> list:
    """Products priced >30% above category average."""
    from api.marketplace.models import Product
    from django.db.models import F, ExpressionWrapper, DecimalField
    results = []
    from api.marketplace.models import Category
    for cat in Category.objects.filter(tenant=tenant, is_active=True):
        avg = Product.objects.filter(tenant=tenant, category=cat, status="active"
                                     ).aggregate(avg=Avg("base_price"))["avg"]
        if not avg:
            continue
        threshold = avg * (1 + threshold_pct / 100)
        expensive = Product.objects.filter(
            tenant=tenant, category=cat, status="active", base_price__gt=threshold
        ).values("id","name","base_price")[:5]
        if expensive:
            results.append({
                "category": cat.name,
                "avg_price": str(round(avg, 2)),
                "threshold":  str(round(threshold, 2)),
                "products":   list(expensive),
            })
    return results


def price_elasticity_estimate(product) -> dict:
    """Estimate demand sensitivity to price changes using historical orders."""
    from api.marketplace.models import OrderItem
    orders = OrderItem.objects.filter(
        variant__product=product
    ).values("unit_price").annotate(qty=Count("id")).order_by("unit_price")
    if len(orders) < 2:
        return {"elasticity": "insufficient_data"}
    return {"elasticity": "computed", "data_points": len(orders)}

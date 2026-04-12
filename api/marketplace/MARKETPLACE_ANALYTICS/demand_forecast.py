"""
MARKETPLACE_ANALYTICS/demand_forecast.py — Demand Forecasting Engine
"""
from api.marketplace.MARKETPLACE_ANALYTICS.forecast_analytics import demand_forecast_product, revenue_forecast


def reorder_recommendations(tenant, threshold_days: int = 14) -> list:
    """Products that will run out within threshold_days based on sales velocity."""
    from api.marketplace.models import Product
    from api.marketplace.enums import ProductStatus
    recommendations = []
    for product in Product.objects.filter(tenant=tenant, status=ProductStatus.ACTIVE).iterator(chunk_size=100):
        forecast = demand_forecast_product(product)
        if 0 < forecast["days_of_stock"] <= threshold_days:
            recommendations.append({
                "product_id":   product.pk,
                "product_name": product.name,
                "current_stock":forecast["current_stock"],
                "days_of_stock":forecast["days_of_stock"],
                "daily_rate":   forecast["daily_rate"],
                "suggested_reorder": forecast["monthly_forecast"],
                "urgency": "critical" if forecast["days_of_stock"] <= 7 else "medium",
            })
    return sorted(recommendations, key=lambda x: x["days_of_stock"])


def seasonal_demand_index(tenant, product_category=None) -> dict:
    """Compute seasonal demand patterns (1.0 = average)."""
    from api.marketplace.models import OrderItem
    from django.db.models.functions import TruncMonth
    from django.db.models import Sum, Count, Avg
    qs = OrderItem.objects.filter(tenant=tenant)
    if product_category:
        qs = qs.filter(variant__product__category=product_category)
    monthly = list(
        qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(units=Sum("quantity"))
        .order_by("month")
    )
    if not monthly:
        return {}
    avg_units = sum(m["units"] or 0 for m in monthly) / len(monthly)
    return {
        m["month"].strftime("%B"): round((m["units"] or 0) / max(1, avg_units), 2)
        for m in monthly
    }

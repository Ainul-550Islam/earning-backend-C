"""
MARKETPLACE_ANALYTICS/forecast_analytics.py — Sales Forecasting
"""
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone


def revenue_forecast(tenant, months_ahead: int = 3) -> dict:
    """Simple moving average forecast based on last 6 months."""
    from api.marketplace.models import Order
    from api.marketplace.enums import OrderStatus

    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    monthly = list(
        Order.objects.filter(tenant=tenant, status=OrderStatus.DELIVERED, created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(revenue=Sum("total_price"))
        .order_by("month")
    )

    if not monthly:
        return {"forecast": [], "basis": "no_data"}

    revenues = [float(m["revenue"] or 0) for m in monthly]
    avg_growth = (revenues[-1] - revenues[0]) / max(1, len(revenues) - 1) if len(revenues) > 1 else 0

    forecast = []
    last_revenue = revenues[-1] if revenues else 0
    last_month   = monthly[-1]["month"] if monthly else timezone.now()

    for i in range(1, months_ahead + 1):
        predicted = max(0, last_revenue + avg_growth * i)
        target_month = last_month.month + i
        target_year  = last_month.year
        while target_month > 12:
            target_month -= 12
            target_year  += 1
        forecast.append({
            "month":         f"{target_year:04d}-{target_month:02d}",
            "predicted":     str(round(predicted, 2)),
            "confidence":    "medium" if len(revenues) >= 4 else "low",
        })

    return {"forecast": forecast, "basis": "moving_average", "data_months": len(revenues)}


def demand_forecast_product(product, days: int = 30) -> dict:
    """Forecast demand for a specific product based on recent sales velocity."""
    from api.marketplace.models import OrderItem
    since = timezone.now() - timezone.timedelta(days=days)
    agg   = OrderItem.objects.filter(
        variant__product=product, created_at__gte=since
    ).aggregate(total_units=Sum("quantity"))
    total_units = agg["total_units"] or 0
    daily_rate  = total_units / days
    return {
        "daily_rate":       round(daily_rate, 2),
        "weekly_forecast":  round(daily_rate * 7, 0),
        "monthly_forecast": round(daily_rate * 30, 0),
        "current_stock":    product.variants.first().inventory.quantity if product.variants.exists() else 0,
        "days_of_stock":    round(product.variants.first().inventory.quantity / max(0.1, daily_rate), 1)
                            if product.variants.exists() else 0,
    }

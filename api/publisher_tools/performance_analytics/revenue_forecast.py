# api/publisher_tools/performance_analytics/revenue_forecast.py
"""Revenue Forecast — ML-based revenue forecasting."""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
import math
from django.db.models import Sum
from django.utils import timezone


def linear_regression(x_vals: List[float], y_vals: List[float]):
    n = len(x_vals)
    if n < 2:
        return 0, y_vals[-1] if y_vals else 0
    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n
    num = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
    den = sum((x_vals[i] - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def forecast_publisher_revenue(publisher, days_ahead: int = 30) -> Dict:
    """Publisher-এর future revenue forecast।"""
    from api.publisher_tools.models import PublisherEarning
    history = list(
        PublisherEarning.objects.filter(publisher=publisher, granularity="daily")
        .values("date").annotate(revenue=Sum("publisher_revenue"))
        .order_by("date")
    )
    if len(history) < 7:
        return {"forecast": 0, "confidence": "insufficient_data", "data_points": len(history)}
    y = [float(h.get("revenue") or 0) for h in history]
    x = list(range(len(y)))
    slope, intercept = linear_regression(x, y)
    n = len(x)
    future_preds = [max(0, slope * (n + i) + intercept) for i in range(1, days_ahead + 1)]
    total_forecast = sum(future_preds)
    recent_avg = sum(y[-7:]) / 7
    trend = "up" if slope > 0 else "down" if slope < 0 else "flat"
    return {
        "publisher_id":    publisher.publisher_id,
        "days_ahead":      days_ahead,
        "total_forecast":  round(total_forecast, 4),
        "daily_avg":       round(total_forecast / days_ahead, 4),
        "current_daily_avg": round(recent_avg, 4),
        "trend":           trend,
        "slope_per_day":   round(slope, 6),
        "confidence":      "high" if len(y) >= 60 else "medium" if len(y) >= 30 else "low",
        "data_points":     len(y),
    }


def forecast_next_month(publisher) -> Dict:
    """Next month revenue forecast।"""
    today = timezone.now().date()
    if today.month == 12:
        next_month_days = 31
    else:
        from calendar import monthrange
        next_year = today.year if today.month < 12 else today.year + 1
        next_month = (today.month % 12) + 1
        next_month_days = monthrange(next_year, next_month)[1]
    forecast = forecast_publisher_revenue(publisher, next_month_days)
    return {**forecast, "forecast_period": f"Next {next_month_days} days"}


def get_seasonal_adjustment(month: int) -> float:
    """Seasonal revenue multiplier by month。"""
    seasonal_factors = {
        1: 0.85, 2: 0.80, 3: 0.90, 4: 0.95, 5: 0.95, 6: 0.90,
        7: 0.85, 8: 0.90, 9: 0.95, 10: 1.00, 11: 1.10, 12: 1.20,
    }
    return seasonal_factors.get(month, 1.0)

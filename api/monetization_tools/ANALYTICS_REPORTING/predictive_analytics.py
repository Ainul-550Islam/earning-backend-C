"""ANALYTICS_REPORTING/predictive_analytics.py — Revenue forecasting."""
from decimal import Decimal
from typing import List


class RevenueForecaster:
    """Simple linear trend forecasting for revenue."""

    @staticmethod
    def linear_regression(y: List[float]) -> tuple:
        """Returns (slope, intercept) for a time series."""
        n  = len(y)
        if n < 2:
            return (0.0, y[0] if y else 0.0)
        x  = list(range(n))
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den = sum((xi - mx) ** 2 for xi in x)
        m   = num / den if den else 0
        b   = my - m * mx
        return (m, b)

    @classmethod
    def forecast_next_n_days(cls, tenant=None, days: int = 7, forecast_days: int = 7) -> list:
        from ..models import RevenueDailySummary
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        data   = list(
            RevenueDailySummary.objects.filter(date__gte=cutoff)
              .order_by("date")
              .values_list("total_revenue", flat=True)
        )
        if not data:
            return []
        y = [float(v) for v in data]
        m, b = cls.linear_regression(y)
        today = timezone.now().date()
        return [
            {
                "date":             str(today + timedelta(days=i+1)),
                "forecasted_revenue": Decimal(str(max(0, b + m * (len(y) + i)))).quantize(Decimal("0.01")),
            }
            for i in range(forecast_days)
        ]

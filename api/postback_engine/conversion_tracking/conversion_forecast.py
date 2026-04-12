"""
conversion_tracking/conversion_forecast.py
────────────────────────────────────────────
Conversion volume and revenue forecasting.
Uses historical data patterns to predict future performance.
Useful for: capacity planning, budget allocation, fraud spike alerts.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from ..models import Conversion, NetworkPerformance
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionForecast:

    def forecast_daily_conversions(
        self,
        network=None,
        days_ahead: int = 7,
        history_days: int = 30,
    ) -> List[dict]:
        """
        Forecast daily conversion volume for the next N days.
        Uses simple moving average of last history_days.
        Returns list of {"date": ..., "forecast_conversions": ..., "forecast_revenue_usd": ...}
        """
        # Calculate baseline from history
        cutoff = timezone.now() - timedelta(days=history_days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            qs = qs.filter(network=network)

        agg = qs.aggregate(
            total_convs=Count("id"),
            total_revenue=Sum("actual_payout"),
        )
        total_convs = agg["total_convs"] or 0
        total_revenue = float(agg["total_revenue"] or 0)

        daily_avg_convs   = total_convs / history_days
        daily_avg_revenue = total_revenue / history_days

        # Apply day-of-week adjustment (weekdays typically have higher CR)
        forecasts = []
        today = timezone.now().date()
        for i in range(1, days_ahead + 1):
            forecast_date = today + timedelta(days=i)
            dow = forecast_date.weekday()  # 0=Monday, 6=Sunday
            # Weekends typically have 20% less traffic
            multiplier = 0.80 if dow >= 5 else 1.10

            forecasts.append({
                "date": str(forecast_date),
                "day_of_week": forecast_date.strftime("%A"),
                "forecast_conversions": round(daily_avg_convs * multiplier),
                "forecast_revenue_usd": round(daily_avg_revenue * multiplier, 2),
            })

        return forecasts

    def forecast_monthly_revenue(
        self,
        network=None,
        history_months: int = 3,
    ) -> dict:
        """Forecast next month's revenue based on last N months."""
        today = timezone.now().date()
        first_of_this_month = today.replace(day=1)
        cutoff = first_of_this_month - timedelta(days=history_months * 30)

        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            converted_at__date__lt=first_of_this_month,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            qs = qs.filter(network=network)

        total = float(qs.aggregate(t=Sum("actual_payout"))["t"] or 0)
        monthly_avg = total / history_months

        return {
            "forecast_next_month_revenue_usd": round(monthly_avg, 2),
            "based_on_months": history_months,
            "monthly_avg_historical_usd": round(monthly_avg, 2),
        }

    def detect_anomaly(self, network, threshold_pct: float = 50.0) -> dict:
        """
        Detect if today's conversion rate is anomalously low or high vs recent average.
        threshold_pct: deviation percentage that triggers an anomaly alert.
        """
        today_convs = Conversion.objects.filter(
            network=network,
            converted_at__date=timezone.now().date(),
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).count()

        # Last 7-day average
        past_week = []
        for i in range(1, 8):
            d = (timezone.now() - timedelta(days=i)).date()
            cnt = Conversion.objects.filter(
                network=network,
                converted_at__date=d,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            ).count()
            past_week.append(cnt)

        avg_7d = sum(past_week) / len(past_week) if past_week else 0

        if avg_7d == 0:
            return {"anomaly": False, "message": "Insufficient historical data."}

        deviation_pct = abs((today_convs - avg_7d) / avg_7d * 100)
        is_anomaly = deviation_pct >= threshold_pct

        return {
            "anomaly": is_anomaly,
            "today_conversions": today_convs,
            "avg_7d_conversions": round(avg_7d, 1),
            "deviation_pct": round(deviation_pct, 1),
            "direction": "above" if today_convs > avg_7d else "below",
            "message": (
                f"⚠️ Anomaly: today's conversions are {deviation_pct:.0f}% "
                f"{'above' if today_convs > avg_7d else 'below'} the 7-day average."
            ) if is_anomaly else "Normal conversion volume."
        }


conversion_forecast = ConversionForecast()

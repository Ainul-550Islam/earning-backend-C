"""
analytics_reporting/weekly_report.py
──────────────────────────────────────
Weekly performance report — runs every Monday at 06:00 UTC.
Aggregates 7 days of NetworkPerformance records into a weekly summary.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Avg, Count, Max, Min
from django.utils import timezone
from ..models import NetworkPerformance, AdNetworkConfig

logger = logging.getLogger(__name__)


class WeeklyReport:

    def generate(self, week_end: date = None) -> dict:
        """
        Generate weekly summary for the 7 days ending on week_end.
        week_end defaults to yesterday.
        """
        week_end = week_end or (timezone.now() - timedelta(days=1)).date()
        week_start = week_end - timedelta(days=6)

        qs = NetworkPerformance.objects.filter(
            date__gte=week_start,
            date__lte=week_end,
        )

        totals = qs.aggregate(
            total_clicks=Sum("total_clicks"),
            total_conversions=Sum("approved_conversions"),
            total_revenue=Sum("total_payout_usd"),
            total_points=Sum("total_points_awarded"),
            avg_cr=Avg("conversion_rate"),
            avg_fraud_rate=Avg("fraud_rate"),
            peak_conversions=Max("approved_conversions"),
        )

        # Per-network breakdown
        network_breakdown = list(
            qs.values("network__name", "network__network_key")
            .annotate(
                weekly_conversions=Sum("approved_conversions"),
                weekly_revenue=Sum("total_payout_usd"),
                avg_cr=Avg("conversion_rate"),
            )
            .order_by("-weekly_conversions")
        )

        report = {
            "period": {"start": str(week_start), "end": str(week_end)},
            "totals": {
                "clicks":       totals["total_clicks"] or 0,
                "conversions":  totals["total_conversions"] or 0,
                "revenue_usd":  float(totals["total_revenue"] or 0),
                "points":       totals["total_points"] or 0,
                "avg_cr_pct":   round(float(totals["avg_cr"] or 0), 2),
                "avg_fraud_pct":round(float(totals["avg_fraud_rate"] or 0), 2),
                "peak_conv_day":totals["peak_conversions"] or 0,
            },
            "network_breakdown": [
                {
                    "network": r["network__name"],
                    "network_key": r["network__network_key"],
                    "conversions": r["weekly_conversions"] or 0,
                    "revenue_usd": float(r["weekly_revenue"] or 0),
                    "avg_cr_pct": round(float(r["avg_cr"] or 0), 2),
                }
                for r in network_breakdown
            ],
        }

        logger.info(
            "WeeklyReport: %s–%s | conversions=%d revenue=$%.2f",
            week_start, week_end,
            report["totals"]["conversions"],
            report["totals"]["revenue_usd"],
        )
        return report


weekly_report = WeeklyReport()

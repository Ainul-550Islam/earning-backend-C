"""
analytics_reporting/postback_analytics.py – Analytics & reporting for postbacks.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from django.db.models import Avg, Count, F, FloatField, Max, Min, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from ..models import (
    AdNetworkConfig, ClickLog, Conversion, HourlyStat,
    NetworkPerformance, PostbackRawLog, FraudAttemptLog,
)
from ..enums import ConversionStatus, PostbackStatus, FraudType

logger = logging.getLogger(__name__)


class PostbackAnalytics:
    """
    Analytics engine for postback system.
    Provides pre-aggregated metrics for dashboards and reports.
    """

    # ── Postback Summary ──────────────────────────────────────────────────────

    def get_postback_summary(
        self,
        network=None,
        start_date: date = None,
        end_date: date = None,
    ) -> dict:
        """
        Overall postback summary for a date range.
        """
        end = end_date or timezone.now().date()
        start = start_date or (end - timedelta(days=30))

        qs = PostbackRawLog.objects.filter(
            received_at__date__gte=start,
            received_at__date__lte=end,
        )
        if network:
            qs = qs.filter(network=network)

        agg = qs.aggregate(
            total=Count("id"),
            rewarded=Count("id", filter=Q(status=PostbackStatus.REWARDED)),
            rejected=Count("id", filter=Q(status=PostbackStatus.REJECTED)),
            duplicate=Count("id", filter=Q(status=PostbackStatus.DUPLICATE)),
            failed=Count("id", filter=Q(status=PostbackStatus.FAILED)),
            total_payout=Sum("usd_awarded"),
            total_points=Sum("points_awarded"),
        )

        total = agg["total"] or 0
        rewarded = agg["rewarded"] or 0

        return {
            "period": {"start": str(start), "end": str(end)},
            "total_postbacks": total,
            "rewarded": rewarded,
            "rejected": agg["rejected"] or 0,
            "duplicate": agg["duplicate"] or 0,
            "failed": agg["failed"] or 0,
            "reward_rate_pct": round((rewarded / total * 100) if total > 0 else 0, 2),
            "total_payout_usd": float(agg["total_payout"] or 0),
            "total_points": agg["total_points"] or 0,
        }

    # ── Conversion Analytics ──────────────────────────────────────────────────

    def get_conversion_funnel(
        self,
        network=None,
        offer_id: str = None,
        days: int = 30,
    ) -> dict:
        """
        Conversion funnel: impressions → clicks → conversions.
        """
        cutoff = timezone.now() - timedelta(days=days)

        click_qs = ClickLog.objects.filter(clicked_at__gte=cutoff)
        conv_qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )

        if network:
            click_qs = click_qs.filter(network=network)
            conv_qs = conv_qs.filter(network=network)
        if offer_id:
            click_qs = click_qs.filter(offer_id=offer_id)
            conv_qs = conv_qs.filter(offer_id=offer_id)

        total_clicks = click_qs.count()
        total_conversions = conv_qs.count()

        return {
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "conversion_rate_pct": round(
                (total_conversions / total_clicks * 100) if total_clicks > 0 else 0, 2
            ),
            "period_days": days,
        }

    # ── Time Series ───────────────────────────────────────────────────────────

    def get_daily_conversion_series(
        self,
        network=None,
        days: int = 30,
    ) -> List[dict]:
        """Return daily conversion counts as a time series."""
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(converted_at__gte=cutoff)
        if network:
            qs = qs.filter(network=network)

        rows = (
            qs.annotate(day=TruncDate("converted_at"))
            .values("day")
            .annotate(
                conversions=Count("id"),
                payout=Sum("actual_payout"),
                points=Sum("points_awarded"),
            )
            .order_by("day")
        )
        return [
            {
                "date": str(r["day"]),
                "conversions": r["conversions"],
                "payout_usd": float(r["payout"] or 0),
                "points": r["points"] or 0,
            }
            for r in rows
        ]

    def get_hourly_series(
        self,
        network=None,
        hours: int = 24,
    ) -> List[dict]:
        """Return hourly conversion counts for the last N hours."""
        cutoff = timezone.now() - timedelta(hours=hours)
        qs = Conversion.objects.filter(converted_at__gte=cutoff)
        if network:
            qs = qs.filter(network=network)

        rows = (
            qs.annotate(hour=TruncHour("converted_at"))
            .values("hour")
            .annotate(
                conversions=Count("id"),
                payout=Sum("actual_payout"),
            )
            .order_by("hour")
        )
        return [
            {
                "hour": r["hour"].isoformat(),
                "conversions": r["conversions"],
                "payout_usd": float(r["payout"] or 0),
            }
            for r in rows
        ]

    # ── Network Leaderboard ───────────────────────────────────────────────────

    def get_network_leaderboard(self, days: int = 30) -> List[dict]:
        """Rank networks by conversion count for the given period."""
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects
            .filter(converted_at__gte=cutoff, status=ConversionStatus.APPROVED)
            .values("network__name", "network__network_key")
            .annotate(
                conversions=Count("id"),
                revenue=Sum("actual_payout"),
            )
            .order_by("-conversions")
        )
        return [
            {
                "network": r["network__name"],
                "network_key": r["network__network_key"],
                "conversions": r["conversions"],
                "revenue_usd": float(r["revenue"] or 0),
            }
            for r in rows
        ]

    # ── Fraud Analytics ───────────────────────────────────────────────────────

    def get_fraud_summary(self, days: int = 30) -> dict:
        """Fraud attempt breakdown by type."""
        cutoff = timezone.now() - timedelta(days=days)
        qs = FraudAttemptLog.objects.filter(detected_at__gte=cutoff)

        breakdown = list(
            qs.values("fraud_type")
            .annotate(count=Count("id"), avg_score=Avg("fraud_score"))
            .order_by("-count")
        )
        return {
            "total_fraud_attempts": qs.count(),
            "auto_blocked": qs.filter(is_auto_blocked=True).count(),
            "breakdown": [
                {
                    "type": r["fraud_type"],
                    "count": r["count"],
                    "avg_score": round(r["avg_score"] or 0, 1),
                }
                for r in breakdown
            ],
            "period_days": days,
        }

    # ── Top Earners ───────────────────────────────────────────────────────────

    def get_top_converting_offers(self, days: int = 30, limit: int = 10) -> List[dict]:
        """Return top offers by conversion count."""
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects
            .filter(converted_at__gte=cutoff, status=ConversionStatus.APPROVED)
            .values("offer_id")
            .annotate(
                conversions=Count("id"),
                revenue=Sum("actual_payout"),
                points=Sum("points_awarded"),
            )
            .order_by("-conversions")[:limit]
        )
        return [
            {
                "offer_id": r["offer_id"],
                "conversions": r["conversions"],
                "revenue_usd": float(r["revenue"] or 0),
                "total_points": r["points"] or 0,
            }
            for r in rows
        ]


# Module-level singleton
postback_analytics = PostbackAnalytics()

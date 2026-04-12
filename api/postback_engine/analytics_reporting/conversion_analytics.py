"""
analytics_reporting/conversion_analytics.py
─────────────────────────────────────────────
Aggregated conversion analytics for reporting dashboard.
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from ..models import Conversion, ClickLog
from ..enums import ConversionStatus


class ConversionAnalyticsReport:

    def summary(self, days: int = 30, network=None, user=None) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network: qs = qs.filter(network=network)
        if user:    qs = qs.filter(user=user)

        agg = qs.aggregate(
            total=Count("id"),
            revenue=Sum("actual_payout"),
            points=Sum("points_awarded"),
            avg_payout=Avg("actual_payout"),
            reversed_count=Count("id", filter=Q(is_reversed=True)),
        )

        total_clicks = ClickLog.objects.filter(clicked_at__gte=cutoff).count()
        total = agg["total"] or 0

        return {
            "period_days": days,
            "total_conversions": total,
            "approved_conversions": total - (agg["reversed_count"] or 0),
            "reversed_conversions": agg["reversed_count"] or 0,
            "total_revenue_usd": float(agg["revenue"] or 0),
            "total_points": agg["points"] or 0,
            "avg_payout_usd": float(agg["avg_payout"] or 0),
            "conversion_rate_pct": round((total / total_clicks * 100) if total_clicks > 0 else 0, 2),
        }

    def funnel(self, days: int = 30, network=None) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        clicks_qs = ClickLog.objects.filter(clicked_at__gte=cutoff)
        convs_qs = Conversion.objects.filter(converted_at__gte=cutoff)
        if network:
            clicks_qs = clicks_qs.filter(network=network)
            convs_qs = convs_qs.filter(network=network)

        total_clicks = clicks_qs.count()
        total_convs = convs_qs.count()
        approved = convs_qs.filter(status=ConversionStatus.APPROVED).count()
        paid = convs_qs.filter(status=ConversionStatus.PAID).count()
        rejected = convs_qs.filter(status=ConversionStatus.REJECTED).count()

        return {
            "clicks": total_clicks,
            "conversions_total": total_convs,
            "conversions_approved": approved,
            "conversions_paid": paid,
            "conversions_rejected": rejected,
            "click_to_conversion_rate": round((total_convs / total_clicks * 100) if total_clicks > 0 else 0, 2),
            "approval_rate": round((approved / total_convs * 100) if total_convs > 0 else 0, 2),
        }


conversion_analytics_report = ConversionAnalyticsReport()

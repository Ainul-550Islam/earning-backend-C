"""
conversion_tracking/conversion_analytics.py
─────────────────────────────────────────────
Conversion-specific analytics: funnel, CR%, revenue, top offers, user LTV.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from ..models import Conversion, ClickLog
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionAnalytics:

    def conversion_rate(self, network=None, offer_id: str = None, days: int = 30) -> float:
        cutoff = timezone.now() - timedelta(days=days)
        clicks = ClickLog.objects.filter(clicked_at__gte=cutoff)
        convs  = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            clicks = clicks.filter(network=network)
            convs  = convs.filter(network=network)
        if offer_id:
            clicks = clicks.filter(offer_id=offer_id)
            convs  = convs.filter(offer_id=offer_id)
        total_clicks = clicks.count()
        if total_clicks == 0:
            return 0.0
        return round((convs.count() / total_clicks) * 100, 2)

    def revenue_by_day(self, days: int = 30, network=None) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            qs = qs.filter(network=network)
        rows = (
            qs.annotate(day=TruncDate("converted_at"))
            .values("day")
            .annotate(revenue=Sum("actual_payout"), conversions=Count("id"))
            .order_by("day")
        )
        return [
            {"date": str(r["day"]), "revenue_usd": float(r["revenue"] or 0), "conversions": r["conversions"]}
            for r in rows
        ]

    def top_offers(self, days: int = 30, limit: int = 10) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
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

    def user_ltv(self, user, days: int = 365) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        agg = Conversion.objects.filter(
            user=user,
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        ).aggregate(
            total=Count("id"),
            revenue=Sum("actual_payout"),
            points=Sum("points_awarded"),
        )
        return {
            "lifetime_conversions": agg["total"] or 0,
            "lifetime_revenue_usd": float(agg["revenue"] or 0),
            "lifetime_points":      agg["points"] or 0,
        }


conversion_analytics = ConversionAnalytics()

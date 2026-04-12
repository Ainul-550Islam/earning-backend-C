"""
analytics_reporting/offer_performance.py
──────────────────────────────────────────
Offer-level performance analytics.
Tracks per-offer: clicks, conversions, CR%, EPC, revenue, fraud rate.
Used for: offer optimisation, budget allocation, fraud identification.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from ..models import ClickLog, Conversion, FraudAttemptLog
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class OfferPerformance:

    def get_offer_stats(
        self,
        offer_id: str,
        days: int = 30,
        network=None,
    ) -> dict:
        """Complete performance stats for a single offer."""
        cutoff = timezone.now() - timedelta(days=days)

        clicks_qs = ClickLog.objects.filter(offer_id=offer_id, clicked_at__gte=cutoff)
        convs_qs = Conversion.objects.filter(
            offer_id=offer_id,
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            clicks_qs = clicks_qs.filter(network=network)
            convs_qs = convs_qs.filter(network=network)

        total_clicks = clicks_qs.count()
        total_convs = convs_qs.count()
        fraud_clicks = clicks_qs.filter(is_fraud=True).count()

        agg = convs_qs.aggregate(
            revenue=Sum("actual_payout"),
            points=Sum("points_awarded"),
            avg_payout=Avg("actual_payout"),
        )

        total_revenue = float(agg["revenue"] or 0)
        epc = total_revenue / total_clicks if total_clicks > 0 else 0
        cr = (total_convs / total_clicks * 100) if total_clicks > 0 else 0
        fraud_rate = (fraud_clicks / total_clicks * 100) if total_clicks > 0 else 0

        return {
            "offer_id": offer_id,
            "period_days": days,
            "total_clicks": total_clicks,
            "total_conversions": total_convs,
            "total_revenue_usd": round(total_revenue, 4),
            "total_points": agg["points"] or 0,
            "avg_payout_usd": float(agg["avg_payout"] or 0),
            "conversion_rate_pct": round(cr, 2),
            "fraud_rate_pct": round(fraud_rate, 2),
            "epc_usd": round(epc, 4),
        }

    def get_all_offers_leaderboard(
        self,
        days: int = 30,
        network=None,
        limit: int = 50,
    ) -> list:
        """Return all offers ranked by conversion count."""
        cutoff = timezone.now() - timedelta(days=days)
        qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            qs = qs.filter(network=network)

        rows = (
            qs.values("offer_id")
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

    def get_underperforming_offers(
        self,
        min_clicks: int = 100,
        max_cr_pct: float = 1.0,
        days: int = 30,
    ) -> list:
        """
        Identify offers with very low conversion rates.
        Requires min_clicks for statistical significance.
        """
        cutoff = timezone.now() - timedelta(days=days)
        click_counts = dict(
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .values("offer_id")
            .annotate(cnt=Count("id"))
            .filter(cnt__gte=min_clicks)
            .values_list("offer_id", "cnt")
        )
        conv_counts = dict(
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .values("offer_id")
            .annotate(cnt=Count("id"))
            .values_list("offer_id", "cnt")
        )
        results = []
        for offer_id, clicks in click_counts.items():
            convs = conv_counts.get(offer_id, 0)
            cr = (convs / clicks * 100) if clicks > 0 else 0
            if cr < max_cr_pct:
                results.append({
                    "offer_id": offer_id,
                    "clicks": clicks,
                    "conversions": convs,
                    "cr_pct": round(cr, 3),
                    "recommendation": "review_or_pause",
                })
        return sorted(results, key=lambda x: x["cr_pct"])

    def get_high_fraud_offers(self, days: int = 30, fraud_rate_threshold: float = 10.0) -> list:
        """Return offers with fraud rates above the threshold."""
        cutoff = timezone.now() - timedelta(days=days)
        results = []
        offer_ids = (
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .values_list("offer_id", flat=True)
            .distinct()
        )
        for offer_id in offer_ids:
            if not offer_id:
                continue
            total = ClickLog.objects.filter(offer_id=offer_id, clicked_at__gte=cutoff).count()
            fraud = ClickLog.objects.filter(
                offer_id=offer_id, clicked_at__gte=cutoff, is_fraud=True
            ).count()
            if total >= 20 and (fraud / total * 100) >= fraud_rate_threshold:
                results.append({
                    "offer_id": offer_id,
                    "total_clicks": total,
                    "fraud_clicks": fraud,
                    "fraud_rate_pct": round(fraud / total * 100, 2),
                    "recommendation": "investigate_or_pause",
                })
        return sorted(results, key=lambda x: x["fraud_rate_pct"], reverse=True)


offer_performance = OfferPerformance()

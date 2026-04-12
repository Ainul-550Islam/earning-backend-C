"""
conversion_tracking/conversion_optimizer.py
─────────────────────────────────────────────
Conversion rate optimization utilities.
Analyzes performance patterns and suggests improvements.
- Identifies low-CR offers for removal
- Flags high-fraud offers for review
- Tracks payout efficiency (revenue per click)
- Identifies best-performing traffic sources
"""
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, FloatField, ExpressionWrapper
from django.utils import timezone
from ..models import Conversion, ClickLog, NetworkPerformance
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class ConversionOptimizer:

    def get_low_cr_offers(self, min_clicks: int = 50, cr_threshold: float = 1.0, days: int = 30) -> list:
        """
        Find offers with very low conversion rates (< cr_threshold %).
        Minimum min_clicks required for statistical significance.
        """
        cutoff = timezone.now() - timedelta(days=days)

        # Get click counts per offer
        click_counts = dict(
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .values("offer_id")
            .annotate(cnt=Count("id"))
            .filter(cnt__gte=min_clicks)
            .values_list("offer_id", "cnt")
        )

        # Get conversion counts per offer
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
            if cr < cr_threshold:
                results.append({
                    "offer_id": offer_id,
                    "clicks": clicks,
                    "conversions": convs,
                    "cr_pct": round(cr, 3),
                    "recommendation": "review_or_remove",
                })

        return sorted(results, key=lambda x: x["cr_pct"])

    def get_top_traffic_sources(self, days: int = 30, limit: int = 10) -> list:
        """Identify best-performing traffic sources by sub_id."""
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .exclude(click_log__sub_id="")
            .values(sub_id=F("click_log__sub_id"))
            .annotate(
                conversions=Count("id"),
                revenue=Sum("actual_payout"),
            )
            .order_by("-conversions")[:limit]
        )
        return [
            {"sub_id": r["sub_id"], "conversions": r["conversions"],
             "revenue_usd": float(r["revenue"] or 0)}
            for r in rows
        ]

    def get_revenue_per_click(self, network=None, days: int = 30) -> float:
        """
        EPC (Earnings Per Click) = Total Revenue / Total Clicks.
        Key metric for traffic quality assessment.
        """
        cutoff = timezone.now() - timedelta(days=days)
        clicks_qs = ClickLog.objects.filter(clicked_at__gte=cutoff)
        convs_qs = Conversion.objects.filter(
            converted_at__gte=cutoff,
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
        )
        if network:
            clicks_qs = clicks_qs.filter(network=network)
            convs_qs = convs_qs.filter(network=network)

        total_clicks = clicks_qs.count()
        total_revenue = convs_qs.aggregate(rev=Sum("actual_payout"))["rev"] or Decimal("0")

        if total_clicks == 0:
            return 0.0
        return float(total_revenue / total_clicks)

    def recommend_payout_adjustments(self, network, days: int = 30) -> list:
        """
        Suggest payout adjustments per offer based on actual conversion data.
        Offers with very high CR can have payouts reduced without losing volume.
        Offers with very low CR may need higher payouts to attract quality traffic.
        """
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(
                network=network,
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .values("offer_id")
            .annotate(
                conversions=Count("id"),
                avg_payout=Avg("actual_payout"),
                total_revenue=Sum("actual_payout"),
            )
            .filter(conversions__gte=10)
        )

        recommendations = []
        for r in rows:
            avg_payout = float(r["avg_payout"] or 0)
            if avg_payout < 0.10:
                action = "increase_payout"
                reason = "Very low payout may reduce publisher interest"
            elif avg_payout > 5.0 and r["conversions"] > 100:
                action = "consider_reducing"
                reason = "High payout with high volume — margin optimization opportunity"
            else:
                action = "maintain"
                reason = "Payout within optimal range"
            recommendations.append({
                "offer_id": r["offer_id"],
                "conversions": r["conversions"],
                "avg_payout_usd": round(avg_payout, 4),
                "total_revenue_usd": float(r["total_revenue"] or 0),
                "action": action,
                "reason": reason,
            })

        return sorted(recommendations, key=lambda x: x["total_revenue_usd"], reverse=True)


# Module-level singleton
conversion_optimizer = ConversionOptimizer()

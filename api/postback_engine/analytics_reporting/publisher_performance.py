"""
analytics_reporting/publisher_performance.py
──────────────────────────────────────────────
Publisher (traffic source) performance analytics.
Publisher = sub_id / traffic source that sent the click.
Tracks: revenue, EPC, CR%, fraud rate per publisher/sub_id.
Used for: publisher quality scoring, payment reconciliation, fraud blacklisting.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from ..models import ClickLog, Conversion
from ..enums import ConversionStatus

logger = logging.getLogger(__name__)


class PublisherPerformance:

    def get_publisher_stats(
        self,
        sub_id: str,
        days: int = 30,
        network=None,
    ) -> dict:
        """Full performance stats for a single publisher (sub_id)."""
        cutoff = timezone.now() - timedelta(days=days)
        clicks_qs = ClickLog.objects.filter(sub_id=sub_id, clicked_at__gte=cutoff)
        convs_qs = Conversion.objects.filter(
            click_log__sub_id=sub_id,
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
            avg_payout=Avg("actual_payout"),
        )
        total_revenue = float(agg["revenue"] or 0)
        return {
            "sub_id": sub_id,
            "period_days": days,
            "total_clicks": total_clicks,
            "total_conversions": total_convs,
            "total_revenue_usd": round(total_revenue, 4),
            "avg_payout_usd": float(agg["avg_payout"] or 0),
            "conversion_rate_pct": round((total_convs / total_clicks * 100) if total_clicks > 0 else 0, 2),
            "fraud_rate_pct": round((fraud_clicks / total_clicks * 100) if total_clicks > 0 else 0, 2),
            "epc_usd": round(total_revenue / total_clicks if total_clicks > 0 else 0, 4),
            "quality_score": self._calculate_quality_score(total_clicks, total_convs, fraud_clicks, total_revenue),
        }

    def get_top_publishers(self, days: int = 30, limit: int = 20) -> list:
        """Return top publishers ranked by revenue."""
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .exclude(click_log__sub_id="")
            .values(sub_id=F("click_log__sub_id"))
            .annotate(conversions=Count("id"), revenue=Sum("actual_payout"))
            .order_by("-revenue")[:limit]
        )
        return [
            {
                "sub_id": r["sub_id"],
                "conversions": r["conversions"],
                "revenue_usd": float(r["revenue"] or 0),
            }
            for r in rows
        ]

    def get_suspicious_publishers(
        self,
        min_clicks: int = 50,
        max_cr_pct: float = 0.5,
        min_fraud_rate_pct: float = 15.0,
        days: int = 30,
    ) -> list:
        """Identify publishers with suspicious traffic patterns."""
        cutoff = timezone.now() - timedelta(days=days)
        click_data = dict(
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .exclude(sub_id="")
            .values("sub_id")
            .annotate(
                total=Count("id"),
                fraud=Count("id", filter={"is_fraud": True}),
            )
            .filter(total__gte=min_clicks)
            .values_list("sub_id", "total")
        )
        conv_data = dict(
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .exclude(click_log__sub_id="")
            .values(sub_id=F("click_log__sub_id"))
            .annotate(cnt=Count("id"))
            .values_list("sub_id", "cnt")
        )
        suspicious = []
        for sub_id, clicks in click_data.items():
            convs = conv_data.get(sub_id, 0)
            cr = convs / clicks * 100 if clicks > 0 else 0
            if cr < max_cr_pct:
                suspicious.append({
                    "sub_id": sub_id,
                    "clicks": clicks,
                    "conversions": convs,
                    "cr_pct": round(cr, 3),
                    "recommendation": "investigate",
                })
        return sorted(suspicious, key=lambda x: x["cr_pct"])

    def _calculate_quality_score(
        self,
        clicks: int,
        conversions: int,
        fraud_clicks: int,
        revenue: float,
    ) -> int:
        """
        Calculate publisher quality score (0-100).
        Higher = better quality traffic.
        """
        if clicks == 0:
            return 50  # Unknown
        score = 100
        # Penalise for fraud
        fraud_rate = fraud_clicks / clicks * 100
        score -= min(50, int(fraud_rate * 2))
        # Reward for good CR
        cr = conversions / clicks * 100
        if cr > 5:
            score += 10
        elif cr < 0.5:
            score -= 20
        # Reward for revenue
        if revenue > 100:
            score += 10
        return max(0, min(100, score))


publisher_performance = PublisherPerformance()

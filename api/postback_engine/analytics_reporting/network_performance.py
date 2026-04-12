"""
analytics_reporting/network_performance.py
────────────────────────────────────────────
Network-level performance analytics.
Calculates CR%, EPC, fraud rate, revenue share per network.
"""
from __future__ import annotations
from datetime import timedelta, date
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from ..models import AdNetworkConfig, NetworkPerformance, Conversion, ClickLog, PostbackRawLog
from ..enums import ConversionStatus, PostbackStatus


class NetworkPerformanceReport:

    def compute_for_date(self, target_date: date, network: AdNetworkConfig) -> NetworkPerformance:
        """Compute and store daily performance metrics for a network."""
        day_start = timezone.datetime.combine(target_date, timezone.datetime.min.time())
        day_start = timezone.make_aware(day_start)
        day_end = day_start + timedelta(days=1)

        clicks = ClickLog.objects.filter(network=network, clicked_at__gte=day_start, clicked_at__lt=day_end)
        convs = Conversion.objects.filter(network=network, converted_at__gte=day_start, converted_at__lt=day_end)
        postbacks = PostbackRawLog.objects.filter(network=network, received_at__gte=day_start, received_at__lt=day_end)

        total_clicks = clicks.count()
        approved = convs.filter(status=ConversionStatus.APPROVED).count()
        rejected = convs.filter(status=ConversionStatus.REJECTED).count()
        duplicates = postbacks.filter(status=PostbackStatus.DUPLICATE).count()
        fraud_clicks = clicks.filter(is_fraud=True).count()

        payout_agg = convs.filter(
            status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID]
        ).aggregate(total=Sum("actual_payout"), pts=Sum("points_awarded"))

        perf, _ = NetworkPerformance.objects.update_or_create(
            network=network, date=target_date,
            defaults={
                "tenant": network.tenant,
                "total_clicks": total_clicks,
                "total_conversions": convs.count(),
                "approved_conversions": approved,
                "rejected_conversions": rejected,
                "duplicate_conversions": duplicates,
                "fraud_clicks": fraud_clicks,
                "total_payout_usd": payout_agg["total"] or Decimal("0"),
                "total_points_awarded": payout_agg["pts"] or 0,
                "conversion_rate": round((approved / total_clicks * 100) if total_clicks > 0 else 0, 4),
                "fraud_rate": round((fraud_clicks / total_clicks * 100) if total_clicks > 0 else 0, 4),
                "avg_payout_usd": (payout_agg["total"] / approved) if approved > 0 else Decimal("0"),
                "computed_at": timezone.now(),
            },
        )
        return perf

    def get_leaderboard(self, days: int = 30) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .values("network__name", "network__network_key")
            .annotate(conversions=Count("id"), revenue=Sum("actual_payout"))
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


network_performance_report = NetworkPerformanceReport()

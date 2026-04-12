"""
click_tracking/click_analytics.py
───────────────────────────────────
Click-specific analytics: volume, device breakdown, geo, EPC, funnel.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from ..models import ClickLog, Conversion
from ..enums import ClickStatus, ConversionStatus, DeviceType

logger = logging.getLogger(__name__)


class ClickAnalytics:

    def click_volume_by_day(self, days: int = 30, network=None) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        qs = ClickLog.objects.filter(clicked_at__gte=cutoff)
        if network:
            qs = qs.filter(network=network)
        rows = (
            qs.annotate(day=TruncDate("clicked_at"))
            .values("day")
            .annotate(clicks=Count("id"), conversions=Count("id", filter={"converted": True}))
            .order_by("day")
        )
        return [
            {
                "date": str(r["day"]),
                "clicks": r["clicks"],
                "conversions": r["conversions"],
                "cr_pct": round((r["conversions"] / r["clicks"] * 100) if r["clicks"] > 0 else 0, 2),
            }
            for r in rows
        ]

    def device_breakdown(self, days: int = 30) -> list:
        cutoff = timezone.now() - timedelta(days=days)
        rows = (
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .values("device_type")
            .annotate(clicks=Count("id"))
            .order_by("-clicks")
        )
        total = sum(r["clicks"] for r in rows)
        return [
            {
                "device_type": r["device_type"],
                "clicks": r["clicks"],
                "pct": round((r["clicks"] / total * 100) if total > 0 else 0, 1),
            }
            for r in rows
        ]

    def fraud_rate_by_hour(self, hours: int = 24) -> list:
        cutoff = timezone.now() - timedelta(hours=hours)
        rows = (
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .annotate(hour=TruncHour("clicked_at"))
            .values("hour")
            .annotate(
                total=Count("id"),
                fraud=Count("id", filter={"is_fraud": True}),
            )
            .order_by("hour")
        )
        return [
            {
                "hour": r["hour"].isoformat(),
                "total_clicks": r["total"],
                "fraud_clicks": r["fraud"],
                "fraud_rate_pct": round((r["fraud"] / r["total"] * 100) if r["total"] > 0 else 0, 2),
            }
            for r in rows
        ]

    def epc_by_offer(self, days: int = 30, limit: int = 20) -> list:
        """Earnings Per Click by offer."""
        cutoff = timezone.now() - timedelta(days=days)
        click_counts = dict(
            ClickLog.objects.filter(clicked_at__gte=cutoff)
            .values("offer_id")
            .annotate(cnt=Count("id"))
            .values_list("offer_id", "cnt")
        )
        revenue_by_offer = dict(
            Conversion.objects.filter(
                converted_at__gte=cutoff,
                status__in=[ConversionStatus.APPROVED, ConversionStatus.PAID],
            )
            .values("offer_id")
            .annotate(rev=Sum("actual_payout"))
            .values_list("offer_id", "rev")
        )
        results = []
        for offer_id, clicks in click_counts.items():
            if clicks == 0:
                continue
            rev = float(revenue_by_offer.get(offer_id) or 0)
            epc = rev / clicks
            results.append({
                "offer_id": offer_id,
                "clicks": clicks,
                "revenue_usd": round(rev, 4),
                "epc_usd": round(epc, 4),
            })
        return sorted(results, key=lambda x: x["epc_usd"], reverse=True)[:limit]


click_analytics = ClickAnalytics()

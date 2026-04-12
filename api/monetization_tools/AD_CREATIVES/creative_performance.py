"""AD_CREATIVES/creative_performance.py — Creative performance analytics."""
from decimal import Decimal
from django.db.models import Sum, Count, Avg


class CreativePerformanceAnalyzer:
    """Analyzes ad creative performance metrics."""

    @staticmethod
    def top_creatives(ad_unit_id: int = None, limit: int = 10) -> list:
        from ..models import AdCreative
        qs = AdCreative.objects.filter(status="approved", impressions__gt=0)
        if ad_unit_id:
            qs = qs.filter(ad_unit_id=ad_unit_id)
        return list(qs.order_by("-revenue")[:limit].values(
            "id", "name", "creative_type", "impressions", "clicks", "revenue"
        ))

    @staticmethod
    def ctr(creative_id: int) -> Decimal:
        from ..models import AdCreative
        try:
            c = AdCreative.objects.get(pk=creative_id)
            if not c.impressions:
                return Decimal("0")
            return (Decimal(c.clicks) / c.impressions * 100).quantize(Decimal("0.0001"))
        except AdCreative.DoesNotExist:
            return Decimal("0")

    @staticmethod
    def ecpm(creative_id: int) -> Decimal:
        from ..models import AdCreative
        try:
            c = AdCreative.objects.get(pk=creative_id)
            if not c.impressions:
                return Decimal("0")
            return (c.revenue / c.impressions * 1000).quantize(Decimal("0.0001"))
        except AdCreative.DoesNotExist:
            return Decimal("0")

    @staticmethod
    def summary(ad_unit_id: int) -> dict:
        from ..models import AdCreative
        return AdCreative.objects.filter(
            ad_unit_id=ad_unit_id, status="approved"
        ).aggregate(
            total_impressions=Sum("impressions"),
            total_clicks=Sum("clicks"),
            total_revenue=Sum("revenue"),
            avg_ecpm=Avg("revenue"),
            count=Count("id"),
        )

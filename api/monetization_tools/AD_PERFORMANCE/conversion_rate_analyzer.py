"""AD_PERFORMANCE/conversion_rate_analyzer.py — Conversion rate analytics."""
from decimal import Decimal
from django.db.models import Avg, Sum


class ConversionRateAnalyzer:
    """Click-to-conversion rate analysis for CPA/CPI campaigns."""

    @staticmethod
    def current(campaign_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            campaign_id=campaign_id, date__gte=cutoff
        ).aggregate(clk=Sum("clicks"), cnv=Sum("conversions"))
        if not agg["clk"]:
            return Decimal("0")
        return (Decimal(agg["cnv"] or 0) / agg["clk"] * 100).quantize(Decimal("0.0001"))

    @staticmethod
    def by_country(campaign_id: int, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return list(
            AdPerformanceDaily.objects.filter(
                campaign_id=campaign_id, date__gte=cutoff
            ).values("country")
             .annotate(clicks=Sum("clicks"), conversions=Sum("conversions"))
             .order_by("-conversions")
        )

    @staticmethod
    def trend(campaign_id: int, days: int = 30) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return list(
            AdPerformanceDaily.objects.filter(
                campaign_id=campaign_id, date__gte=cutoff
            ).values("date")
             .annotate(cvr=Avg("cvr"))
             .order_by("date")
        )

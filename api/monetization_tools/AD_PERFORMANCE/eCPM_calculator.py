"""AD_PERFORMANCE/eCPM_calculator.py — Effective CPM computation."""
from decimal import Decimal
from django.db.models import Sum, Avg


class ECPMCalculator:
    """Computes eCPM across different dimensions."""

    @staticmethod
    def from_revenue(revenue: Decimal, impressions: int) -> Decimal:
        if not impressions:
            return Decimal("0.0000")
        return (revenue / impressions * 1000).quantize(Decimal("0.0001"))

    @staticmethod
    def weighted_average(data: list) -> Decimal:
        """Weighted average eCPM: sum(rev) / sum(imp) * 1000."""
        total_rev = sum(Decimal(str(r.get("revenue", 0))) for r in data)
        total_imp = sum(int(r.get("impressions", 0)) for r in data)
        if not total_imp:
            return Decimal("0.0000")
        return (total_rev / total_imp * 1000).quantize(Decimal("0.0001"))

    @staticmethod
    def by_country(ad_unit_id: int, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return list(
            AdPerformanceDaily.objects.filter(
                ad_unit_id=ad_unit_id, date__gte=cutoff
            ).values("country")
             .annotate(rev=Sum("total_revenue"), imp=Sum("impressions"), avg_ecpm=Avg("ecpm"))
             .order_by("-avg_ecpm")
        )

    @staticmethod
    def trend(ad_unit_id: int, days: int = 30) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return list(
            AdPerformanceDaily.objects.filter(
                ad_unit_id=ad_unit_id, date__gte=cutoff
            ).values("date").annotate(ecpm=Avg("ecpm")).order_by("date")
        )

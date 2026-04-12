"""AD_PERFORMANCE/fill_rate_analyzer.py — Ad fill rate analysis."""
from decimal import Decimal
from django.db.models import Avg, Sum


class FillRateAnalyzer:
    """Analyzes ad fill rates to identify inventory gaps."""

    LOW_FILL_THRESHOLD  = Decimal("50.00")
    GOOD_FILL_THRESHOLD = Decimal("80.00")

    @staticmethod
    def current(ad_unit_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return AdPerformanceDaily.objects.filter(
            ad_unit_id=ad_unit_id, date__gte=cutoff
        ).aggregate(avg=Avg("fill_rate"))["avg"] or Decimal("0")

    @staticmethod
    def low_fill_units(tenant=None, threshold: Decimal = None, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        threshold = threshold or FillRateAnalyzer.LOW_FILL_THRESHOLD
        cutoff    = timezone.now().date() - timedelta(days=days)
        qs = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("ad_unit_id", "ad_unit__name")
              .annotate(avg_fill=Avg("fill_rate"))
              .filter(avg_fill__lt=threshold)
              .order_by("avg_fill")
        )

    @staticmethod
    def by_network(tenant=None, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("ad_network__display_name")
              .annotate(avg_fill=Avg("fill_rate"), total_imp=Sum("impressions"))
              .order_by("-avg_fill")
        )

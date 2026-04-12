"""OPTIMIZATION_ENGINES/yield_optimizer.py — Ad yield optimization."""
from decimal import Decimal
from django.db.models import Avg


class YieldOptimizer:
    """Maximizes revenue per impression across the waterfall."""

    @classmethod
    def optimal_floor(cls, ad_unit_id: int, percentile: float = 0.25) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum
        cutoff = timezone.now().date() - timedelta(days=7)
        ecpms  = list(
            AdPerformanceDaily.objects.filter(
                ad_unit_id=ad_unit_id, date__gte=cutoff, impressions__gt=0
            ).values_list("ecpm", flat=True).order_by("ecpm")
        )
        if not ecpms:
            return Decimal("0.5000")
        idx = int(len(ecpms) * percentile)
        return Decimal(str(ecpms[idx])).quantize(Decimal("0.0001"))

    @classmethod
    def revenue_uplift(cls, old_floor: Decimal, new_floor: Decimal,
                        avg_ecpm: Decimal, impressions: int) -> Decimal:
        if avg_ecpm <= 0:
            return Decimal("0")
        fill_change = Decimal("1") - (new_floor / avg_ecpm)
        return (impressions / 1000 * avg_ecpm * fill_change).quantize(Decimal("0.0001"))

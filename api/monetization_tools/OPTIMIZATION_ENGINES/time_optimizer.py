"""OPTIMIZATION_ENGINES/time_optimizer.py — Time-of-day bid optimization."""
from decimal import Decimal


HOUR_MULTIPLIERS = {
    0: Decimal("0.6"), 1: Decimal("0.5"), 2: Decimal("0.4"),
    3: Decimal("0.4"), 4: Decimal("0.5"), 5: Decimal("0.6"),
    6: Decimal("0.8"), 7: Decimal("1.0"), 8: Decimal("1.2"),
    9: Decimal("1.4"), 10: Decimal("1.5"), 11: Decimal("1.5"),
    12: Decimal("1.4"), 13: Decimal("1.3"), 14: Decimal("1.2"),
    15: Decimal("1.3"), 16: Decimal("1.4"), 17: Decimal("1.5"),
    18: Decimal("1.6"), 19: Decimal("1.7"), 20: Decimal("1.8"),
    21: Decimal("1.7"), 22: Decimal("1.5"), 23: Decimal("1.0"),
}


class TimeOptimizer:
    """Adjusts bids based on time-of-day performance patterns."""

    @classmethod
    def multiplier(cls, hour: int = None) -> Decimal:
        from django.utils import timezone
        h = hour if hour is not None else timezone.now().hour
        return HOUR_MULTIPLIERS.get(h, Decimal("1.0"))

    @classmethod
    def adjust_bid(cls, base_bid: Decimal, hour: int = None) -> Decimal:
        return (base_bid * cls.multiplier(hour)).quantize(Decimal("0.0001"))

    @classmethod
    def peak_hours(cls) -> list:
        return [h for h, m in HOUR_MULTIPLIERS.items() if m >= Decimal("1.5")]

    @classmethod
    def hourly_revenue_pattern(cls, ad_unit_id: int, days: int = 7) -> list:
        from ..models import AdPerformanceHourly
        from django.db.models import Avg, Sum
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models.functions import ExtractHour
        cutoff = timezone.now() - timedelta(days=days)
        return list(
            AdPerformanceHourly.objects.filter(
                ad_unit_id=ad_unit_id, hour_bucket__gte=cutoff
            ).annotate(hour=ExtractHour("hour_bucket"))
             .values("hour")
             .annotate(avg_ecpm=Avg("ecpm"), total_rev=Sum("revenue_usd"))
             .order_by("hour")
        )

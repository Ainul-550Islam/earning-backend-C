"""OPTIMIZATION_ENGINES/device_optimizer.py — Device-type bid optimization."""
from decimal import Decimal


DEVICE_ECPM_MAP = {
    "mobile":  Decimal("1.0"),
    "tablet":  Decimal("1.2"),
    "desktop": Decimal("1.5"),
    "tv":      Decimal("0.8"),
}


class DeviceOptimizer:
    """Device-type based bid and creative optimization."""

    @classmethod
    def multiplier(cls, device_type: str) -> Decimal:
        return DEVICE_ECPM_MAP.get(device_type.lower() if device_type else "mobile", Decimal("1.0"))

    @classmethod
    def adjust_bid(cls, base_bid: Decimal, device_type: str) -> Decimal:
        return (base_bid * cls.multiplier(device_type)).quantize(Decimal("0.0001"))

    @classmethod
    def best_format(cls, device_type: str) -> str:
        return {
            "mobile":  "rewarded_video",
            "tablet":  "interstitial",
            "desktop": "native",
            "tv":      "video",
        }.get(device_type.lower() if device_type else "mobile", "banner")

    @classmethod
    def device_revenue_breakdown(cls, tenant=None, days: int = 7) -> list:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum, Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs     = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(
            qs.values("device_type")
              .annotate(revenue=Sum("total_revenue"), ecpm=Avg("ecpm"))
              .order_by("-revenue")
        )

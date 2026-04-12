"""OPTIMIZATION_ENGINES/inventory_optimizer.py — Ad inventory optimization."""
from decimal import Decimal


class InventoryOptimizer:
    """Optimizes ad inventory allocation for maximum yield."""

    @staticmethod
    def unfilled_revenue_estimate(ad_unit_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.db.models import Sum, Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        agg    = AdPerformanceDaily.objects.filter(
            ad_unit_id=ad_unit_id, date__gte=cutoff
        ).aggregate(imp=Sum("impressions"), req=Sum("requests"), ecpm=Avg("ecpm"))
        if not agg["req"] or not agg["ecpm"]:
            return Decimal("0")
        unfilled = max(0, (agg["req"] or 0) - (agg["imp"] or 0))
        return (Decimal(unfilled) / 1000 * agg["ecpm"]).quantize(Decimal("0.0001"))

    @staticmethod
    def recommend_additional_networks(ad_unit_id: int) -> list:
        from ..models import WaterfallConfig, AdNetwork
        existing = WaterfallConfig.objects.filter(
            ad_unit_id=ad_unit_id, is_active=True
        ).values_list("ad_network_id", flat=True)
        return list(
            AdNetwork.objects.filter(is_active=True)
              .exclude(id__in=existing)
              .order_by("priority")
              .values("id", "display_name", "network_type")
        )

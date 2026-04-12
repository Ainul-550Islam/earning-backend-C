"""AD_NETWORKS/network_optimizer.py — Network performance optimizer."""
from decimal import Decimal
from django.db.models import Avg, Sum
from ..models import AdNetwork, AdPerformanceDaily


class NetworkOptimizer:
    """Optimizes network selection based on historical performance."""

    @staticmethod
    def get_top_networks(tenant=None, days: int = 7, limit: int = 5) -> list:
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        qs = AdPerformanceDaily.objects.filter(date__gte=cutoff)
        if tenant:
            qs = qs.filter(tenant=tenant)
        data = (
            qs.values("ad_network__display_name", "ad_network__network_type")
              .annotate(avg_ecpm=Avg("ecpm"), total_rev=Sum("total_revenue"))
              .order_by("-avg_ecpm")[:limit]
        )
        return list(data)

    @staticmethod
    def recommend_floor(network_id: int, days: int = 7) -> Decimal:
        """Recommend floor eCPM based on recent p25 of actual eCPM."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        avg = AdPerformanceDaily.objects.filter(
            ad_network_id=network_id, date__gte=cutoff
        ).aggregate(avg=Avg("ecpm"))["avg"]
        if not avg:
            return Decimal("0.5000")
        return (Decimal(str(avg)) * Decimal("0.25")).quantize(Decimal("0.0001"))

    @staticmethod
    def auto_adjust_priorities(tenant=None, days: int = 7):
        """Re-rank networks by recent avg eCPM — highest eCPM gets priority 1."""
        top = NetworkOptimizer.get_top_networks(tenant, days)
        for i, row in enumerate(top, start=1):
            AdNetwork.objects.filter(
                network_type=row["ad_network__network_type"]
            ).update(priority=i)
        return len(top)

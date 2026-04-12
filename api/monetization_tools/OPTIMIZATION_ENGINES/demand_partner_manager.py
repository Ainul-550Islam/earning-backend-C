"""OPTIMIZATION_ENGINES/demand_partner_manager.py — Demand partner optimization."""
from decimal import Decimal
from ..models import AdNetwork


class DemandPartnerManager:
    """Manages and scores demand partner performance."""

    @staticmethod
    def rank_partners(tenant=None, days: int = 7) -> list:
        from ..AD_NETWORKS.network_optimizer import NetworkOptimizer
        return NetworkOptimizer.get_top_networks(tenant, days)

    @staticmethod
    def enable(network_id: int):
        AdNetwork.objects.filter(pk=network_id).update(is_active=True)

    @staticmethod
    def disable(network_id: int):
        AdNetwork.objects.filter(pk=network_id).update(is_active=False)

    @staticmethod
    def set_timeout(network_id: int, timeout_ms: int):
        AdNetwork.objects.filter(pk=network_id).update(timeout_ms=timeout_ms)

    @staticmethod
    def toggle_bidding(network_id: int, enabled: bool):
        AdNetwork.objects.filter(pk=network_id).update(is_bidding=enabled)

    @staticmethod
    def get_fill_rate(network_id: int, days: int = 7) -> Decimal:
        from ..models import AdPerformanceDaily
        from django.db.models import Avg
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now().date() - timedelta(days=days)
        return AdPerformanceDaily.objects.filter(
            ad_network_id=network_id, date__gte=cutoff
        ).aggregate(avg=Avg("fill_rate"))["avg"] or Decimal("0")

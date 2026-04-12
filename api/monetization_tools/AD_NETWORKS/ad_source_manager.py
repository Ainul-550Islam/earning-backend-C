"""AD_NETWORKS/ad_source_manager.py — Manages multiple ad sources."""
from ..models import AdNetwork


class AdSourceManager:
    """Central registry of active ad network sources."""

    @staticmethod
    def get_all_active(tenant=None) -> list:
        qs = AdNetwork.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("priority"))

    @staticmethod
    def get_by_type(network_type: str, tenant=None):
        qs = AdNetwork.objects.filter(network_type=network_type, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def activate(network_id: int) -> bool:
        return bool(AdNetwork.objects.filter(pk=network_id).update(is_active=True))

    @staticmethod
    def deactivate(network_id: int) -> bool:
        return bool(AdNetwork.objects.filter(pk=network_id).update(is_active=False))

    @staticmethod
    def set_priority(network_id: int, priority: int) -> bool:
        return bool(AdNetwork.objects.filter(pk=network_id).update(priority=priority))

    @staticmethod
    def get_bidding_partners(tenant=None) -> list:
        qs = AdNetwork.objects.filter(is_active=True, is_bidding=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.order_by("priority"))

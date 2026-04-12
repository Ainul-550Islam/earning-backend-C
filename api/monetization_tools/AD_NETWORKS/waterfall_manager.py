"""AD_NETWORKS/waterfall_manager.py — Waterfall mediation manager."""
from decimal import Decimal
from ..models import WaterfallConfig


class WaterfallManager:
    """Manages mediation waterfall — ordered network selection."""

    @staticmethod
    def get(ad_unit_id: int, floor_ecpm: Decimal = Decimal("0")) -> list:
        return list(
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id,
                is_active=True,
                floor_ecpm__lte=floor_ecpm if floor_ecpm else Decimal("9999"),
            ).select_related("ad_network").order_by("priority")
        )

    @staticmethod
    def add_network(ad_unit_id: int, network_id: int,
                    priority: int, floor_ecpm: Decimal = Decimal("0"),
                    timeout_ms: int = 5000, tenant=None) -> WaterfallConfig:
        wf, _ = WaterfallConfig.objects.get_or_create(
            ad_unit_id=ad_unit_id, ad_network_id=network_id,
            defaults={
                "priority": priority, "floor_ecpm": floor_ecpm,
                "timeout_ms": timeout_ms, "tenant": tenant,
            },
        )
        return wf

    @staticmethod
    def reorder(ad_unit_id: int, network_priority_map: dict):
        """Bulk update priorities. network_priority_map = {network_id: priority}"""
        for net_id, prio in network_priority_map.items():
            WaterfallConfig.objects.filter(
                ad_unit_id=ad_unit_id, ad_network_id=net_id
            ).update(priority=prio)

    @staticmethod
    def remove_network(ad_unit_id: int, network_id: int):
        WaterfallConfig.objects.filter(
            ad_unit_id=ad_unit_id, ad_network_id=network_id
        ).delete()

"""AD_PLACEMENTS/placement_manager.py — Central placement manager."""
from decimal import Decimal
from typing import Optional


class PlacementManager:
    """Manages ad unit-to-screen placement resolution."""

    @staticmethod
    def get_placement(placement_key: str, tenant=None):
        from ..models import AdPlacement
        qs = AdPlacement.objects.filter(placement_key=placement_key, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related("ad_unit", "ad_network").first()

    @staticmethod
    def get_placements_for_screen(screen_name: str, tenant=None):
        from ..models import AdPlacement
        qs = AdPlacement.objects.filter(screen_name=screen_name, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.select_related("ad_unit", "ad_network").order_by("position")

    @staticmethod
    def activate(placement_id: int) -> bool:
        from ..models import AdPlacement
        return bool(AdPlacement.objects.filter(pk=placement_id).update(is_active=True))

    @staticmethod
    def deactivate(placement_id: int) -> bool:
        from ..models import AdPlacement
        return bool(AdPlacement.objects.filter(pk=placement_id).update(is_active=False))

    @staticmethod
    def bulk_activate_for_screen(screen_name: str) -> int:
        from ..models import AdPlacement
        return AdPlacement.objects.filter(screen_name=screen_name).update(is_active=True)

    @staticmethod
    def get_all_screens(tenant=None) -> list:
        from ..models import AdPlacement
        qs = AdPlacement.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.values_list("screen_name", flat=True).distinct().order_by("screen_name"))

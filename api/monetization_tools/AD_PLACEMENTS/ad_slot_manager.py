"""AD_PLACEMENTS/ad_slot_manager.py — Ad slot inventory management."""
from typing import List, Optional


class AdSlotManager:
    """Manages available ad slot inventory per screen/position."""

    SLOT_POSITIONS = [
        "top", "bottom", "mid_content", "fullscreen",
        "sidebar", "after_action", "on_exit", "in_feed",
    ]

    @staticmethod
    def get_available_slots(screen_name: str, tenant=None) -> List[dict]:
        """Return all available (unfilled) slots on a screen."""
        from ..models import AdPlacement
        qs = AdPlacement.objects.filter(
            screen_name=screen_name, is_active=True
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        return [
            {
                "slot_id":       p.id,
                "position":      p.position,
                "placement_key": p.placement_key,
                "refresh_rate":  p.refresh_rate,
                "freq_cap":      p.frequency_cap,
                "ad_format":     p.ad_unit.ad_format if p.ad_unit_id else None,
            }
            for p in qs.select_related("ad_unit")
        ]

    @staticmethod
    def count_slots(tenant=None) -> dict:
        from ..models import AdPlacement
        from django.db.models import Count
        qs = AdPlacement.objects.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return {
            "total":    qs.count(),
            "by_pos":   dict(qs.values_list("position").annotate(c=Count("id"))),
        }

    @staticmethod
    def is_slot_available(placement_key: str, tenant=None) -> bool:
        from ..models import AdPlacement
        qs = AdPlacement.objects.filter(placement_key=placement_key, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.exists()

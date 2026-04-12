# api/publisher_tools/ad_placements/placement_waterfall.py
"""Placement Waterfall — Waterfall configuration per placement."""
from decimal import Decimal
from typing import List, Dict
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlacementWaterfallConfig(TimeStampedModel):
    """Waterfall config specific to a placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_placementwaterfall_tenant", db_index=True)
    placement            = models.OneToOneField("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="waterfall_config")
    override_mediation   = models.BooleanField(default=False, help_text="Override ad unit mediation group")
    custom_waterfall_items = models.JSONField(default=list, blank=True)
    timeout_ms           = models.IntegerField(default=3000)
    no_fill_behavior     = models.CharField(max_length=20, choices=[
        ("collapse","Collapse Placement"),("fallback","Show Fallback"),("hide","Hide"),
    ], default="collapse")
    fallback_ad_url      = models.URLField(blank=True)
    fallback_html        = models.TextField(blank=True)
    enable_passback      = models.BooleanField(default=False)
    passback_tag         = models.TextField(blank=True)

    class Meta:
        db_table = "publisher_tools_placement_waterfall_configs"
        verbose_name = _("Placement Waterfall Config")

    def __str__(self):
        return f"Waterfall: {self.placement.name}"


def get_placement_waterfall(placement) -> List[Dict]:
    """Placement-এর effective waterfall return করে।"""
    try:
        config = placement.waterfall_config
        if config.override_mediation and config.custom_waterfall_items:
            return config.custom_waterfall_items
    except Exception:
        pass
    # Fall back to ad unit mediation group
    try:
        group = placement.ad_unit.mediation_group
        from api.publisher_tools.services import MediationService
        items = MediationService.get_active_waterfall(group)
        return [{"network": item.network.name, "priority": item.priority, "floor_ecpm": float(item.floor_ecpm)} for item in items]
    except Exception:
        return []

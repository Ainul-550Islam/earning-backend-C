# api/publisher_tools/ad_placements/placement_mediation.py
"""Placement Mediation — Mediation strategy per placement."""
from decimal import Decimal
from typing import Dict, List
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlacementMediationStrategy(TimeStampedModel):
    """Mediation strategy config for a specific placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_placementmed_tenant", db_index=True)
    STRATEGIES = [
        ("waterfall","Traditional Waterfall"),
        ("header_bidding","Header Bidding Only"),
        ("hybrid","Hybrid Mediation"),
        ("direct_deal","Direct Deal Priority"),
        ("programmatic","Programmatic Only"),
    ]
    placement          = models.OneToOneField("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="mediation_strategy")
    strategy           = models.CharField(max_length=20, choices=STRATEGIES, default="waterfall")
    enable_direct_deals= models.BooleanField(default=True)
    direct_deal_priority = models.IntegerField(default=1)
    enable_pmp         = models.BooleanField(default=False)
    pmp_deals          = models.JSONField(default=list, blank=True)
    enable_open_auction= models.BooleanField(default=True)
    open_auction_floor = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0000"))
    demand_sources      = models.JSONField(default=list, blank=True)
    exclude_networks    = models.JSONField(default=list, blank=True)
    auto_optimize       = models.BooleanField(default=False)

    class Meta:
        db_table = "publisher_tools_placement_mediation_strategies"
        verbose_name = _("Placement Mediation Strategy")

    def __str__(self):
        return f"Mediation: {self.placement.name} [{self.strategy}]"

    def get_demand_priority_order(self) -> List[str]:
        order = []
        if self.enable_direct_deals:
            order.append("direct_deal")
        if self.enable_pmp:
            order.append("pmp")
        order.append(self.strategy)
        if self.enable_open_auction and "open_auction" not in order:
            order.append("open_auction")
        return order

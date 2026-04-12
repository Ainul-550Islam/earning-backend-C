# api/publisher_tools/ad_placements/placement_header_bidding.py
"""Placement Header Bidding — Per-placement header bidding config."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlacementHeaderBiddingConfig(TimeStampedModel):
    """Header bidding settings specific to a placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_placementhb_tenant", db_index=True)
    placement            = models.OneToOneField("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="header_bidding_config")
    enabled              = models.BooleanField(default=False)
    bidder_type          = models.CharField(max_length=20, choices=[("prebid","Prebid.js"),("server","Server-side"),("hybrid","Hybrid")], default="prebid")
    timeout_ms           = models.IntegerField(default=1000)
    price_granularity    = models.CharField(max_length=10, choices=[("low","Low"),("medium","Medium"),("high","High"),("auto","Auto")], default="medium")
    bidders              = models.JSONField(default=list, blank=True)
    send_all_bids        = models.BooleanField(default=False)
    enable_user_id       = models.BooleanField(default=False)
    user_id_modules      = models.JSONField(default=list, blank=True)
    floor_price          = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0000"))
    currency             = models.CharField(max_length=5, default="USD")
    enable_analytics     = models.BooleanField(default=True)
    prebid_config_override = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "publisher_tools_placement_hb_configs"
        verbose_name = _("Placement HB Config")

    def __str__(self):
        return f"HB: {self.placement.name} — {'enabled' if self.enabled else 'disabled'}"

    def generate_prebid_config(self) -> dict:
        return {
            "timeout": self.timeout_ms,
            "priceGranularity": self.price_granularity,
            "bidders": self.bidders,
            "enableSendAllBids": self.send_all_bids,
            "floors": {"default": float(self.floor_price)},
            "currency": {"adServerCurrency": self.currency},
        }

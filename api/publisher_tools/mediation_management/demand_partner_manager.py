# api/publisher_tools/mediation_management/demand_partner_manager.py
"""Demand Partner Manager — DSP and demand partner management."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class DemandPartner(TimeStampedModel):
    """Demand-side platform (DSP) partner."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_demandpartner_tenant", db_index=True)
    PARTNER_TYPES = [
        ("dsp","DSP"),("agency","Agency Trading Desk"),("direct_advertiser","Direct Advertiser"),
        ("programmatic","Programmatic Buyer"),("private_marketplace","Private Marketplace"),
    ]
    name             = models.CharField(max_length=200)
    partner_type     = models.CharField(max_length=30, choices=PARTNER_TYPES, default="dsp")
    contact_email    = models.EmailField(blank=True)
    deal_id          = models.CharField(max_length=100, blank=True)
    seat_id          = models.CharField(max_length=100, blank=True)
    bidder_key       = models.CharField(max_length=100, blank=True)
    endpoint_url     = models.URLField(blank=True)
    is_active        = models.BooleanField(default=True, db_index=True)
    is_preferred     = models.BooleanField(default=False)
    floor_price      = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0000"))
    total_spend      = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    avg_cpm          = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    win_rate         = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    notes            = models.TextField(blank=True)

    class Meta:
        db_table = "publisher_tools_demand_partners"
        verbose_name = _("Demand Partner")
        verbose_name_plural = _("Demand Partners")
        ordering = ["-total_spend"]

    def __str__(self):
        return f"{self.name} [{self.partner_type}]"

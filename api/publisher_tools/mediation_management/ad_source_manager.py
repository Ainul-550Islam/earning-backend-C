# api/publisher_tools/mediation_management/ad_source_manager.py
"""Ad Source Manager — Multiple ad sources orchestration."""
from decimal import Decimal
from typing import List, Dict
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AdSource(TimeStampedModel):
    """Ad source configuration — each source in mediation stack."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_adsource_tenant", db_index=True)
    SOURCE_TYPES = [
        ("network","Ad Network"),("rtb","Real-Time Bidding"),("direct","Direct Campaign"),
        ("house","House Ad"),("fallback","Fallback"),("passback","Passback"),
    ]
    mediation_group  = models.ForeignKey("publisher_tools.MediationGroup", on_delete=models.CASCADE, related_name="ad_sources")
    name             = models.CharField(max_length=200)
    source_type      = models.CharField(max_length=20, choices=SOURCE_TYPES, default="network")
    priority         = models.IntegerField(default=0)
    floor_ecpm       = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0000"))
    is_active        = models.BooleanField(default=True, db_index=True)
    config           = models.JSONField(default=dict, blank=True)
    total_requests   = models.BigIntegerField(default=0)
    total_wins       = models.BigIntegerField(default=0)
    total_revenue    = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        db_table = "publisher_tools_ad_sources"
        verbose_name = _("Ad Source")
        ordering = ["priority"]
        indexes = [
            models.Index(fields=["mediation_group", "priority", "is_active"], name='idx_mediation_group_priori_a8f'),
        ]

    def __str__(self):
        return f"#{self.priority} {self.name} [{self.source_type}] — floor: ${self.floor_ecpm}"

    @property
    def win_rate(self):
        return round(self.total_wins / self.total_requests * 100, 2) if self.total_requests > 0 else 0.0

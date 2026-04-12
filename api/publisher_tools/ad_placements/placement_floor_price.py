# api/publisher_tools/ad_placements/placement_floor_price.py
"""Placement Floor Price — Dynamic floor price management."""
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class FloorPriceRule(TimeStampedModel):
    """Dynamic floor price rules per placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_floorpricerule_tenant", db_index=True)
    RULE_TYPES = [
        ("geo","Country-based"),("device","Device-based"),("time","Time-based"),
        ("network","Ad Network-based"),("audience","Audience-based"),("default","Default"),
    ]
    placement        = models.ForeignKey("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="floor_rules")
    rule_type        = models.CharField(max_length=20, choices=RULE_TYPES, default="default")
    conditions       = models.JSONField(default=dict, help_text="{'countries': ['US','GB'], 'devices': ['mobile']}")
    floor_price      = models.DecimalField(max_digits=8, decimal_places=4)
    priority         = models.IntegerField(default=0)
    is_active        = models.BooleanField(default=True, db_index=True)
    starts_at        = models.DateTimeField(null=True, blank=True)
    ends_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "publisher_tools_floor_price_rules"
        verbose_name = _("Floor Price Rule")
        ordering = ["-priority", "-created_at"]

    def __str__(self):
        return f"{self.placement.name} — {self.rule_type} floor: ${self.floor_price}"

    @property
    def is_active_now(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True


def get_effective_floor_price(placement, context: dict = None) -> Decimal:
    """Context-based effective floor price calculate করে।"""
    if context is None:
        return placement.effective_floor_price
    rules = FloorPriceRule.objects.filter(placement=placement, is_active=True).order_by("-priority")
    for rule in rules:
        if not rule.is_active_now:
            continue
        conditions = rule.conditions
        if rule.rule_type == "geo":
            if context.get("country") in conditions.get("countries", []):
                return rule.floor_price
        elif rule.rule_type == "device":
            if context.get("device_type") in conditions.get("devices", []):
                return rule.floor_price
        elif rule.rule_type == "default":
            return rule.floor_price
    return placement.effective_floor_price


def suggest_floor_price(placement, days: int = 30) -> Dict:
    """Historical eCPM data-র ভিত্তিতে floor price suggest করে।"""
    from django.db.models import Avg
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    agg = PublisherEarning.objects.filter(
        ad_unit=placement.ad_unit, date__gte=start, impressions__gt=0,
    ).aggregate(avg_ecpm=Avg("ecpm"))
    avg_ecpm = float(agg.get("avg_ecpm") or 0)
    suggested = round(avg_ecpm * 0.70, 4)
    return {
        "current_floor": float(placement.effective_floor_price),
        "avg_ecpm_30d": avg_ecpm,
        "suggested_floor": suggested,
        "potential_uplift_pct": round((suggested - float(placement.effective_floor_price)) / max(float(placement.effective_floor_price), 0.01) * 100, 2),
    }

from typing import Dict

# api/publisher_tools/ad_placements/placement_refresh.py
"""Placement Refresh — Ad refresh management and rate optimization."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


REFRESH_REVENUE_MULTIPLIERS = {
    "none": 1.0,
    "time_based": 1.3,
    "scroll": 1.2,
    "click": 1.1,
}

OPTIMAL_REFRESH_INTERVALS = {
    "banner":     30,
    "leaderboard": 45,
    "rectangle":  30,
    "sticky":     20,
    "native":     60,
}


class PlacementRefreshConfig(TimeStampedModel):
    """Advanced refresh configuration per placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_refreshconf_tenant", db_index=True)
    placement           = models.OneToOneField("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="refresh_config")
    enable_refresh      = models.BooleanField(default=False)
    refresh_type        = models.CharField(max_length=20, choices=[("time","Time"),("scroll","Scroll"),("user_action","User Action")], default="time")
    interval_seconds    = models.IntegerField(default=30)
    max_refreshes_per_session = models.IntegerField(default=10)
    stop_after_non_viewable  = models.BooleanField(default=True)
    min_viewability_for_refresh = models.IntegerField(default=50)
    refresh_on_tab_focus = models.BooleanField(default=True)
    throttle_on_slow_net = models.BooleanField(default=True)
    slow_net_threshold_ms= models.IntegerField(default=3000)
    daily_refresh_count  = models.BigIntegerField(default=0)
    avg_incremental_ecpm = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0000"))

    class Meta:
        db_table = "publisher_tools_placement_refresh_configs"
        verbose_name = _("Refresh Config")

    def __str__(self):
        return f"Refresh: {self.placement.name} — {self.interval_seconds}s"

    @property
    def estimated_revenue_lift(self):
        return REFRESH_REVENUE_MULTIPLIERS.get(self.refresh_type, 1.0)

    @classmethod
    def get_optimal_interval(cls, ad_format: str) -> int:
        return OPTIMAL_REFRESH_INTERVALS.get(ad_format, 30)

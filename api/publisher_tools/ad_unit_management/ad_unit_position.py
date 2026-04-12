# api/publisher_tools/ad_unit_management/ad_unit_position.py
"""Ad Unit Position — Above/below fold detection and position scoring."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


POSITION_ECPM_MULTIPLIERS = {
    "above_fold":    1.50,
    "header":        1.40,
    "in_content":    1.30,
    "between_posts": 1.20,
    "sticky_top":    1.30,
    "sticky_bottom": 1.25,
    "sidebar_left":  1.00,
    "sidebar_right": 0.90,
    "below_fold":    0.70,
    "footer":        0.60,
    "popup":         1.10,
}


class AdUnitPositionData(TimeStampedModel):
    """Tracks actual position performance data."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_adunitpos_tenant", db_index=True)
    ad_unit           = models.ForeignKey("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="position_data")
    position          = models.CharField(max_length=30)
    date              = models.DateField()
    avg_viewability   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_ecpm          = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    impressions       = models.BigIntegerField(default=0)
    clicks            = models.BigIntegerField(default=0)
    revenue           = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    scroll_depth_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Avg scroll depth when ad seen")
    time_to_view_ms   = models.IntegerField(default=0, help_text="Avg time from page load to ad view")

    class Meta:
        db_table = "publisher_tools_ad_unit_position_data"
        verbose_name = _("Position Data")
        unique_together = [["ad_unit", "position", "date"]]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.ad_unit.unit_id} @ {self.position} — {self.date}"

    @property
    def expected_ecpm_multiplier(self):
        return POSITION_ECPM_MULTIPLIERS.get(self.position, 1.0)

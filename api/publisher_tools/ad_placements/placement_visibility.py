# api/publisher_tools/ad_placements/placement_visibility.py
"""Placement Visibility — Viewability tracking and optimization."""
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlacementViewabilityLog(TimeStampedModel):
    """Daily viewability data per placement."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_viewlog_tenant", db_index=True)
    placement        = models.ForeignKey("publisher_tools.AdPlacement", on_delete=models.CASCADE, related_name="viewability_logs", db_index=True)
    date             = models.DateField(db_index=True)
    measured_imps    = models.BigIntegerField(default=0)
    viewable_imps    = models.BigIntegerField(default=0)
    viewability_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    avg_time_in_view = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    in_view_rate_1sec= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    in_view_rate_5sec= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    avg_scroll_depth = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "publisher_tools_placement_viewability_logs"
        verbose_name = _("Viewability Log")
        unique_together = [["placement", "date"]]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.placement.name} — {self.date} — {self.viewability_rate}%"

    def update_placement_avg(self):
        from django.db.models import Avg
        avg = PlacementViewabilityLog.objects.filter(
            placement=self.placement,
            date__gte=timezone.now().date() - timedelta(days=30)
        ).aggregate(avg=Avg("viewability_rate"))
        self.placement.avg_viewability = avg.get("avg") or Decimal("0")
        self.placement.save(update_fields=["avg_viewability", "updated_at"])

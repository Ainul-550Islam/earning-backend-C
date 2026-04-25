# api/publisher_tools/ad_unit_management/ad_unit_frequency.py
"""Ad Unit Frequency — Frequency capping management."""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class FrequencyCap(TimeStampedModel):
    """Frequency cap settings per ad unit."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_freqcap_tenant", db_index=True)
    ad_unit          = models.ForeignKey("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="frequency_caps")
    cap_type         = models.CharField(max_length=20, choices=[
        ("impressions","Impressions"),("clicks","Clicks"),("conversions","Conversions")
    ], default="impressions")
    max_count        = models.IntegerField(validators=[MinValueValidator(1)])
    window_type      = models.CharField(max_length=10, choices=[
        ("hour","Per Hour"),("day","Per Day"),("week","Per Week"),("session","Per Session"),
    ], default="day")
    window_hours     = models.IntegerField(default=24, validators=[MinValueValidator(1)])
    is_active        = models.BooleanField(default=True, db_index=True)
    applies_to       = models.CharField(max_length=20, choices=[
        ("user","Per User"),("device","Per Device"),("ip","Per IP"),("cookie","Per Cookie"),
    ], default="user")

    class Meta:
        db_table = "publisher_tools_frequency_caps"
        verbose_name = _("Frequency Cap")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ad_unit", "is_active"], name='idx_ad_unit_is_active_1534'),
        ]

    def __str__(self):
        return f"{self.ad_unit.unit_id} — Max {self.max_count} {self.cap_type}/{self.window_type}"


class FrequencyLog(TimeStampedModel):
    """Track frequency cap usage per user/device."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_freqlog_tenant", db_index=True)
    frequency_cap    = models.ForeignKey(FrequencyCap, on_delete=models.CASCADE, related_name="usage_logs")
    identifier       = models.CharField(max_length=255, db_index=True)
    count            = models.IntegerField(default=0)
    window_start     = models.DateTimeField()
    window_end       = models.DateTimeField()
    last_event_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "publisher_tools_frequency_logs"
        verbose_name = _("Frequency Log")
        unique_together = [["frequency_cap", "identifier", "window_start"]]
        indexes = [
            models.Index(fields=["frequency_cap", "identifier"], name='idx_frequency_cap_identifi_e64'),
        ]

    def __str__(self):
        return f"FreqLog: {self.frequency_cap.ad_unit.unit_id} — {self.identifier[:20]} — {self.count}/{self.frequency_cap.max_count}"

    @property
    def is_capped(self):
        return self.count >= self.frequency_cap.max_count

# api/publisher_tools/app_management/app_downloads.py
"""App Downloads — Download count tracking and analytics."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppDownloadSnapshot(TimeStampedModel):
    """Daily app download count snapshot."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appdownload_tenant", db_index=True)
    app              = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="download_snapshots", db_index=True)
    date             = models.DateField(db_index=True)
    new_downloads    = models.IntegerField(default=0)
    cumulative_downloads = models.BigIntegerField(default=0)
    new_installs     = models.IntegerField(default=0)
    uninstalls       = models.IntegerField(default=0)
    net_installs     = models.IntegerField(default=0)
    active_installs  = models.BigIntegerField(default=0)
    country_breakdown = models.JSONField(default=list, blank=True)
    platform         = models.CharField(max_length=10, choices=[("android","Android"),("ios","iOS")], default="android")
    source           = models.CharField(max_length=30, default="manual")

    class Meta:
        db_table = "publisher_tools_app_download_snapshots"
        verbose_name = _("App Download Snapshot")
        unique_together = [["app", "date", "platform"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["app", "date"]),
        ]

    def __str__(self):
        return f"{self.app.name} — {self.date} — {self.new_downloads:,} downloads"

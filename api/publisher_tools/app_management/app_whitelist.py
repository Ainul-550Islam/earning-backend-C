# api/publisher_tools/app_management/app_whitelist.py
"""App Whitelist — Approved advertisers and content for apps."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppWhitelistEntry(TimeStampedModel):
    """App-level ad whitelist."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appwl_tenant", db_index=True)
    app             = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="whitelist_entries", db_index=True)
    entry_type      = models.CharField(max_length=20, choices=[
        ("advertiser","Advertiser"),("domain","Ad Domain"),
        ("category","Preferred Category"),("network","Ad Network"),
    ], db_index=True)
    value           = models.CharField(max_length=500)
    priority        = models.IntegerField(default=0)
    is_preferred    = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True, db_index=True)
    reason          = models.TextField(blank=True)
    floor_price_override = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    added_by        = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = "publisher_tools_app_whitelist_entries"
        verbose_name = _("App Whitelist Entry")
        ordering = ["-priority", "-created_at"]
        indexes = [models.Index(fields=["app", "entry_type", "is_active"], name='idx_app_entry_type_is_acti_90e')]

    def __str__(self):
        return f"{self.app.name} — Allow {self.entry_type}: {self.value[:50]}"

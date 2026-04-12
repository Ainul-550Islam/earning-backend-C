# api/publisher_tools/app_management/app_blacklist.py
"""App Blacklist — Content and advertiser blocking for apps."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppBlacklistEntry(TimeStampedModel):
    """App-level ad blacklist entries."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appbl_tenant", db_index=True)
    app             = models.ForeignKey("publisher_tools.App", on_delete=models.CASCADE, related_name="blacklist_entries", db_index=True)
    entry_type      = models.CharField(max_length=20, choices=[
        ("advertiser","Advertiser"),("domain","Ad Domain"),
        ("category","Content Category"),("network","Ad Network"),
    ], db_index=True)
    value           = models.CharField(max_length=500)
    reason          = models.TextField(blank=True)
    is_active       = models.BooleanField(default=True, db_index=True)
    expires_at      = models.DateTimeField(null=True, blank=True)
    added_by        = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = "publisher_tools_app_blacklist_entries"
        verbose_name = _("App Blacklist Entry")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["app", "entry_type", "is_active"])]

    def __str__(self):
        return f"{self.app.name} — Block {self.entry_type}: {self.value[:50]}"

    @property
    def is_effective(self):
        return self.is_active and not (self.expires_at and timezone.now() > self.expires_at)

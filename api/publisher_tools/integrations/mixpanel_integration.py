# api/publisher_tools/integrations/mixpanel_integration.py
"""Mixpanel Analytics integration for Publisher Tools."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class MixpanelAnalyticsIntegration(TimeStampedModel):
    """Mixpanel Analytics integration configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_mixpanel_tenant", db_index=True)
    publisher   = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="mixpanel_integrations")
    name        = models.CharField(max_length=200, default="Mixpanel Analytics")
    is_active   = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    project_token = models.CharField(max_length=200, blank=True)
    api_secret = models.CharField(max_length=200, blank=True)
    settings    = models.JSONField(default=dict, blank=True)
    last_sync   = models.DateTimeField(null=True, blank=True)
    error_msg   = models.TextField(blank=True)
    sync_count  = models.IntegerField(default=0)
    status      = models.CharField(max_length=20, choices=[("active","Active"),("error","Error"),("pending","Pending")], default="pending")

    class Meta:
        db_table = "publisher_tools_mixpanel_integrations"
        verbose_name = _("Mixpanel Analytics Integration")
        unique_together = [["publisher"]]

    def __str__(self):
        return f"Mixpanel Analytics: {self.publisher.publisher_id} [{'active' if self.is_active else 'inactive'}]"

    def sync(self) -> bool:
        import logging
        logging.getLogger(__name__).info(f"Syncing Mixpanel Analytics for {self.publisher.publisher_id}")
        self.last_sync = timezone.now()
        self.sync_count += 1
        self.status = "active"
        self.save(update_fields=["last_sync", "sync_count", "status", "updated_at"])
        return True

    def get_embed_code(self) -> str:
        return f"<!-- Mixpanel Analytics Integration — Publisher {self.publisher.publisher_id} -->"

    def test_connection(self) -> bool:
        return self.is_active and bool(self.project_token)

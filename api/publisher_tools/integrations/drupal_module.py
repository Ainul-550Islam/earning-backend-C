# api/publisher_tools/integrations/drupal_module.py
"""Drupal Module integration for Publisher Tools."""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class DrupalModuleIntegration(TimeStampedModel):
    """Drupal Module integration configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_drupal_tenant", db_index=True)
    publisher   = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="drupal_integrations")
    name        = models.CharField(max_length=200, default="Drupal Module")
    is_active   = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    site_url = models.CharField(max_length=200, blank=True)
    module_key = models.CharField(max_length=200, blank=True)
    settings    = models.JSONField(default=dict, blank=True)
    last_sync   = models.DateTimeField(null=True, blank=True)
    error_msg   = models.TextField(blank=True)
    sync_count  = models.IntegerField(default=0)
    status      = models.CharField(max_length=20, choices=[("active","Active"),("error","Error"),("pending","Pending")], default="pending")

    class Meta:
        db_table = "publisher_tools_drupal_integrations"
        verbose_name = _("Drupal Module Integration")
        unique_together = [["publisher"]]

    def __str__(self):
        return f"Drupal Module: {self.publisher.publisher_id} [{'active' if self.is_active else 'inactive'}]"

    def sync(self) -> bool:
        import logging
        logging.getLogger(__name__).info(f"Syncing Drupal Module for {self.publisher.publisher_id}")
        self.last_sync = timezone.now()
        self.sync_count += 1
        self.status = "active"
        self.save(update_fields=["last_sync", "sync_count", "status", "updated_at"])
        return True

    def get_embed_code(self) -> str:
        return f"<!-- Drupal Module Integration — Publisher {self.publisher.publisher_id} -->"

    def test_connection(self) -> bool:
        return self.is_active and bool(self.site_url)

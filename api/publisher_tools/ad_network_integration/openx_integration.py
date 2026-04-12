# api/publisher_tools/ad_network_integration/openx_integration.py
"""OpenX integration for Publisher Tools."""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class OpenXConfig(TimeStampedModel):
    """OpenX publisher configuration."""
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="publisher_tools_openx_tenant",
        db_index=True,
    )
    publisher = models.ForeignKey(
        "publisher_tools.Publisher",
        on_delete=models.CASCADE,
        related_name="openx_configs",
    )
    is_enabled   = models.BooleanField(default=True, db_index=True)
    is_test_mode = models.BooleanField(default=False)
    del_domain = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=200, blank=True)
    extra_params = models.JSONField(default=dict, blank=True)
    daily_revenue  = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    total_revenue  = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    last_sync_at   = models.DateTimeField(null=True, blank=True)
    sync_status    = models.CharField(
        max_length=20,
        choices=[("ok","OK"),("error","Error"),("pending","Pending")],
        default="pending",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "publisher_tools_openx_configs"
        verbose_name = _("OpenX Config")
        unique_together = [["publisher"]]

    def __str__(self):
        return f"OpenX: {self.publisher.publisher_id}"

    def sync_revenue(self) -> bool:
        """Revenue data sync করে। Production-এ OpenX API call করো।"""
        import logging
        logging.getLogger(__name__).info(
            f"Syncing OpenX revenue for {self.publisher.publisher_id}"
        )
        self.last_sync_at = timezone.now()
        self.sync_status = "ok"
        self.save(update_fields=["last_sync_at", "sync_status", "updated_at"])
        return True

    def get_ad_tag(self, ad_unit_id: str) -> str:
        """Ad tag code generate করে।"""
        return f"<!-- OpenX Ad Tag — {self.publisher.publisher_id} — {ad_unit_id} -->"

    def validate_credentials(self) -> bool:
        """API credentials validate করে।"""
        required = self.del_domain, self.unit
        return all(bool(getattr(self, p, None)) for p in ['del_domain', 'unit'])

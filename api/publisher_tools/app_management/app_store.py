# api/publisher_tools/app_management/app_store.py
"""App Store — Play Store / App Store metadata sync."""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppStoreMetadata(TimeStampedModel):
    """App Store listing metadata — synced from stores."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appstore_tenant", db_index=True)
    app              = models.OneToOneField("publisher_tools.App", on_delete=models.CASCADE, related_name="store_metadata")
    store_title      = models.CharField(max_length=300, blank=True)
    store_description= models.TextField(blank=True)
    store_developer  = models.CharField(max_length=200, blank=True)
    store_rating     = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal("0.0"))
    store_review_count = models.IntegerField(default=0)
    total_downloads  = models.BigIntegerField(default=0)
    current_version  = models.CharField(max_length=20, blank=True)
    min_android_version = models.CharField(max_length=10, blank=True)
    min_ios_version  = models.CharField(max_length=10, blank=True)
    content_rating   = models.CharField(max_length=20, blank=True)
    icon_url         = models.URLField(blank=True)
    screenshots      = models.JSONField(default=list, blank=True)
    categories       = models.JSONField(default=list, blank=True)
    tags             = models.JSONField(default=list, blank=True)
    is_free          = models.BooleanField(default=True)
    price_usd        = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    has_in_app_purchases = models.BooleanField(default=False)
    has_ads          = models.BooleanField(default=False)
    last_store_sync  = models.DateTimeField(null=True, blank=True)
    sync_error       = models.TextField(blank=True)

    class Meta:
        db_table = "publisher_tools_app_store_metadata"
        verbose_name = _("App Store Metadata")

    def __str__(self):
        return f"Store: {self.app.name} v{self.current_version}"

    def sync_from_store(self):
        """Store API থেকে metadata sync করে। Production-এ google-play / apple APIs use করো।"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Syncing store metadata for {self.app.package_name}")
        self.last_store_sync = timezone.now()
        self.save(update_fields=["last_store_sync", "updated_at"])

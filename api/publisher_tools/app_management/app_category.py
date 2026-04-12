# api/publisher_tools/app_management/app_category.py
"""App Category — Mobile app category management."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AppCategory(TimeStampedModel):
    """App categories with Google Play / App Store taxonomy."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_appcat_tenant", db_index=True)
    name             = models.CharField(max_length=100, unique=True)
    slug             = models.SlugField(unique=True)
    description      = models.TextField(blank=True)
    parent           = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subcategories")
    play_store_id    = models.CharField(max_length=50, blank=True)
    app_store_id     = models.CharField(max_length=50, blank=True)
    is_game          = models.BooleanField(default=False)
    is_active        = models.BooleanField(default=True, db_index=True)
    sort_order       = models.IntegerField(default=0)
    avg_ecpm_tier    = models.CharField(max_length=10, choices=[("low","Low"),("medium","Medium"),("high","High"),("premium","Premium")], default="medium")
    best_ad_formats  = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "publisher_tools_app_categories"
        verbose_name = _("App Category")
        verbose_name_plural = _("App Categories")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent else self.name

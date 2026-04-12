# api/publisher_tools/ad_unit_management/ad_unit_model.py
"""Ad Unit Model extensions — Creative specs, SDK config."""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AdUnitCreativeSpec(TimeStampedModel):
    """Ad unit creative specifications."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_creativspec_tenant", db_index=True)
    ad_unit             = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="creative_spec")
    accepted_mime_types = models.JSONField(default=list, blank=True, help_text="['image/jpeg','image/png','video/mp4']")
    max_file_size_kb    = models.IntegerField(default=200)
    max_video_length_sec= models.IntegerField(default=30, null=True, blank=True)
    min_video_bitrate   = models.IntegerField(default=0)
    supports_html5      = models.BooleanField(default=True)
    supports_video      = models.BooleanField(default=False)
    supports_rich_media = models.BooleanField(default=False)
    supports_expandable = models.BooleanField(default=False)
    safe_frame_enabled  = models.BooleanField(default=True)
    ssl_required        = models.BooleanField(default=True)
    companion_sizes     = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "publisher_tools_ad_unit_creative_specs"
        verbose_name = _("Creative Spec")

    def __str__(self):
        return f"Spec: {self.ad_unit.unit_id}"

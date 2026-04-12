# api/publisher_tools/ad_unit_management/playable_ad_unit.py
"""Playable Ad Unit — Interactive/playable ad configuration."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PlayableAdConfig(TimeStampedModel):
    """Playable/interactive ad configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_playableconf_tenant", db_index=True)
    ad_unit            = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="playable_config")
    gameplay_duration_sec = models.IntegerField(default=30)
    end_card_duration_sec = models.IntegerField(default=5)
    cta_text           = models.CharField(max_length=50, default="Play Now!")
    cta_button_color   = models.CharField(max_length=10, default="#22c55e")
    orientation        = models.CharField(max_length=10, choices=[("portrait","Portrait"),("landscape","Landscape"),("any","Any")], default="any")
    requires_sound     = models.BooleanField(default=False)
    requires_gyroscope = models.BooleanField(default=False)
    requires_touch     = models.BooleanField(default=True)
    mraid_enabled      = models.BooleanField(default=True)
    mraid_version      = models.CharField(max_length=5, default="2.0")
    max_file_size_mb   = models.IntegerField(default=5)
    supported_formats  = models.JSONField(default=list, blank=True, help_text="['html5','unity','construct']")

    class Meta:
        db_table = "publisher_tools_playable_ad_configs"
        verbose_name = _("Playable Ad Config")

    def __str__(self):
        return f"Playable: {self.ad_unit.unit_id}"

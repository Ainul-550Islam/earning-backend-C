# api/publisher_tools/ad_unit_management/audio_ad_unit.py
"""Audio Ad Unit — Podcast and audio stream ad configuration."""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AudioAdConfig(TimeStampedModel):
    """Audio ad unit configuration for podcast/audio apps."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_audioconf_tenant", db_index=True)
    ad_unit          = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="audio_config")
    ad_position      = models.CharField(max_length=10, choices=[("pre","Pre-roll"),("mid","Mid-roll"),("post","Post-roll")], default="pre")
    min_duration_sec = models.IntegerField(default=15, validators=[MinValueValidator(5)])
    max_duration_sec = models.IntegerField(default=60, validators=[MaxValueValidator(120)])
    skippable        = models.BooleanField(default=False)
    skip_after_sec   = models.IntegerField(default=15)
    companion_banner_enabled = models.BooleanField(default=True)
    companion_size   = models.CharField(max_length=20, default="300x250")
    vast_audio_url   = models.URLField(blank=True)
    show_notification= models.BooleanField(default=True)
    notification_text= models.CharField(max_length=200, default="Ad playing...")
    max_per_content  = models.IntegerField(default=2, help_text="Max audio ads per content piece")
    min_content_length_sec = models.IntegerField(default=300, help_text="Min content length to show mid-roll")

    class Meta:
        db_table = "publisher_tools_audio_ad_configs"
        verbose_name = _("Audio Ad Config")

    def __str__(self):
        return f"Audio: {self.ad_unit.unit_id} [{self.ad_position}]"

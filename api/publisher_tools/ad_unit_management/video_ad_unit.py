# api/publisher_tools/ad_unit_management/video_ad_unit.py
"""Video Ad Unit — In-stream and out-stream video ad config."""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class VideoAdConfig(TimeStampedModel):
    """Video ad unit configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_videoconf_tenant", db_index=True)
    ad_unit           = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="video_config")
    video_type        = models.CharField(max_length=20, choices=[
        ("instream_pre","In-stream Pre-roll"),("instream_mid","In-stream Mid-roll"),
        ("instream_post","In-stream Post-roll"),("outstream","Out-stream"),
        ("sticky_video","Sticky Video"),
    ], default="outstream")
    min_duration_sec  = models.IntegerField(default=5, validators=[MinValueValidator(3)])
    max_duration_sec  = models.IntegerField(default=30, validators=[MaxValueValidator(300)])
    skippable         = models.BooleanField(default=True)
    skip_after_sec    = models.IntegerField(default=5, validators=[MinValueValidator(3)])
    autoplay          = models.BooleanField(default=True)
    autoplay_muted    = models.BooleanField(default=True)
    click_to_unmute   = models.BooleanField(default=True)
    show_countdown    = models.BooleanField(default=True)
    show_progress_bar = models.BooleanField(default=True)
    show_volume_control = models.BooleanField(default=True)
    close_button_enabled = models.BooleanField(default=False)
    vast_tag_url      = models.URLField(blank=True)
    vpaid_enabled     = models.BooleanField(default=False)
    min_viewability_pct = models.IntegerField(default=50)
    viewability_time_sec = models.IntegerField(default=2)
    player_width      = models.IntegerField(null=True, blank=True)
    player_height     = models.IntegerField(null=True, blank=True)
    player_color      = models.CharField(max_length=10, default="#000000")

    class Meta:
        db_table = "publisher_tools_video_ad_configs"
        verbose_name = _("Video Ad Config")

    def __str__(self):
        return f"Video: {self.ad_unit.unit_id} [{self.video_type}]"

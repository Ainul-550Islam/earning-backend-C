# api/publisher_tools/ad_unit_management/interstitial_ad_unit.py
"""Interstitial Ad Unit — Full-screen ad configuration."""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class InterstitialAdConfig(TimeStampedModel):
    """Interstitial full-screen ad settings."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_interstitialconf_tenant", db_index=True)
    ad_unit              = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="interstitial_config")
    show_on_app_open     = models.BooleanField(default=False)
    show_on_screen_change= models.BooleanField(default=True)
    show_on_app_close    = models.BooleanField(default=False)
    close_button_delay_sec = models.IntegerField(default=5, validators=[MinValueValidator(3), MaxValueValidator(30)])
    min_interval_between_sec = models.IntegerField(default=60, validators=[MinValueValidator(30)])
    max_per_session      = models.IntegerField(default=3)
    show_countdown_timer = models.BooleanField(default=True)
    skip_text            = models.CharField(max_length=20, default="Skip Ad")
    is_closeable         = models.BooleanField(default=True)
    overlay_color        = models.CharField(max_length=10, default="#000000")
    overlay_opacity      = models.DecimalField(max_digits=3, decimal_places=2, default=0.70)
    transition_animation = models.CharField(max_length=20, choices=[("slide","Slide"),("fade","Fade"),("zoom","Zoom")], default="fade")

    class Meta:
        db_table = "publisher_tools_interstitial_ad_configs"
        verbose_name = _("Interstitial Ad Config")

    def __str__(self):
        return f"Interstitial: {self.ad_unit.unit_id}"

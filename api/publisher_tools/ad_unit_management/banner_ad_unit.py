# api/publisher_tools/ad_unit_management/banner_ad_unit.py
"""Banner Ad Unit — Web banner specific configurations."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


STANDARD_BANNER_SIZES = {
    "leaderboard": (728, 90),
    "rectangle":   (300, 250),
    "large_rect":  (336, 280),
    "half_page":   (300, 600),
    "banner":      (320, 50),
    "billboard":   (970, 250),
    "skyscraper":  (160, 600),
}


class BannerAdConfig(TimeStampedModel):
    """Banner ad specific settings."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_bannerconf_tenant", db_index=True)
    ad_unit          = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="banner_config")
    size_preset      = models.CharField(max_length=20, choices=[(k,k.replace("_"," ").title()) for k in STANDARD_BANNER_SIZES], blank=True)
    is_sticky        = models.BooleanField(default=False)
    sticky_position  = models.CharField(max_length=10, choices=[("top","Top"),("bottom","Bottom")], default="bottom")
    auto_collapse    = models.BooleanField(default=False, help_text="Collapse when no ad fills")
    collapse_delay_ms= models.IntegerField(default=0)
    border_enabled   = models.BooleanField(default=False)
    border_color     = models.CharField(max_length=10, blank=True)
    background_color = models.CharField(max_length=10, blank=True)
    lazy_load        = models.BooleanField(default=True)
    lazy_load_offset = models.IntegerField(default=200, help_text="px from viewport")
    animate_in       = models.BooleanField(default=False)
    animation_type   = models.CharField(max_length=20, blank=True, choices=[("fade","Fade"),("slide","Slide"),("bounce","Bounce")])

    class Meta:
        db_table = "publisher_tools_banner_ad_configs"
        verbose_name = _("Banner Ad Config")

    def __str__(self):
        return f"Banner: {self.ad_unit.unit_id} {'sticky' if self.is_sticky else ''}"

    def get_size(self):
        if self.size_preset and self.size_preset in STANDARD_BANNER_SIZES:
            return STANDARD_BANNER_SIZES[self.size_preset]
        return (self.ad_unit.width, self.ad_unit.height)

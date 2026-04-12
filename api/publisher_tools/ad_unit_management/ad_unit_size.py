# api/publisher_tools/ad_unit_management/ad_unit_size.py
"""Ad Unit Size — Standard IAB sizes and custom size management."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel

IAB_STANDARD_SIZES = [
    ("300x250","Medium Rectangle"),("728x90","Leaderboard"),("160x600","Wide Skyscraper"),
    ("320x50","Mobile Banner"),("300x600","Half Page"),("970x250","Billboard"),
    ("336x280","Large Rectangle"),("468x60","Full Banner"),("234x60","Half Banner"),
    ("120x240","Vertical Banner"),("120x600","Skyscraper"),("300x1050","Portrait"),
    ("970x90","Large Leaderboard"),("250x250","Square"),("200x200","Small Square"),
]


class AdSizePreset(TimeStampedModel):
    """Standard and custom ad size presets."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_adsizepreset_tenant", db_index=True)
    name         = models.CharField(max_length=100)
    width        = models.IntegerField()
    height       = models.IntegerField()
    format_code  = models.CharField(max_length=20, blank=True)
    is_iab_standard = models.BooleanField(default=False)
    is_mobile_only  = models.BooleanField(default=False)
    is_desktop_only = models.BooleanField(default=False)
    supports_responsive = models.BooleanField(default=True)
    is_active    = models.BooleanField(default=True)
    description  = models.TextField(blank=True)
    avg_ecpm_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.00, help_text="vs baseline eCPM")

    class Meta:
        db_table = "publisher_tools_ad_size_presets"
        verbose_name = _("Ad Size Preset")
        ordering = ["-is_iab_standard", "name"]

    def __str__(self):
        return f"{self.name} ({self.width}x{self.height})"

    @property
    def aspect_ratio(self):
        from math import gcd
        g = gcd(self.width, self.height)
        return f"{self.width//g}:{self.height//g}"

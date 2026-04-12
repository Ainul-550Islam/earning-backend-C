# api/publisher_tools/ad_unit_management/native_ad_unit.py
"""Native Ad Unit — Native ad template and style configuration."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class NativeAdConfig(TimeStampedModel):
    """Native ad appearance and content settings."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_nativeconf_tenant", db_index=True)
    ad_unit           = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="native_config")
    template_type     = models.CharField(max_length=20, choices=[
        ("small","Small — Icon + Title + CTA"),
        ("medium","Medium — Image + Title + Description + CTA"),
        ("large","Large — Full Width Image + All Elements"),
        ("content","Content Stream — Matches Feed Style"),
        ("custom","Custom HTML Template"),
    ], default="medium")
    show_app_icon     = models.BooleanField(default=True)
    show_advertiser   = models.BooleanField(default=True)
    show_headline     = models.BooleanField(default=True)
    show_description  = models.BooleanField(default=True)
    show_cta_button   = models.BooleanField(default=True)
    show_rating       = models.BooleanField(default=False)
    show_image        = models.BooleanField(default=True)
    show_ad_badge     = models.BooleanField(default=True)
    ad_badge_text     = models.CharField(max_length=20, default="Ad")
    ad_badge_color    = models.CharField(max_length=10, default="#f59e0b")
    cta_button_color  = models.CharField(max_length=10, default="#2563eb")
    cta_button_text_color = models.CharField(max_length=10, default="#ffffff")
    custom_css        = models.TextField(blank=True)
    custom_template   = models.TextField(blank=True)
    card_border_radius= models.IntegerField(default=8)
    padding_px        = models.IntegerField(default=12)
    font_family       = models.CharField(max_length=100, default="inherit")
    headline_font_size= models.IntegerField(default=14)
    description_font_size = models.IntegerField(default=12)
    max_in_feed_count = models.IntegerField(default=3, help_text="Max native ads in a content feed")

    class Meta:
        db_table = "publisher_tools_native_ad_configs"
        verbose_name = _("Native Ad Config")

    def __str__(self):
        return f"Native: {self.ad_unit.unit_id} [{self.template_type}]"

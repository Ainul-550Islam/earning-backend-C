# api/publisher_tools/ad_unit_management/offerwall_unit.py
"""Offerwall Ad Unit — Offerwall specific configuration."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class OfferwallAdConfig(TimeStampedModel):
    """Offerwall settings and offer display config."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_offerwallconf_tenant", db_index=True)
    ad_unit              = models.OneToOneField("publisher_tools.AdUnit", on_delete=models.CASCADE, related_name="offerwall_config")
    currency_name        = models.CharField(max_length=50, default="Coins")
    exchange_rate        = models.DecimalField(max_digits=10, decimal_places=4, default=1.0, help_text="1 USD = X coins")
    show_currency_balance= models.BooleanField(default=True)
    default_offer_sort   = models.CharField(max_length=20, choices=[("reward_desc","Highest Reward"),("newest","Newest"),("easiest","Easiest"),("featured","Featured First")], default="featured")
    filter_by_country    = models.BooleanField(default=True)
    filter_by_device     = models.BooleanField(default=True)
    show_featured_first  = models.BooleanField(default=True)
    offer_categories     = models.JSONField(default=list, blank=True)
    min_offer_reward     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_offers_shown     = models.IntegerField(default=50)
    enable_search        = models.BooleanField(default=True)
    enable_filters       = models.BooleanField(default=True)
    theme_color          = models.CharField(max_length=10, default="#2563eb")
    logo_url             = models.URLField(blank=True)
    header_text          = models.CharField(max_length=200, blank=True)
    empty_state_text     = models.CharField(max_length=300, default="No offers available in your region. Check back later!")
    postback_url         = models.URLField(blank=True)
    postback_secret      = models.CharField(max_length=100, blank=True)
    server_side_credit   = models.BooleanField(default=True)

    class Meta:
        db_table = "publisher_tools_offerwall_ad_configs"
        verbose_name = _("Offerwall Config")

    def __str__(self):
        return f"Offerwall: {self.ad_unit.unit_id} — {self.currency_name}"

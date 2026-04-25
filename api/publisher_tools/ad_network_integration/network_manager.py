# api/publisher_tools/ad_network_integration/network_manager.py
"""Ad Network Manager — Central network management and configuration."""
from decimal import Decimal
from typing import List, Dict, Optional
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class AdNetworkConfig(TimeStampedModel):
    """Publisher-specific ad network configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_networkconf_tenant", db_index=True)
    publisher         = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="network_configs", db_index=True)
    network           = models.ForeignKey("ad_networks.AdNetwork", on_delete=models.CASCADE, related_name="publisher_configs")
    is_enabled        = models.BooleanField(default=True, db_index=True)
    publisher_app_id  = models.CharField(max_length=200, blank=True)
    publisher_api_key = models.CharField(max_length=255, blank=True)
    publisher_secret  = models.CharField(max_length=255, blank=True)
    account_id        = models.CharField(max_length=100, blank=True)
    extra_params      = models.JSONField(default=dict, blank=True)
    revenue_share_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_test_mode      = models.BooleanField(default=False)
    last_sync_at      = models.DateTimeField(null=True, blank=True)
    total_revenue     = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    total_impressions = models.BigIntegerField(default=0)

    class Meta:
        db_table = "publisher_tools_ad_network_configs"
        verbose_name = _("Ad Network Config")
        unique_together = [["publisher", "network"]]
        indexes = [
            models.Index(fields=["publisher", "is_enabled"], name='idx_publisher_is_enabled_1533'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.network.name} [{'on' if self.is_enabled else 'off'}]"


def get_enabled_networks(publisher) -> List:
    """Publisher-এর সব enabled networks।"""
    return list(
        AdNetworkConfig.objects.filter(publisher=publisher, is_enabled=True)
        .select_related("network").order_by("-total_revenue")
    )


def get_network_performance(publisher, days: int = 30) -> List[Dict]:
    """Network performance comparison।"""
    from api.publisher_tools.models import PublisherEarning
    from datetime import timedelta
    from django.db.models import Sum, Avg
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(
            publisher=publisher, date__gte=start, network__isnull=False,
        ).values("network__name", "network__network_type").annotate(
            revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
            ecpm=Avg("ecpm"), fill_rate=Avg("fill_rate"),
        ).order_by("-revenue")
    )


def recommend_networks(publisher, ad_format: str) -> List[Dict]:
    """Publisher-এর জন্য network recommendations।"""
    recommendations = {
        "banner":       ["admob", "applovin", "facebook_audience", "unity"],
        "interstitial": ["admob", "applovin", "ironsource", "unity"],
        "rewarded_video":["applovin", "ironsource", "unity", "vungle"],
        "native":       ["admob", "facebook_audience", "applovin"],
        "offerwall":    ["tapjoy", "ironsource", "fyber"],
    }
    suggested_types = recommendations.get(ad_format, ["admob"])
    return [{"network_type": t, "reason": f"Top performer for {ad_format} ads"} for t in suggested_types]

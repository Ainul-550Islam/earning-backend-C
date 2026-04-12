# api/publisher_tools/mediation_management/header_bidding_manager.py
"""Header Bidding Manager — Prebid.js and server-side bidding management."""
from decimal import Decimal
from typing import List, Dict
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class PrebidConfig(TimeStampedModel):
    """Global Prebid.js configuration."""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_prebidconf_tenant", db_index=True)
    publisher         = models.OneToOneField("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="prebid_config")
    prebid_version    = models.CharField(max_length=10, default="8.0")
    global_timeout_ms = models.IntegerField(default=1000)
    price_granularity = models.CharField(max_length=10, choices=[("low","Low"),("medium","Medium"),("high","High"),("auto","Auto"),("dense","Dense")], default="medium")
    send_all_bids     = models.BooleanField(default=False)
    enable_user_sync  = models.BooleanField(default=True)
    user_sync_delay   = models.IntegerField(default=3000)
    enable_gdpr       = models.BooleanField(default=True)
    enable_ccpa       = models.BooleanField(default=False)
    enable_usp        = models.BooleanField(default=False)
    enable_gpp        = models.BooleanField(default=False)
    currency_module   = models.BooleanField(default=True)
    ad_server_currency= models.CharField(max_length=5, default="USD")
    enable_floors     = models.BooleanField(default=True)
    floors_config     = models.JSONField(default=dict, blank=True)
    enable_analytics  = models.BooleanField(default=True)
    analytics_adapter = models.CharField(max_length=50, blank=True, default="ga")
    custom_config     = models.JSONField(default=dict, blank=True)
    is_active         = models.BooleanField(default=True)

    class Meta:
        db_table = "publisher_tools_prebid_configs"
        verbose_name = _("Prebid Config")

    def __str__(self):
        return f"Prebid v{self.prebid_version}: {self.publisher.publisher_id}"

    def generate_config_js(self) -> str:
        return f"""pbjs.setConfig({{
  bidderTimeout: {self.global_timeout_ms},
  priceGranularity: "{self.price_granularity}",
  enableSendAllBids: {"true" if self.send_all_bids else "false"},
  currency: {{ adServerCurrency: "{self.ad_server_currency}" }},
  userSync: {{ syncEnabled: {"true" if self.enable_user_sync else "false"}, syncDelay: {self.user_sync_delay} }},
}});"""


def get_bidder_configurations(group) -> List[Dict]:
    """Mediation group-এর active header bidding configs।"""
    from api.publisher_tools.models import HeaderBiddingConfig
    configs = HeaderBiddingConfig.objects.filter(
        mediation_group=group, status="active",
    ).select_related()
    return [
        {
            "bidder": c.bidder_name, "type": c.bidder_type,
            "params": c.bidder_params, "timeout_ms": c.timeout_ms,
            "floor": float(c.price_floor),
        }
        for c in configs
    ]


def calculate_bid_win_rate(config) -> float:
    if config.total_bid_responses > 0:
        return round(config.total_bid_wins / config.total_bid_responses * 100, 2)
    return 0.0


def get_header_bidding_report(publisher, days: int = 30) -> Dict:
    from api.publisher_tools.models import HeaderBiddingConfig
    from django.db.models import Sum, Avg
    from datetime import timedelta
    from django.utils import timezone
    configs = HeaderBiddingConfig.objects.filter(
        mediation_group__ad_unit__publisher=publisher, status="active",
    )
    return {
        "total_bidders":    configs.count(),
        "total_bid_requests":  sum(c.total_bid_requests for c in configs),
        "total_bid_wins":   sum(c.total_bid_wins for c in configs),
        "total_revenue":    float(sum(c.total_revenue for c in configs)),
        "bidders": [
            {"name": c.bidder_name, "wins": c.total_bid_wins, "revenue": float(c.total_revenue), "avg_cpm": float(c.avg_bid_cpm)}
            for c in configs
        ],
    }

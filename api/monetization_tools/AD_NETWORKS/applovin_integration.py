"""AD_NETWORKS/applovin_integration.py — AppLovin MAX integration."""
import logging
from decimal import Decimal
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class AppLovinIntegration:
    NETWORK_TYPE = "applovin"
    REPORTING_URL = "https://r.applovin.com/report"

    def __init__(self, network: AdNetwork):
        self.network = network
        self.sdk_key = network.api_key or ""
        self.report_key = network.reporting_api_key or ""

    def build_reporting_url(self, date_str: str) -> str:
        return (f"{self.REPORTING_URL}?api_key={self.report_key}"
                f"&start={date_str}&end={date_str}&columns=day,earnings,impressions,ecpm")

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("AppLovin: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0, "ecpm": "0"}

    def get_max_sdk_config(self) -> dict:
        return {"sdk_key": self.sdk_key, "network": "applovin"}

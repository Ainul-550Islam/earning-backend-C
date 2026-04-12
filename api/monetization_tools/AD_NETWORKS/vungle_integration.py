"""AD_NETWORKS/vungle_integration.py — Vungle / Liftoff integration."""
import logging
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class VungleIntegration:
    NETWORK_TYPE = "vungle"
    REPORT_URL   = "https://report.api.vungle.com/ext/pub/reports/performance"

    def __init__(self, network: AdNetwork):
        self.network = network
        self.api_key = network.api_key or ""
        self.app_id  = network.app_id or ""

    def get_auth_header(self) -> dict:
        return {"Vungle-Version": "1", "Authorization": f"Bearer {self.api_key}"}

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("Vungle: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0, "ecpm": "0"}

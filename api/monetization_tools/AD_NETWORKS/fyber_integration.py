"""AD_NETWORKS/fyber_integration.py — Fyber / Digital Turbine integration."""
import logging
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class FyberIntegration:
    NETWORK_TYPE  = "fyber"
    REPORT_URL    = "https://reporting.fyber.com/api/v1/publisher/report"

    def __init__(self, network: AdNetwork):
        self.network  = network
        self.api_key  = network.api_key or ""
        self.app_id   = network.app_id or ""

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("Fyber: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0}

    def validate_s2s_callback(self, uid: str, sid: str,
                               pub_sig: str) -> bool:
        import hashlib
        raw = f"{uid}{sid}{self.network.secret_key or ''}"
        return hashlib.sha1(raw.encode()).hexdigest() == pub_sig

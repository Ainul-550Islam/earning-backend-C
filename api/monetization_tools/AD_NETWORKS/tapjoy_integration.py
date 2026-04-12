"""AD_NETWORKS/tapjoy_integration.py — Tapjoy offerwall integration."""
import logging
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class TapjoyIntegration:
    NETWORK_TYPE = "tapjoy"
    POSTBACK_PARAM = "snuid"

    def __init__(self, network: AdNetwork):
        self.network   = network
        self.api_key   = network.api_key or ""
        self.secret    = network.secret_key or ""

    def validate_postback(self, user_id: str, currency: str,
                           amount: str, sig: str) -> bool:
        import hashlib
        payload = f"{user_id}{currency}{amount}{self.secret}"
        expected = hashlib.md5(payload.encode()).hexdigest()
        return expected == sig

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("Tapjoy: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "offers_completed": 0}

    def build_offer_url(self, uid: str, device: str = "android") -> str:
        return (f"https://offerwall.tapjoy.com/wall?sdk_key={self.api_key}"
                f"&uid={uid}&device={device}")

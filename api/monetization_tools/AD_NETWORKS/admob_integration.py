"""AD_NETWORKS/admob_integration.py — Google AdMob integration."""
import logging
from decimal import Decimal
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class AdMobIntegration:
    NETWORK_TYPE = "admob"

    def __init__(self, network: AdNetwork):
        self.network  = network
        self.app_id   = network.app_id or ""
        self.api_key  = network.api_key or ""

    def get_ad_request_url(self, unit_id: str, format: str = "banner") -> str:
        return f"https://admob.googleapis.com/v1/accounts/{self.app_id}/adUnits/{unit_id}"

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("AdMob: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0, "ecpm": "0"}

    def validate_postback(self, payload: dict, signature: str) -> bool:
        from ..utils import verify_hmac_signature
        secret = self.network.postback_secret or ""
        import json
        return verify_hmac_signature(json.dumps(payload, sort_keys=True), signature, secret)

    def get_floor_ecpm(self) -> Decimal:
        return self.network.floor_ecpm

"""AD_NETWORKS/facebook_audience.py — Meta Audience Network integration."""
import logging
from decimal import Decimal
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class FacebookAudienceNetwork:
    NETWORK_TYPE = "facebook"

    def __init__(self, network: AdNetwork):
        self.network = network
        self.app_id  = network.app_id or ""
        self.token   = network.api_key or ""

    def get_placement_id(self, unit_name: str) -> str:
        return f"{self.app_id}_{unit_name}"

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("Facebook AN: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0}

    def build_bid_request(self, placement_id: str, user_data: dict) -> dict:
        return {
            "placement_id": placement_id,
            "format": "native",
            "user": {"country": user_data.get("country", "")},
        }

    def validate_signature(self, payload: str, sig: str) -> bool:
        import hmac, hashlib
        expected = hmac.new(
            self.network.postback_secret.encode() if self.network.postback_secret else b"",
            payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

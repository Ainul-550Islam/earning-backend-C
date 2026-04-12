"""AD_NETWORKS/unity_ads_integration.py — Unity Ads integration."""
import logging
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class UnityAdsIntegration:
    NETWORK_TYPE = "unity"
    STATS_URL = "https://stats.unityads.unity3d.com/organizations"

    def __init__(self, network: AdNetwork):
        self.network  = network
        self.game_id  = network.app_id or ""
        self.api_key  = network.api_key or ""
        self.org_id   = network.extra_config.get("org_id", "") if network.extra_config else ""

    def get_placement_config(self, placement_id: str) -> dict:
        return {"placementId": placement_id, "gameId": self.game_id}

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("Unity: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0}

    def validate_postback(self, sid: str, hmac_sig: str) -> bool:
        import hmac as _hmac, hashlib
        secret = self.network.postback_secret or ""
        expected = _hmac.new(secret.encode(), sid.encode(), hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, hmac_sig)

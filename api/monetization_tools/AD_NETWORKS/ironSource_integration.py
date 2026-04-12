"""AD_NETWORKS/ironSource_integration.py — IronSource integration."""
import logging
from ..models import AdNetwork

logger = logging.getLogger(__name__)

class IronSourceIntegration:
    NETWORK_TYPE = "ironsource"
    REPORT_URL   = "https://platform.ironsrc.com/partners/publisher/mediation/management/api"

    def __init__(self, network: AdNetwork):
        self.network    = network
        self.secret_key = network.secret_key or ""
        self.app_key    = network.app_id or ""

    def get_auth_header(self) -> dict:
        import base64
        creds = base64.b64encode(
            f"{self.network.api_key or ''}:{self.secret_key}".encode()
        ).decode()
        return {"Authorization": f"Basic {creds}"}

    def fetch_reporting(self, date_str: str) -> dict:
        logger.info("IronSource: fetching report for %s", date_str)
        return {"date": date_str, "revenue": "0", "impressions": 0}

    def validate_postback(self, params: dict, sig: str) -> bool:
        import hmac, hashlib
        payload = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        expected = hmac.new(
            self.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, sig)

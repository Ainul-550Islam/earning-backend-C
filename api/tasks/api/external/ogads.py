"""
api/external/ogads.py
OGAds API client.
Docs: https://ogads.com/developers/
Required env: OGADS_API_KEY, OGADS_PUB_ID
Postback params: click_id, offer_id, payout, ip, status (approved|reversed)
"""
import logging, requests
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://ogads.com/api"

def get_offers(pub_id: str, country: str = "US", os_filter: str = "all", limit: int = 50) -> list:
    try:
        r = requests.get(
            f"{BASE_URL}/offers",
            params={"api_key": getattr(settings, "OGADS_API_KEY", ""),
                    "pub_id": pub_id, "country": country,
                    "os": os_filter, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data.get("offers", []))
    except Exception as e:
        logger.error("[OGAds] get_offers error: %s", e)
        return []

def verify_postback_ip(ip: str) -> bool:
    """OGAds whitelisted postback IPs (update periodically from their docs)."""
    OGADS_IPS = {"52.200.79.48", "54.85.87.20", "54.173.229.200"}
    return ip in OGADS_IPS

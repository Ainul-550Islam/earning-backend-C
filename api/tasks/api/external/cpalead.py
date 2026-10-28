"""
api/external/cpalead.py
CPAlead API client.
Docs: https://cpalead.com/dashboard/reports/campaign_serv.php
Required env: CPALEAD_API_KEY, CPALEAD_PUB_ID
"""
import logging, os, requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://cpalead.com/api/v2"

def get_offers(pub_id: str, country: str = "US", limit: int = 50) -> list:
    try:
        r = requests.get(
            f"{BASE_URL}/offers",
            params={"apikey": getattr(settings, "CPALEAD_API_KEY", ""), "pub_id": pub_id,
                    "country": country, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("offers", data.get("data", []))
    except Exception as e:
        logger.error("[CPAlead] get_offers error: %s", e)
        return []

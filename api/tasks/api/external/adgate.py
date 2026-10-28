"""
api/external/adgate.py
AdGate Media API client.
Docs: https://adgatemedia.com/publishers/api/
Required env: ADGATE_API_KEY, ADGATE_WALL_ID
Postback params: user_id, amount, currency, offer_id, transaction_id
Security: HMAC-SHA256 token verification
"""
import logging, hashlib, hmac, requests
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://adgatemedia.com/api/v1"

def get_offers(wall_id: str, country: str = "US", limit: int = 50) -> list:
    try:
        r = requests.get(
            f"{BASE_URL}/offers",
            params={"wall_id": wall_id,
                    "api_key": getattr(settings, "ADGATE_API_KEY", ""),
                    "country": country, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("offers", data.get("data", []))
    except Exception as e:
        logger.error("[AdGate] get_offers error: %s", e)
        return []

def verify_postback_token(user_id: str, amount: str, transaction_id: str, token: str) -> bool:
    """Verify AdGate postback HMAC-SHA256 signature."""
    secret = getattr(settings, "ADGATE_SECRET", "")
    expected = hmac.new(
        secret.encode(), f"{user_id}:{amount}:{transaction_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, token)

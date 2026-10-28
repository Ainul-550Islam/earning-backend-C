"""
api/external/monlix.py
Monlix API client.
Docs: https://monlix.com/publishers/api/
Required env: MONLIX_APP_ID, MONLIX_API_KEY
Offer types: cpa, cpi, survey, cpe (Cost Per Engagement)
Postback: userid, amount, app_id, offer_id, transaction_id, type
Security: IP whitelist + HMAC token
"""
import logging, hashlib, hmac, requests
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://api.monlix.com/v1"

MONLIX_POSTBACK_IPS = {
    "185.254.26.0/24",  # update from Monlix dashboard
}

def get_offers(app_id: str, api_key: str, user_id: str,
               ip: str, country: str = "US", limit: int = 50) -> list:
    """
    Returns offer list for the given user. country & ip are used for geo-targeting.
    offer dict keys: offer_id, title, description, payout, currency,
                     type (cpa/cpi/survey/cpe), requirements, image_url,
                     time_estimate (minutes), countries[]
    """
    try:
        r = requests.get(
            f"{BASE_URL}/offers",
            params={"app_id": app_id, "api_key": api_key,
                    "user_id": user_id, "ip": ip,
                    "country": country, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("offers", data.get("offers", []))
    except Exception as e:
        logger.error("[Monlix] get_offers error: %s", e)
        return []

def verify_postback_token(user_id: str, amount: str, app_id: str, token: str) -> bool:
    """Monlix: HMAC-SHA256(user_id + amount + app_id, api_key)"""
    api_key = getattr(settings, "MONLIX_API_KEY", "")
    expected = hmac.new(
        api_key.encode(), f"{user_id}{amount}{app_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, token)

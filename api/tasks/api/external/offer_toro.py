"""
api/external/offer_toro.py
OfferToro API client.
Docs: https://www.offertoro.com/publishers/tools/api
Required env: OFFERTORO_APP_ID, OFFERTORO_SECRET
Postback params: userId, amount, token, transactionId, offerId
Security: token = MD5(userId + amount + secret)
"""
import logging, hashlib, requests
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://www.offertoro.com/api"

def get_offers(app_id: str, pub_id: str, user_id: str, country: str = "US") -> list:
    try:
        r = requests.get(
            f"{BASE_URL}/served/offers/",
            params={"app_id": app_id, "pub_id": pub_id,
                    "user_id": user_id, "country": country},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", {}).get("data", data.get("data", []))
    except Exception as e:
        logger.error("[OfferToro] get_offers error: %s", e)
        return []

def verify_postback_token(user_id: str, amount: str, token: str) -> bool:
    """OfferToro: token = MD5(userId + amount + secret)"""
    secret = getattr(settings, "OFFERTORO_SECRET", "")
    expected = hashlib.md5(f"{user_id}{amount}{secret}".encode()).hexdigest()
    return expected == token

# api/wallet/integration/rocket_integration.py
"""Rocket MFS (Bangladesh) payout integration."""
import logging, requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.integration.rocket")

class RocketService:
    BASE_URL   = getattr(settings, "ROCKET_BASE_URL", "https://api.rocket.com.bd/v1")
    API_KEY    = getattr(settings, "ROCKET_API_KEY", "")
    API_SECRET = getattr(settings, "ROCKET_API_SECRET", "")
    TIMEOUT    = 30

    @classmethod
    def _headers(cls) -> dict:
        import hashlib, time
        ts   = str(int(time.time()))
        sign = hashlib.sha256(f"{cls.API_KEY}{ts}{cls.API_SECRET}".encode()).hexdigest()
        return {"X-API-Key": cls.API_KEY, "X-Timestamp": ts,
                "X-Signature": sign, "Content-Type": "application/json"}

    @classmethod
    def disburse(cls, receiver_mobile: str, amount: Decimal,
                 reference: str = "", remarks: str = "Payout") -> dict:
        import re
        cleaned = re.sub(r"[\s\-\+]", "", str(receiver_mobile))
        if cleaned.startswith("880"): cleaned = "0" + cleaned[3:]
        payload = {"receiver": cleaned, "amount": str(amount),
                   "currency": "BDT", "reference": reference[:50], "remarks": remarks[:100]}
        try:
            resp = requests.post(f"{cls.BASE_URL}/b2c/disburse", json=payload,
                                  headers=cls._headers(), timeout=cls.TIMEOUT)
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return {"success": True, "trxID": data.get("trxID",""), "data": data}
            return {"success": False, "error": data.get("message","Unknown"), "data": data}
        except Exception as e:
            logger.error(f"Rocket disburse error: {e}")
            return {"success": False, "error": str(e)}

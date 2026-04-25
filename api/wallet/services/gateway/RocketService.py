# api/wallet/services/gateway/RocketService.py
"""Rocket MFS payout service."""
import logging
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger("wallet.gateway.rocket")

class RocketService:
    BASE_URL   = getattr(settings, "ROCKET_BASE_URL", "https://api.rocket.com.bd/v1")
    API_KEY    = getattr(settings, "ROCKET_API_KEY", "")
    API_SECRET = getattr(settings, "ROCKET_API_SECRET", "")

    @classmethod
    def disburse(cls, receiver_mobile: str, amount: Decimal, reference: str = "") -> dict:
        from ..integration.rocket_integration import RocketService as RS
        return RS.disburse(receiver_mobile, amount, reference)

    @classmethod
    def validate_number(cls, number: str) -> bool:
        import re
        cleaned = re.sub(r"[\s\-\+]","",str(number))
        if cleaned.startswith("880"): cleaned = "0" + cleaned[3:]
        return bool(re.match(r"^01[3-9]\d{8}$", cleaned))

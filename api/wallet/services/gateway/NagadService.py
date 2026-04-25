# api/wallet/services/gateway/NagadService.py
"""
Nagad disbursement service.
Docs: https://nagad.com.bd/developer-api
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.gateway.nagad")


class NagadService:
    """Nagad B2C (Business to Customer) payout."""

    BASE_URL    = getattr(settings, "NAGAD_BASE_URL", "https://api.mynagad.com/api")
    MERCHANT_ID = getattr(settings, "NAGAD_MERCHANT_ID", "")
    MERCHANT_KEY = getattr(settings, "NAGAD_MERCHANT_KEY", "")
    PUBLIC_KEY  = getattr(settings, "NAGAD_PUBLIC_KEY", "")
    PRIVATE_KEY = getattr(settings, "NAGAD_PRIVATE_KEY", "")
    TIMEOUT     = 30

    @classmethod
    def _headers(cls) -> dict:
        return {
            "X-KM-Api-Version": "v-0.2.0",
            "X-KM-Client-Type": "PC_WEB",
            "Content-Type":     "application/json",
        }

    @classmethod
    def disburse(cls, receiver_mobile: str, amount: Decimal,
                 invoice: str = "", description: str = "Payout") -> dict:
        """
        B2C disbursement to Nagad account.
        """
        import uuid, json, base64
        order_id = invoice or str(uuid.uuid4())

        payload = {
            "merchantId":      cls.MERCHANT_ID,
            "orderId":         order_id,
            "amount":          str(amount),
            "currencyCode":    "050",   # BDT
            "challenge":       str(uuid.uuid4()),
            "receiver":        receiver_mobile,
            "description":     description[:100],
        }
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/dfs/check-out/initialize",
                json=payload,
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            if data.get("reason") == "Successful":
                return {"success": True, "trxID": data.get("merchantInvoiceNumber",""), "data": data}
            return {"success": False, "error": data.get("reason","Unknown"), "data": data}
        except Exception as e:
            logger.error(f"Nagad disburse error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def validate_number(cls, number: str) -> bool:
        import re
        cleaned = re.sub(r"[\s\-\+]","",str(number))
        if cleaned.startswith("880"): cleaned = "0" + cleaned[3:]
        return bool(re.match(r"^01[3-9]\d{8}$", cleaned))

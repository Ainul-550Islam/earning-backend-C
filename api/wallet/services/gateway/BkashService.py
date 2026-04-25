# api/wallet/services/gateway/BkashService.py
"""
bKash B2C (Business to Customer) payout service.
Docs: https://developer.bka.sh/
Supports: bKash B2C API, bKash Checkout API
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.gateway.bkash")


class BkashService:
    """bKash B2C Disbursement API."""

    BASE_URL   = getattr(settings, "BKASH_BASE_URL", "https://tokenized.sandbox.bka.sh/v1.2.0-beta")
    APP_KEY    = getattr(settings, "BKASH_APP_KEY", "")
    APP_SECRET = getattr(settings, "BKASH_APP_SECRET", "")
    USERNAME   = getattr(settings, "BKASH_USERNAME", "")
    PASSWORD   = getattr(settings, "BKASH_PASSWORD", "")
    TIMEOUT    = 30

    _token     = None
    _token_type = None

    @classmethod
    def _get_token(cls) -> str:
        """Get bKash auth token."""
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/tokenized/checkout/token/grant",
                json={"app_key": cls.APP_KEY, "app_secret": cls.APP_SECRET},
                headers={
                    "username": cls.USERNAME,
                    "password": cls.PASSWORD,
                    "Content-Type": "application/json",
                },
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            cls._token      = data.get("id_token")
            cls._token_type = data.get("token_type", "Bearer")
            return cls._token
        except Exception as e:
            logger.error(f"bKash token error: {e}")
            return ""

    @classmethod
    def _headers(cls) -> dict:
        token = cls._get_token()
        return {
            "Authorization": f"{cls._token_type} {token}",
            "X-APP-Key":     cls.APP_KEY,
            "Content-Type":  "application/json",
        }

    @classmethod
    def disburse(cls, receiver_msisdn: str, amount: Decimal,
                 reference: str = "", remarks: str = "Payout") -> dict:
        """
        B2C disbursement to a bKash account.
        Returns: {"success": bool, "trxID": str, "status": str, "error": str}
        """
        payload = {
            "amount":          str(amount),
            "currency":        "BDT",
            "intent":          "B2C",
            "merchantInvoiceNumber": reference[:50] if reference else "",
            "receiver_msisdn": receiver_msisdn,
            "remarks":         remarks[:50],
        }
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/tokenized/checkout/b2cPayment",
                json=payload,
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            logger.info(f"bKash B2C: {receiver_msisdn} {amount} → {data.get('statusMessage')}")
            if data.get("statusCode") == "0000":
                return {"success": True, "trxID": data.get("trxID",""), "status": data.get("statusMessage","")}
            return {"success": False, "error": data.get("statusMessage", "Unknown error"), "data": data}
        except Exception as e:
            logger.error(f"bKash disburse error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def check_status(cls, trx_id: str) -> dict:
        """Check status of a B2C transaction."""
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/tokenized/checkout/b2cPayment/queryPayment",
                json={"merchantInvoiceNumber": trx_id},
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def validate_number(cls, number: str) -> bool:
        """Validate bKash number format: 01XXXXXXXXX."""
        import re
        cleaned = re.sub(r"[\s\-\+]", "", str(number))
        if cleaned.startswith("880"): cleaned = "0" + cleaned[3:]
        return bool(re.match(r"^01[3-9]\d{8}$", cleaned))

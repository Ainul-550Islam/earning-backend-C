# api/wallet/services/gateway/UpayService.py
"""
Upay MFS (United Commercial Bank) gateway integration.
Bangladesh 2025: Upay is growing as 4th major MFS provider.
"""
import logging
import requests
import hashlib
import time
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.gateway.upay")


class UpayService:
    """Upay MFS payout service."""

    BASE_URL   = getattr(settings, "UPAY_BASE_URL",   "https://api.upay.com.bd/v1")
    API_KEY    = getattr(settings, "UPAY_API_KEY",    "")
    API_SECRET = getattr(settings, "UPAY_API_SECRET", "")
    TIMEOUT    = 30

    @classmethod
    def _headers(cls) -> dict:
        """Generate authenticated headers."""
        timestamp = str(int(time.time()))
        signature = hashlib.sha256(
            (cls.API_KEY + timestamp + cls.API_SECRET).encode()
        ).hexdigest()
        return {
            "X-API-Key":    cls.API_KEY,
            "X-Timestamp":  timestamp,
            "X-Signature":  signature,
            "Content-Type": "application/json",
        }

    @classmethod
    def validate_number(cls, number: str) -> bool:
        """Validate Bangladesh mobile number for Upay."""
        import re
        cleaned = "".join(c for c in str(number) if c.isdigit() or c == "+")
        if cleaned.startswith("880"):
            cleaned = "0" + cleaned[3:]
        elif cleaned.startswith("+880"):
            cleaned = "0" + cleaned[4:]
        return bool(re.match("^01[3-9][0-9]{8}$", cleaned))

    @classmethod
    def normalize_number(cls, number: str) -> str:
        """Normalize to 01XXXXXXXXX format."""
        cleaned = "".join(c for c in str(number) if c.isdigit() or c == "+")
        if cleaned.startswith("+880"):
            cleaned = "0" + cleaned[4:]
        elif cleaned.startswith("880"):
            cleaned = "0" + cleaned[3:]
        return cleaned

    @classmethod
    def verify_account(cls, mobile: str) -> dict:
        """Verify a Upay account exists before disbursement."""
        if not cls.API_KEY:
            return {"verified": True, "note": "Upay not configured"}
        mobile = cls.normalize_number(mobile)
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/account/verify",
                json={"mobile": mobile},
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            return {
                "verified":     data.get("status") == "SUCCESS",
                "account_name": data.get("name", ""),
                "mobile":       mobile,
            }
        except Exception as e:
            logger.error(f"Upay verify error: {e}")
            return {"verified": False, "error": str(e)}

    @classmethod
    def disburse(cls, receiver_mobile: str, amount: Decimal,
                 reference: str = "", remarks: str = "Payout") -> dict:
        """Disburse funds to a Upay mobile account (B2C)."""
        if not cls.API_KEY:
            return {
                "success": False,
                "error":   "Upay not configured. Set UPAY_API_KEY in settings.",
            }

        mobile = cls.normalize_number(receiver_mobile)
        if not cls.validate_number(mobile):
            return {"success": False, "error": f"Invalid Upay number: {mobile}"}

        if amount < Decimal("10"):
            return {"success": False, "error": "Minimum 10 BDT"}

        payload = {
            "receiver":  mobile,
            "amount":    str(amount),
            "currency":  "BDT",
            "reference": str(reference)[:50],
            "remarks":   str(remarks)[:100],
        }

        try:
            resp = requests.post(
                f"{cls.BASE_URL}/b2c/disburse",
                json=payload,
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            if data.get("status") == "SUCCESS":
                logger.info(f"Upay disburse OK: {mobile} {amount} BDT")
                return {"success": True, "trxID": data.get("trxID", ""), "data": data}
            error_msg = data.get("message") or "Disbursement failed"
            logger.warning(f"Upay disburse failed: {error_msg}")
            return {"success": False, "error": error_msg, "data": data}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Upay timeout"}
        except Exception as e:
            logger.error(f"Upay error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @classmethod
    def check_transaction(cls, trx_id: str) -> dict:
        """Check status of a Upay transaction."""
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/transaction/{trx_id}",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

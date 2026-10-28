# api/wallet/bb_iips_integration.py
"""
Bangladesh Bank IIPS (Inclusive Instant Payment System) integration.
Bangladesh Bank Roadmap 2027: Full IIPS rollout by July 2027.
IIPS = Bangladesh's UPI-equivalent instant payment infrastructure.

Current status (2025): Bangladesh Bank piloting IIPS.
This file prepares the integration for when IIPS goes live.

Reference: https://polygontechnology.io/bangladesh-banks-digital-finance-reforms-by-2027/
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.bb_iips")


class BBIIPSService:
    """
    Bangladesh Bank IIPS integration.
    Allows instant payment between any bank/MFS account in Bangladesh.
    Similar to India's UPI system.
    
    Status: READY — activate when BB IIPS goes live (expected 2026-2027)
    """

    BASE_URL = getattr(settings, "BB_IIPS_BASE_URL",  "https://iips.bb.org.bd/api/v1")
    API_KEY  = getattr(settings, "BB_IIPS_API_KEY",   "")
    TIMEOUT  = 15

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.API_KEY)

    @classmethod
    def initiate_payment(cls, sender_account: str, receiver_account: str,
                          amount: Decimal, reference: str = "",
                          remarks: str = "Wallet payout") -> dict:
        """
        Initiate IIPS instant payment.
        sender_account: VPA (Virtual Payment Address) e.g. "user@wallet"
        receiver_account: VPA or bank account
        """
        if not cls.is_configured():
            return {
                "success": False,
                "error":   "BB IIPS not yet active",
                "note":    "Expected launch: 2026-2027 per Bangladesh Bank Roadmap 2027",
                "status":  "PENDING_ACTIVATION",
            }
        try:
            payload = {
                "sender":    sender_account,
                "receiver":  receiver_account,
                "amount":    str(amount),
                "currency":  "BDT",
                "reference": str(reference)[:50],
                "remarks":   str(remarks)[:100],
            }
            resp = requests.post(
                f"{cls.BASE_URL}/payment/initiate",
                json=payload,
                headers={"Authorization": f"Bearer {cls.API_KEY}",
                          "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            if data.get("status") == "SUCCESS":
                return {"success": True, "transaction_id": data.get("txnId"), "data": data}
            return {"success": False, "error": data.get("message", "Failed"), "data": data}
        except Exception as e:
            logger.error(f"BB IIPS error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def register_vpa(cls, username: str, wallet_id: int) -> dict:
        """
        Register a Virtual Payment Address (VPA) for the user.
        e.g. "john_doe@wallet" or "01712345678@wallet"
        """
        if not cls.is_configured():
            return {"success": False, "note": "BB IIPS not yet active"}
        vpa = f"{username}@wallet"
        try:
            resp = requests.post(
                f"{cls.BASE_URL}/vpa/register",
                json={"vpa": vpa, "wallet_id": str(wallet_id)},
                headers={"Authorization": f"Bearer {cls.API_KEY}"},
                timeout=cls.TIMEOUT,
            )
            data = resp.json()
            return {"success": data.get("status") == "SUCCESS", "vpa": vpa, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def get_payment_status(cls, transaction_id: str) -> dict:
        """Check status of an IIPS transaction."""
        if not cls.is_configured():
            return {"status": "UNKNOWN", "note": "BB IIPS not configured"}
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/payment/{transaction_id}",
                headers={"Authorization": f"Bearer {cls.API_KEY}"},
                timeout=cls.TIMEOUT,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

# api/wallet/integration/paypal_integration.py
"""PayPal Payouts REST API integration."""
import logging, requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.integration.paypal")

class PayPalService:
    CLIENT_ID     = getattr(settings, "PAYPAL_CLIENT_ID", "")
    CLIENT_SECRET = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
    BASE_URL      = getattr(settings, "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    TIMEOUT       = 30

    @classmethod
    def _get_token(cls) -> str:
        try:
            resp = requests.post(f"{cls.BASE_URL}/v1/oauth2/token",
                auth=(cls.CLIENT_ID, cls.CLIENT_SECRET),
                data={"grant_type": "client_credentials"}, timeout=cls.TIMEOUT)
            return resp.json().get("access_token", "")
        except Exception as e:
            logger.error(f"PayPal token error: {e}"); return ""

    @classmethod
    def create_payout(cls, email: str, amount: Decimal, currency: str = "USD",
                       note: str = "Wallet Payout", sender_item_id: str = "") -> dict:
        token = cls._get_token()
        if not token: return {"success": False, "error": "Token failed"}
        payload = {
            "sender_batch_header": {"sender_batch_id": sender_item_id, "email_subject": "You have a payment"},
            "items": [{"recipient_type": "EMAIL", "amount": {"value": str(amount), "currency": currency},
                       "receiver": email, "note": note, "sender_item_id": sender_item_id}]
        }
        try:
            resp = requests.post(f"{cls.BASE_URL}/v1/payments/payouts",
                json=payload, headers={"Authorization": f"Bearer {token}",
                "Content-Type": "application/json"}, timeout=cls.TIMEOUT)
            data = resp.json()
            if resp.status_code in (200, 201):
                batch_id = data.get("batch_header", {}).get("payout_batch_id", "")
                return {"success": True, "batch_id": batch_id, "status": data.get("batch_header", {}).get("batch_status")}
            return {"success": False, "error": str(data)}
        except Exception as e:
            return {"success": False, "error": str(e)}

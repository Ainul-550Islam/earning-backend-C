"""
SmartLink — PayPal Payouts API Service
=======================================
Self-contained PayPal integration. No imports from any other api.* app.
Uses PayPal Payouts API v1 (REST).

Required Django settings (add to your settings.py or env):
    SMARTLINK_PAYPAL_CLIENT_ID     = "..."
    SMARTLINK_PAYPAL_CLIENT_SECRET = "..."
    SMARTLINK_PAYPAL_MODE          = "sandbox" | "live"   (default: "sandbox")
"""
import logging
import uuid
import requests
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("smartlink.billing.paypal")

# ── Endpoints ─────────────────────────────────────────────────────────────────
_BASE = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live":    "https://api-m.paypal.com",
}


class PayPalPayoutService:
    """
    Sends individual or batch payouts via PayPal Payouts API.

    Usage:
        svc = PayPalPayoutService()
        result = svc.send_payout(payout_record)
        # result → {"success": True, "transaction_id": "...", "batch_id": "..."}
    """

    def __init__(self):
        mode = getattr(settings, "SMARTLINK_PAYPAL_MODE", "sandbox")
        self.base_url       = _BASE.get(mode, _BASE["sandbox"])
        self.client_id      = getattr(settings, "SMARTLINK_PAYPAL_CLIENT_ID", "")
        self.client_secret  = getattr(settings, "SMARTLINK_PAYPAL_CLIENT_SECRET", "")
        self._access_token  = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """
        Fetch a fresh OAuth2 access token from PayPal.
        Token is cached on the instance for the request lifecycle.
        Each Celery task instantiates a fresh service, so no stale tokens.
        """
        if self._access_token:
            return self._access_token

        url = f"{self.base_url}/v1/oauth2/token"
        resp = requests.post(
            url,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        logger.debug("PayPal access token acquired")
        return self._access_token

    def _headers(self) -> dict:
        return {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self._get_access_token()}",
        }

    # ── Single Payout ─────────────────────────────────────────────────────────

    def send_payout(self, payout_record) -> dict:
        """
        Send a single payout to a publisher via PayPal.

        Args:
            payout_record: smartlink.models.billing.PayoutRecord instance

        Returns:
            {
                "success":        bool,
                "batch_id":       str | "",   # PayPal payout batch ID
                "transaction_id": str | "",   # PayPal item transaction ID (pending at send)
                "status":         str,         # "PENDING" | "FAILED" | ...
                "error":          str | "",
            }
        """
        if not self.client_id or not self.client_secret:
            return self._error("PayPal credentials not configured "
                               "(SMARTLINK_PAYPAL_CLIENT_ID / SMARTLINK_PAYPAL_CLIENT_SECRET)")

        email   = payout_record.payment_address
        amount  = str(payout_record.net_amount.quantize(Decimal("0.01")))
        currency = payout_record.currency or "USD"
        sender_item_id = str(payout_record.reference_id)

        payload = {
            "sender_batch_header": {
                "sender_batch_id": f"sl_{sender_item_id}",
                "email_subject":   "Your SmartLink payout is on its way",
                "email_message":   (
                    f"You have received a payout of {currency} {amount}. "
                    "Thank you for being a SmartLink publisher."
                ),
            },
            "items": [
                {
                    "recipient_type":  "EMAIL",
                    "amount": {
                        "value":    amount,
                        "currency": currency,
                    },
                    "note":           f"SmartLink payout ref {sender_item_id}",
                    "sender_item_id": sender_item_id,
                    "receiver":       email,
                }
            ],
        }

        try:
            resp = requests.post(
                f"{self.base_url}/v1/payments/payouts",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            data = resp.json()

            if resp.status_code in (200, 201):
                batch_id = data.get("batch_header", {}).get("payout_batch_id", "")
                logger.info(
                    f"PayPal payout sent: ref={sender_item_id} "
                    f"email={email} amount={amount} {currency} "
                    f"batch_id={batch_id}"
                )
                return {
                    "success":        True,
                    "batch_id":       batch_id,
                    "transaction_id": batch_id,   # item transaction ID available later via webhook
                    "status":         data.get("batch_header", {}).get("batch_status", "PENDING"),
                    "error":          "",
                }
            else:
                # PayPal error response
                err_name    = data.get("name", "UNKNOWN")
                err_message = data.get("message", str(data))
                logger.error(
                    f"PayPal payout failed: ref={sender_item_id} "
                    f"status={resp.status_code} err={err_name}: {err_message}"
                )
                return self._error(f"{err_name}: {err_message}")

        except requests.exceptions.Timeout:
            return self._error("PayPal API timeout after 30s")
        except requests.exceptions.ConnectionError as e:
            return self._error(f"PayPal connection error: {e}")
        except Exception as e:
            logger.exception(f"PayPal unexpected error for ref={sender_item_id}")
            return self._error(str(e))

    # ── Batch Status Check ────────────────────────────────────────────────────

    def get_batch_status(self, batch_id: str) -> dict:
        """
        Poll PayPal for payout batch status.
        Returns the raw PayPal batch_header dict, or {"error": "..."}.
        """
        if not self.client_id or not self.client_secret:
            return {"error": "PayPal credentials not configured"}
        try:
            resp = requests.get(
                f"{self.base_url}/v1/payments/payouts/{batch_id}",
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200:
                return data.get("batch_header", data)
            return {"error": data.get("message", "Unknown error")}
        except Exception as e:
            return {"error": str(e)}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _error(message: str) -> dict:
        return {
            "success":        False,
            "batch_id":       "",
            "transaction_id": "",
            "status":         "FAILED",
            "error":          message,
        }

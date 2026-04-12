"""PAYMENT_PROCESSING/razorpay_integration.py — Razorpay (India)."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class RazorpayGateway(BasePaymentGateway):
    GATEWAY_NAME = "razorpay"
    BASE_URL     = "https://api.razorpay.com/v1"

    def __init__(self):
        from django.conf import settings
        self.key_id     = getattr(settings, "RAZORPAY_KEY_ID", "")
        self.key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        amount_paise = int(amount * 100)
        logger.info("Razorpay initiate: paise=%d ref=%s", amount_paise, reference)
        return {
            "gateway":   self.GATEWAY_NAME, "order_id": f"rp_{reference}",
            "amount":    amount_paise, "currency": currency or "INR",
            "key_id":    self.key_id, "status": "created",
        }

    def verify(self, transaction_id: str) -> dict:
        return {"transaction_id": transaction_id, "status": "captured"}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        return {"transaction_id": transaction_id, "status": "processed"}

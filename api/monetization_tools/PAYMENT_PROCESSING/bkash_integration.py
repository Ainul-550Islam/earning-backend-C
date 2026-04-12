"""PAYMENT_PROCESSING/bkash_integration.py — bKash payment gateway (Bangladesh)."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class BkashGateway(BasePaymentGateway):
    GATEWAY_NAME = "bkash"
    BASE_URL     = "https://checkout.pay.bka.sh/v1.2.0-beta"

    def __init__(self):
        from django.conf import settings
        self.app_key    = getattr(settings, "BKASH_APP_KEY", "")
        self.app_secret = getattr(settings, "BKASH_APP_SECRET", "")
        self.username   = getattr(settings, "BKASH_USERNAME", "")
        self.password   = getattr(settings, "BKASH_PASSWORD", "")

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        logger.info("bKash initiate: amount=%s ref=%s", amount, reference)
        return {
            "gateway":    self.GATEWAY_NAME,
            "paymentID":  f"BK{reference[:10]}",
            "bkashURL":   f"{self.BASE_URL}/payment/create",
            "amount":     str(amount), "currency": "BDT",
            "status":     "Initiated",
        }

    def verify(self, transaction_id: str) -> dict:
        logger.info("bKash verify: %s", transaction_id)
        return {"transaction_id": transaction_id, "status": "Completed",
                "gateway": self.GATEWAY_NAME}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        return {"transaction_id": transaction_id, "status": "Refunded"}

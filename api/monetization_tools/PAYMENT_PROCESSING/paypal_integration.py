"""PAYMENT_PROCESSING/paypal_integration.py — PayPal payment gateway."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class PayPalGateway(BasePaymentGateway):
    GATEWAY_NAME = "paypal"
    SANDBOX_URL  = "https://api.sandbox.paypal.com"
    LIVE_URL     = "https://api.paypal.com"

    def __init__(self, sandbox: bool = False):
        from django.conf import settings
        self.client_id  = getattr(settings, "PAYPAL_CLIENT_ID", "")
        self.secret     = getattr(settings, "PAYPAL_SECRET", "")
        self.base_url   = self.SANDBOX_URL if sandbox else self.LIVE_URL

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        logger.info("PayPal initiate: amount=%s %s", amount, currency)
        return {"gateway": self.GATEWAY_NAME, "approval_url": f"{self.base_url}/pay/{reference}",
                "status": "initiated"}

    def verify(self, transaction_id: str) -> dict:
        logger.info("PayPal verify: %s", transaction_id)
        return {"transaction_id": transaction_id, "status": "success"}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        return {"transaction_id": transaction_id, "status": "refunded"}

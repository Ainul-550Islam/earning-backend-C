"""PAYMENT_PROCESSING/nagad_integration.py — Nagad payment gateway (Bangladesh)."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class NagadGateway(BasePaymentGateway):
    GATEWAY_NAME = "nagad"
    BASE_URL     = "https://api.mynagad.com/api/dfs"
    SANDBOX_URL  = "https://sandbox.mynagad.com:10080/remote-payment-gateway-1.0/api/dfs"

    def __init__(self, sandbox: bool = False):
        from django.conf import settings
        self.merchant_id = getattr(settings, "NAGAD_MERCHANT_ID", "")
        self.private_key = getattr(settings, "NAGAD_PRIVATE_KEY", "")
        self.public_key  = getattr(settings, "NAGAD_PUBLIC_KEY", "")
        self.base_url    = self.SANDBOX_URL if sandbox else self.BASE_URL

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        logger.info("Nagad initiate: amount=%s ref=%s", amount, reference)
        return {
            "gateway":   self.GATEWAY_NAME, "orderId": reference,
            "amount":    str(amount), "currency": "BDT",
            "paymentURL": f"{self.base_url}/check-out/initialize/{self.merchant_id}/{reference}",
            "status":    "Initialized",
        }

    def verify(self, transaction_id: str) -> dict:
        return {"transaction_id": transaction_id, "status": "Success"}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        return {"transaction_id": transaction_id, "status": "Refunded"}

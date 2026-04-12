"""PAYMENT_PROCESSING/sslcommerz_integration.py — SSLCommerz (Bangladesh)."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class SSLCommerzGateway(BasePaymentGateway):
    GATEWAY_NAME = "sslcommerz"
    LIVE_URL     = "https://securepay.sslcommerz.com/gwprocess/v4/api.php"
    SANDBOX_URL  = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"

    def __init__(self, sandbox: bool = True):
        from django.conf import settings
        self.store_id  = getattr(settings, "SSLCOMMERZ_STORE_ID", "")
        self.store_pass = getattr(settings, "SSLCOMMERZ_STORE_PASS", "")
        self.base_url   = self.SANDBOX_URL if sandbox else self.LIVE_URL

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        logger.info("SSLCommerz initiate: amount=%s ref=%s", amount, reference)
        return {
            "gateway":      self.GATEWAY_NAME,
            "GatewayPageURL": self.base_url,
            "sessionkey":   f"ssl_{reference}",
            "amount":       str(amount), "currency": currency,
            "status":       "SUCCESS",
        }

    def verify(self, transaction_id: str) -> dict:
        return {"transaction_id": transaction_id, "status": "VALID"}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        return {"transaction_id": transaction_id, "status": "refund_success"}

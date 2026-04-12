"""PAYMENT_PROCESSING/stripe_integration.py — Stripe payment gateway."""
import logging
from decimal import Decimal
from .payment_gateway import BasePaymentGateway

logger = logging.getLogger(__name__)


class StripeGateway(BasePaymentGateway):
    GATEWAY_NAME = "stripe"
    BASE_URL     = "https://api.stripe.com/v1"

    def __init__(self):
        from django.conf import settings
        self.secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")

    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        logger.info("Stripe initiate: amount=%s %s ref=%s", amount, currency, reference)
        return {
            "gateway":       self.GATEWAY_NAME,
            "amount":        str(amount),
            "currency":      currency,
            "reference":     reference,
            "client_secret": f"pi_{reference}_secret",
            "status":        "initiated",
        }

    def verify(self, transaction_id: str) -> dict:
        logger.info("Stripe verify: %s", transaction_id)
        return {"transaction_id": transaction_id, "status": "success", "gateway": self.GATEWAY_NAME}

    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        logger.info("Stripe refund: %s amount=%s", transaction_id, amount)
        return {"transaction_id": transaction_id, "status": "refunded", "gateway": self.GATEWAY_NAME}

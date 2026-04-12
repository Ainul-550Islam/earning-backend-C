"""PAYMENT_PROCESSING/payment_gateway.py — Abstract payment gateway base."""
from abc import ABC, abstractmethod
from decimal import Decimal


class BasePaymentGateway(ABC):
    """Abstract base for all payment gateway integrations."""

    @abstractmethod
    def initiate(self, amount: Decimal, currency: str, user, reference: str) -> dict:
        pass

    @abstractmethod
    def verify(self, transaction_id: str) -> dict:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal = None) -> dict:
        pass

    @staticmethod
    def gateway_for(gateway_name: str) -> "BasePaymentGateway":
        from . import stripe_integration, bkash_integration, nagad_integration
        gateways = {
            "stripe": stripe_integration.StripeGateway,
            "bkash":  bkash_integration.BkashGateway,
            "nagad":  nagad_integration.NagadGateway,
        }
        cls = gateways.get(gateway_name)
        if cls:
            return cls()
        raise ValueError(f"Unknown gateway: {gateway_name}")

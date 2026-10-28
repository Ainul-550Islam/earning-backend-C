"""
INTEGRATIONS/payment_gateway.py — re-export shim (test compatibility)
"""
from .payment_gateway_integration import (
    PaymentGatewayBase,
    BkashIntegration,
    NagadIntegration,
)


class BkashGateway(BkashIntegration):
    """Test-friendly subclass with default credentials."""
    def __init__(self, app_key="test", app_secret="test",
                 username="test", password="test", sandbox=True):
        super().__init__(app_key=app_key, app_secret=app_secret,
                         username=username, password=password, sandbox=sandbox)


class NagadGateway(NagadIntegration):
    """Test-friendly subclass with default credentials."""
    def __init__(self, merchant_id="test", merchant_number="01700000000",
                 public_key="test", private_key="test", sandbox=True):
        super().__init__(merchant_id=merchant_id, merchant_number=merchant_number,
                         public_key=public_key, private_key=private_key,
                         sandbox=sandbox)


__all__ = ["PaymentGatewayBase", "BkashGateway", "NagadGateway"]

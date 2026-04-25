# api/wallet/services/gateway/SSLCommerzService.py
"""SSLCommerz service wrapper."""
from decimal import Decimal
import logging
logger = logging.getLogger("wallet.gateway.sslcommerz")

class SSLCommerzService:
    @classmethod
    def initiate(cls, order_id: str, amount: Decimal, user_email: str,
                  user_phone: str, **kwargs) -> dict:
        from ..integration.sslcommerz_integration import SSLCommerzService as SS
        return SS.initiate_payment(order_id, amount, user_email, user_phone, **kwargs)

    @classmethod
    def validate(cls, val_id: str) -> dict:
        from ..integration.sslcommerz_integration import SSLCommerzService as SS
        return SS.validate_ipn(val_id)

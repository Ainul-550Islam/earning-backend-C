# api/wallet/services/gateway/PayPalService.py
"""PayPal payout service wrapper."""
from decimal import Decimal
import logging
logger = logging.getLogger("wallet.gateway.paypal")

class PayPalService:
    @classmethod
    def payout(cls, email: str, amount_bdt: Decimal, item_id: str = "", note: str = "Payout") -> dict:
        from ..currency_converter import CurrencyConverter
        from ..integration.paypal_integration import PayPalService as PP
        amount_usd = CurrencyConverter.from_bdt(amount_bdt, "USD")
        return PP.create_payout(email, amount_usd, currency="USD", note=note, sender_item_id=item_id)

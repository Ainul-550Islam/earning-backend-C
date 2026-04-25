# api/wallet/services/gateway/StripeService.py
"""Stripe Connect payout service wrapper."""
from decimal import Decimal
import logging
logger = logging.getLogger("wallet.gateway.stripe")

class StripeService:
    @classmethod
    def payout(cls, stripe_account_id: str, amount_bdt: Decimal, description: str = "Payout") -> dict:
        from ..integration.stripe_integration import StripeService as SS
        return SS.create_payout(amount_bdt, stripe_account_id, description=description)

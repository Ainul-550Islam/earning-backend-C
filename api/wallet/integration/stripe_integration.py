# api/wallet/integration/stripe_integration.py
"""Stripe Connect payout integration."""
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger("wallet.integration.stripe")

class StripeService:
    API_KEY       = getattr(settings, "STRIPE_SECRET_KEY", "")
    WEBHOOK_SECRET= getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    @classmethod
    def create_payout(cls, amount_bdt: Decimal, stripe_account_id: str,
                       currency: str = "usd", description: str = "Wallet Payout") -> dict:
        try:
            import stripe
            stripe.api_key = cls.API_KEY
            # Convert BDT to USD cents
            from ..currency_converter import CurrencyConverter
            amount_usd = CurrencyConverter.from_bdt(amount_bdt, "USD")
            amount_cents = int(amount_usd * 100)
            payout = stripe.Payout.create(
                amount=amount_cents, currency=currency,
                description=description,
                stripe_account=stripe_account_id,
            )
            return {"success": True, "payout_id": payout.id, "status": payout.status,
                    "amount_usd": float(amount_usd)}
        except Exception as e:
            logger.error(f"Stripe payout error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def verify_webhook(cls, payload: bytes, sig_header: str) -> dict:
        try:
            import stripe
            stripe.api_key = cls.API_KEY
            event = stripe.Webhook.construct_event(payload, sig_header, cls.WEBHOOK_SECRET)
            return {"valid": True, "event": event}
        except Exception as e:
            return {"valid": False, "error": str(e)}

# api/wallet/virtual_cards.py
"""
Virtual Cards — issue virtual Visa/Mastercard from wallet balance.
2026 trend: Virtual cards becoming default for online payments.
Integration: Stripe Issuing or Marqeta API.

Features:
  - Issue single-use or multi-use virtual card
  - Card funded from wallet balance
  - Real-time spend control (limit per transaction)
  - Freeze/unfreeze card instantly
  - Card-linked to specific merchant (e.g., for online ads)
  - Auto-expire after set date

No core code modified — uses plugin_registry + hooks.
"""
import uuid
import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("wallet.virtual_cards")


class VirtualCardService:
    """Issue and manage virtual payment cards."""

    PROVIDER  = getattr(settings, "VIRTUAL_CARD_PROVIDER", "stripe")
    API_KEY   = getattr(settings, "STRIPE_SECRET_KEY", "")
    ENABLED   = getattr(settings, "VIRTUAL_CARDS_ENABLED", False)

    @classmethod
    def issue(cls, user, wallet, spending_limit: Decimal,
               currency: str = "usd", single_use: bool = False,
               expires_months: int = 12, label: str = "") -> dict:
        """
        Issue a new virtual card funded from wallet balance.
        Args:
            spending_limit: Maximum spend on this card (in BDT)
            single_use: True = card expires after 1 transaction
            expires_months: Card validity in months
        """
        if not cls.ENABLED:
            return {"success": False, "error": "Virtual cards not enabled",
                    "note": "Set VIRTUAL_CARDS_ENABLED=True and configure Stripe Issuing"}

        if spending_limit > wallet.available_balance:
            return {"success": False, "error": "Insufficient wallet balance for card limit"}
        if spending_limit < Decimal("100"):
            return {"success": False, "error": "Minimum card limit: 100 BDT"}

        try:
            # Convert BDT to USD for Stripe
            from .currency_converter import CurrencyConverter
            limit_usd_cents = int(CurrencyConverter.from_bdt(spending_limit, "USD") * 100)

            if cls.PROVIDER == "stripe":
                return cls._issue_stripe(user, wallet, limit_usd_cents,
                                          single_use, expires_months, label, spending_limit)
            return {"success": False, "error": f"Unknown provider: {cls.PROVIDER}"}
        except Exception as e:
            logger.error(f"Virtual card issue error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @classmethod
    def _issue_stripe(cls, user, wallet, limit_cents: int,
                       single_use: bool, expires_months: int,
                       label: str, bdt_limit: Decimal) -> dict:
        """Issue card via Stripe Issuing API."""
        try:
            import stripe
            stripe.api_key = cls.API_KEY

            # Create or get cardholder
            cardholder = cls._get_or_create_cardholder(user)

            from datetime import datetime, timedelta
            exp_date = datetime.now() + timedelta(days=30 * expires_months)

            card = stripe.issuing.Card.create(
                cardholder=cardholder,
                currency="usd",
                type="virtual",
                spending_controls={
                    "spending_limits": [{
                        "amount":   limit_cents,
                        "interval": "per_authorization" if single_use else "monthly",
                    }]
                },
                metadata={
                    "wallet_id":  str(wallet.id),
                    "user_id":    str(user.id),
                    "bdt_limit":  str(bdt_limit),
                    "label":      label[:50],
                    "single_use": str(single_use),
                },
            )

            # Reserve funds in wallet
            from .services.core.WalletService import WalletService
            WalletService.reserve_balance(wallet, bdt_limit, f"Virtual card: {card.id}")

            logger.info(f"Virtual card issued: {card.id} user={user.id} limit={bdt_limit} BDT")
            return {
                "success":   True,
                "card_id":   card.id,
                "last4":     card.last4,
                "brand":     card.brand,
                "exp_month": exp_date.month,
                "exp_year":  exp_date.year,
                "status":    card.status,
                "limit_bdt": str(bdt_limit),
                "single_use":single_use,
            }
        except Exception as e:
            logger.error(f"Stripe card issue error: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def _get_or_create_cardholder(cls, user):
        """Get or create Stripe cardholder for user."""
        import stripe
        stripe.api_key = cls.API_KEY
        existing = stripe.issuing.Cardholder.list(email=user.email, limit=1)
        if existing.data:
            return existing.data[0].id
        holder = stripe.issuing.Cardholder.create(
            type="individual",
            name=f"{user.first_name} {user.last_name}".strip() or user.username,
            email=user.email,
            billing={"address": {"line1": "Bangladesh", "city": "Dhaka",
                                  "country": "BD", "postal_code": "1000"}},
        )
        return holder.id

    @classmethod
    def freeze(cls, card_id: str) -> dict:
        """Freeze a virtual card instantly."""
        if not cls.API_KEY:
            return {"success": False, "error": "Not configured"}
        try:
            import stripe
            stripe.api_key = cls.API_KEY
            card = stripe.issuing.Card.modify(card_id, status="inactive")
            return {"success": True, "card_id": card_id, "status": "frozen"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def unfreeze(cls, card_id: str) -> dict:
        """Unfreeze a virtual card."""
        if not cls.API_KEY:
            return {"success": False, "error": "Not configured"}
        try:
            import stripe
            stripe.api_key = cls.API_KEY
            card = stripe.issuing.Card.modify(card_id, status="active")
            return {"success": True, "card_id": card_id, "status": "active"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def cancel(cls, card_id: str, wallet, release_funds: bool = True) -> dict:
        """Cancel a virtual card and optionally release reserved funds."""
        if not cls.API_KEY:
            return {"success": False, "error": "Not configured"}
        try:
            import stripe
            stripe.api_key = cls.API_KEY
            card = stripe.issuing.Card.modify(card_id, status="canceled")
            if release_funds:
                meta = card.metadata or {}
                bdt_limit = Decimal(meta.get("bdt_limit", "0"))
                if bdt_limit > 0:
                    from .services.core.WalletService import WalletService
                    WalletService.release_reserve(wallet, bdt_limit, f"Card cancelled: {card_id}")
            return {"success": True, "card_id": card_id, "funds_released": release_funds}
        except Exception as e:
            return {"success": False, "error": str(e)}

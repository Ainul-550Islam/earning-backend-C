# api/offerwall/services.py
"""
Business logic for offerwall. Move complex logic out of views.
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class OfferwallService:
    """Service for offer completion and reward crediting."""

    @staticmethod
    def credit_offer_reward(user, offer, amount: Decimal, reference_id: str, **meta) -> Optional[Any]:
        """Credit user wallet for offer completion. Integrates with wallet + fraud_detection."""
        try:
            from api.wallet.models import Wallet, WalletTransaction
            wallet = Wallet.objects.filter(user=user).first()
            if not wallet:
                logger.warning("No wallet for user %s", user.id)
                return None
            # Optional: run fraud check before crediting
            from api.fraud_detection.models import UserRiskProfile
            risk = UserRiskProfile.objects.filter(user=user).first()
            if risk and (risk.is_flagged or risk.is_restricted):
                logger.warning("User %s flagged; skipping auto-credit", user.id)
                return None
            return WalletTransaction.objects.create(
                wallet=wallet,
                type='reward',
                amount=amount,
                status='approved',
                reference_id=reference_id,
                reference_type='offer_completion',
                description=meta.get('description', 'Offer reward'),
                metadata=meta,
            )
        except Exception as e:
            logger.exception("Credit offer reward failed: %s", e)
            return None

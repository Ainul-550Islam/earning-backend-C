# api/payment_gateways/services.py
"""
Business logic for payment gateways. Move complex logic out of views.
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class PaymentGatewayService:
    """Central service for payment operations."""

    @staticmethod
    def create_withdrawal_transaction(wallet, amount: Decimal, reference_id: str, **meta) -> Optional[Any]:
        """Create wallet transaction for withdrawal. Integrate with wallet app."""
        try:
            from api.wallet.models import WalletTransaction
            return WalletTransaction.objects.create(
                wallet=wallet,
                type='withdrawal',
                amount=-amount,
                status='pending',
                reference_id=reference_id,
                reference_type='payment_gateway',
                description=meta.get('description', 'Withdrawal'),
                metadata=meta,
            )
        except Exception as e:
            logger.exception("Create withdrawal transaction failed: %s", e)
            return None

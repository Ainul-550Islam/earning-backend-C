# api/offer_inventory/finance_payment/wallet_integration.py
"""
Wallet Integration Bridge.
Connects offer_inventory to the main wallet system.
"""
import logging
from decimal import Decimal
from django.db import transaction

logger = logging.getLogger(__name__)


class WalletIntegration:
    """Bridge between offer_inventory and api.wallet."""

    @staticmethod
    def get_balance(user) -> dict:
        """Get user's current wallet balances."""
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            return {
                'current_balance' : float(wallet.current_balance),
                'pending_balance' : float(wallet.pending_balance),
                'total_earned'    : float(wallet.total_earned),
                'total_withdrawn' : float(wallet.total_withdrawn),
                'frozen_balance'  : float(wallet.frozen_balance),
                'available'       : float(wallet.current_balance - wallet.frozen_balance),
                'is_locked'       : wallet.is_locked,
                'currency'        : wallet.currency,
            }
        except Exception as e:
            logger.error(f'WalletIntegration.get_balance error: {e}')
            return {
                'current_balance': 0.0, 'pending_balance': 0.0,
                'total_earned': 0.0, 'total_withdrawn': 0.0,
                'available': 0.0, 'is_locked': False, 'currency': 'BDT',
            }

    @staticmethod
    def ensure_wallet(user):
        """Create wallet if it doesn't exist."""
        from api.wallet.models import Wallet
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            logger.info(f'Wallet auto-created for user {user.id}')
        return wallet

    @staticmethod
    @transaction.atomic
    def credit(user, amount: Decimal, source: str, source_id: str,
               description: str) -> bool:
        """Credit user wallet. Returns True on success."""
        try:
            from api.offer_inventory.repository import WalletRepository
            WalletRepository.credit_user(
                user_id    =user.id,
                amount     =amount,
                source     =source,
                source_id  =source_id,
                description=description,
            )
            return True
        except Exception as e:
            logger.error(f'Wallet credit error user={user.id}: {e}')
            return False

    @staticmethod
    @transaction.atomic
    def debit(user, amount: Decimal, source: str, source_id: str,
              description: str) -> bool:
        """Debit user wallet. Returns True on success."""
        try:
            from api.offer_inventory.repository import WalletRepository
            WalletRepository.debit_user(
                user_id    =user.id,
                amount     =amount,
                source     =source,
                source_id  =source_id,
                description=description,
            )
            return True
        except Exception as e:
            logger.error(f'Wallet debit error user={user.id}: {e}')
            return False

    @staticmethod
    def lock_wallet(user, reason: str) -> bool:
        """Lock user wallet (fraud/dispute)."""
        try:
            from api.wallet.models import Wallet
            Wallet.objects.filter(user=user).update(
                is_locked=True, locked_reason=reason
            )
            logger.warning(f'Wallet locked: user={user.id} reason={reason}')
            return True
        except Exception as e:
            logger.error(f'Wallet lock error: {e}')
            return False

    @staticmethod
    def unlock_wallet(user) -> bool:
        """Unlock user wallet."""
        try:
            from api.wallet.models import Wallet
            Wallet.objects.filter(user=user).update(
                is_locked=False, locked_reason=''
            )
            return True
        except Exception as e:
            logger.error(f'Wallet unlock error: {e}')
            return False

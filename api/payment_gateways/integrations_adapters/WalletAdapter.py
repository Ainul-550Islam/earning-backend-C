# api/payment_gateways/integrations_adapters/WalletAdapter.py
# Bridge between payment_gateways and api.wallet

from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class WalletAdapter:
    """
    Bridges payment_gateways with your existing api.wallet app.
    Instead of building a new wallet, we call your existing wallet.

    Your api.wallet handles:
        - Balance tracking
        - Transaction ledger
        - Wallet history

    We just call it after gateway events.
    """

    def credit_deposit(self, user, amount: Decimal, gateway: str, reference_id: str):
        """Credit user wallet after successful deposit."""
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                transaction_type='deposit',
                amount=amount,
                source=gateway,
                reference=reference_id,
                description=f'Deposit via {gateway.upper()}',
                status='completed',
            )
            logger.info(f'Wallet credited: user={user.id} +{amount} via {gateway}')
            return True
        except ImportError:
            # api.wallet not installed — fallback to direct balance update
            return self._direct_balance_update(user, amount, 'credit')
        except Exception as e:
            logger.error(f'WalletAdapter.credit_deposit failed: {e}')
            return False

    def debit_withdrawal(self, user, amount: Decimal, gateway: str, reference_id: str):
        """Debit user wallet for withdrawal."""
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                transaction_type='withdrawal',
                amount=-amount,  # Negative for debit
                source=gateway,
                reference=reference_id,
                description=f'Withdrawal via {gateway.upper()}',
                status='completed',
            )
            return True
        except ImportError:
            return self._direct_balance_update(user, amount, 'debit')
        except Exception as e:
            logger.error(f'WalletAdapter.debit_withdrawal failed: {e}')
            return False

    def credit_conversion(self, user, amount: Decimal, offer_name: str,
                            conversion_id: str):
        """Credit publisher earnings from a conversion."""
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                transaction_type='earning',
                amount=amount,
                source='conversion',
                reference=conversion_id,
                description=f'Offer completion: {offer_name}',
                status='completed',
            )
            return True
        except ImportError:
            return self._direct_balance_update(user, amount, 'credit')
        except Exception as e:
            logger.error(f'WalletAdapter.credit_conversion failed: {e}')
            return False

    def get_balance(self, user) -> Decimal:
        """Get user balance from wallet app."""
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            return wallet.balance
        except ImportError:
            return Decimal(str(getattr(user, 'balance', '0') or '0'))
        except Exception:
            return Decimal(str(getattr(user, 'balance', '0') or '0'))

    def _direct_balance_update(self, user, amount: Decimal, direction: str) -> bool:
        """Fallback: directly update user.balance if wallet app unavailable."""
        try:
            from django.db.models import F
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if direction == 'credit':
                User.objects.filter(id=user.id).update(balance=F('balance') + amount)
            else:
                User.objects.filter(id=user.id).update(balance=F('balance') - amount)
            return True
        except Exception as e:
            logger.error(f'Direct balance update failed: {e}')
            return False

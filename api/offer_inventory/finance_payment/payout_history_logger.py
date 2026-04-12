# api/offer_inventory/finance_payment/payout_history_logger.py
"""
Payout History Logger.
Immutable audit trail for every wallet debit/credit event.
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class PayoutHistoryLogger:
    """Write immutable payout history records."""

    @staticmethod
    def log_conversion_payout(user, conversion, amount: Decimal,
                               balance_before: Decimal, balance_after: Decimal):
        """Log a conversion reward payment."""
        from api.offer_inventory.models import WalletAudit
        WalletAudit.objects.create(
            user            =user,
            transaction_type='conversion_payout',
            amount          =amount,
            balance_before  =balance_before,
            balance_after   =balance_after,
            reference_id    =str(conversion.id),
            reference_type  ='Conversion',
            note            =(
                f'Offer: {conversion.offer.title if conversion.offer else "?"} | '
                f'Payout: {conversion.payout_amount}'
            ),
        )

    @staticmethod
    def log_withdrawal(user, withdrawal_request, balance_before: Decimal,
                        balance_after: Decimal):
        """Log a withdrawal debit."""
        from api.offer_inventory.models import WalletAudit
        WalletAudit.objects.create(
            user            =user,
            transaction_type='withdrawal',
            amount          =withdrawal_request.amount,
            balance_before  =balance_before,
            balance_after   =balance_after,
            reference_id    =str(withdrawal_request.id),
            reference_type  ='WithdrawalRequest',
            note            =(
                f'Ref: {withdrawal_request.reference_no} | '
                f'Net: {withdrawal_request.net_amount} | '
                f'Fee: {withdrawal_request.fee}'
            ),
        )

    @staticmethod
    def log_referral_commission(referrer, conversion, amount: Decimal):
        """Log referral commission credit."""
        from api.offer_inventory.models import WalletAudit
        from api.wallet.models import Wallet
        try:
            wallet = Wallet.objects.get(user=referrer)
            bal    = wallet.current_balance
        except Exception:
            bal = Decimal('0')
        WalletAudit.objects.create(
            user            =referrer,
            transaction_type='referral_commission',
            amount          =amount,
            balance_before  =bal - amount,
            balance_after   =bal,
            reference_id    =str(conversion.id),
            reference_type  ='ReferralCommission',
            note            =f'Commission from {conversion.user.username}',
        )

    @staticmethod
    def log_reversal(user, conversion, amount: Decimal,
                      balance_before: Decimal, balance_after: Decimal):
        """Log a balance reversal."""
        from api.offer_inventory.models import WalletAudit
        WalletAudit.objects.create(
            user            =user,
            transaction_type='reversal',
            amount          =-amount,   # Negative = debit
            balance_before  =balance_before,
            balance_after   =balance_after,
            reference_id    =str(conversion.id),
            reference_type  ='ConversionReversal',
            note            =f'Clawback for conversion {conversion.id}',
        )

    @staticmethod
    def get_user_history(user, page: int = 1, page_size: int = 20) -> list:
        """Paginated payout history for a user."""
        from api.offer_inventory.models import WalletAudit
        start = (page - 1) * page_size
        return list(
            WalletAudit.objects.filter(user=user)
            .order_by('-created_at')[start:start + page_size]
        )

"""
api/users/wallet/balance_checker.py
Balance validation — withdrawal বা action-এর আগে check করো
"""
import logging
from decimal import Decimal
from ..constants import UserTier, WalletConstants
from ..exceptions import InsufficientBalanceException, KYCRequiredException

logger = logging.getLogger(__name__)


class BalanceChecker:
    """
    Withdrawal বা কোনো action-এর আগে
    balance সংক্রান্ত সব validation এখানে।
    """

    def check_withdrawal_eligibility(self, user, amount: float) -> dict:
        """
        Withdrawal করার আগে সব check করো।
        Returns: {'eligible': True/False, 'reason': '...'}
        Raises exceptions যদি না হয়।
        """
        checks = []

        # 1. Balance sufficient?
        balance = self._get_balance(user)
        if balance < amount:
            raise InsufficientBalanceException(
                required  = amount,
                available = balance,
            )
        checks.append('✓ Sufficient balance')

        # 2. Minimum withdrawal amount?
        tier     = getattr(user, 'tier', 'FREE')
        min_amt  = UserTier.MIN_WITHDRAWAL.get(tier, 5.00)
        if amount < min_amt:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'amount': f'Minimum withdrawal for {tier} tier is ${min_amt}'
            })
        checks.append(f'✓ Above minimum (${min_amt})')

        # 3. Maximum daily withdrawal?
        daily_withdrawn = self._get_daily_withdrawn(user)
        if daily_withdrawn + amount > WalletConstants.MAX_DAILY_WITHDRAWAL:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'amount': f'Daily withdrawal limit is ${WalletConstants.MAX_DAILY_WITHDRAWAL}. Already withdrawn: ${daily_withdrawn}'
            })
        checks.append(f'✓ Within daily limit')

        # 4. KYC required for large withdrawal?
        if amount >= 50 and not self._is_kyc_verified(user):
            raise KYCRequiredException()
        checks.append('✓ KYC check passed')

        # 5. Account verified?
        if not getattr(user, 'is_active', True):
            from ..exceptions import AccountSuspendedException
            raise AccountSuspendedException()
        checks.append('✓ Account active')

        return {
            'eligible':      True,
            'amount':        amount,
            'balance_after': balance - amount,
            'checks':        checks,
        }

    def can_afford(self, user, amount: float) -> bool:
        """Simple balance check — exception raise করে না"""
        return self._get_balance(user) >= amount

    def get_withdrawal_limits(self, user) -> dict:
        """User-এর withdrawal limits দাও"""
        tier = getattr(user, 'tier', 'FREE')
        return {
            'min_withdrawal':   UserTier.MIN_WITHDRAWAL.get(tier, 5.00),
            'max_daily':        WalletConstants.MAX_DAILY_WITHDRAWAL,
            'daily_withdrawn':  self._get_daily_withdrawn(user),
            'daily_remaining':  WalletConstants.MAX_DAILY_WITHDRAWAL - self._get_daily_withdrawn(user),
            'tier':             tier,
            'kyc_required_above': 50.00,
            'kyc_verified':     self._is_kyc_verified(user),
        }

    def check_hold_period(self, user) -> bool:
        """
        Conversion hold period পেরিয়েছে কিনা।
        Fraud prevention — নতুন conversion তাৎক্ষণিক withdraw করা যাবে না।
        """
        try:
            from django.apps import apps
            from django.utils import timezone
            from datetime import timedelta

            Transaction = apps.get_model('wallet', 'Transaction')
            hold_since  = timezone.now() - timedelta(days=WalletConstants.HOLD_PERIOD_DAYS)

            # Hold period-এর মধ্যে credit আছে কিনা
            has_held = Transaction.objects.filter(
                user       = user,
                type       = 'credit',
                created_at__gte = hold_since,
                status     = 'held',
            ).exists()

            return not has_held  # True = can withdraw
        except Exception:
            return True

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _get_balance(self, user) -> float:
        from .wallet_manager import wallet_bridge
        data = wallet_bridge.get_balance(user)
        return float(data.get('available_balance', 0))

    def _get_daily_withdrawn(self, user) -> float:
        try:
            from django.apps import apps
            from django.utils import timezone
            from django.db.models import Sum

            Transaction = apps.get_model('wallet', 'Transaction')
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            result = Transaction.objects.filter(
                user       = user,
                type       = 'debit',
                created_at__gte = today_start,
            ).aggregate(total=Sum('amount'))

            return float(result['total'] or 0)
        except Exception:
            return 0.0

    def _is_kyc_verified(self, user) -> bool:
        try:
            from django.apps import apps
            KYC = apps.get_model('kyc', 'KYCVerification')
            return KYC.objects.filter(user=user, status='approved').exists()
        except Exception:
            return getattr(user, 'is_verified', False)


# Singleton
balance_checker = BalanceChecker()

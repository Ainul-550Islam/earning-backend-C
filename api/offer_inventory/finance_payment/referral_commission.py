# api/offer_inventory/finance_payment/referral_commission.py
"""
Referral Commission Calculator & Manager.
Commission is ALWAYS calculated on user_net (after platform fee).
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_RATE = Decimal('5')    # 5% of user_net


class ReferralCommissionManager:
    """Full lifecycle referral commission handling."""

    @classmethod
    @transaction.atomic
    def process(cls, conversion, user_net_reward: Decimal) -> Decimal:
        """
        Calculate and pay referral commission for a conversion.
        user_net_reward: user's reward AFTER platform fee — commission base.
        Returns commission amount paid (Decimal).
        """
        from api.offer_inventory.models import (
            UserReferral, ReferralCommission
        )

        if not conversion.user:
            return Decimal('0')

        # Check if user was referred
        try:
            referral = UserReferral.objects.select_for_update().get(
                referred=conversion.user
            )
        except UserReferral.DoesNotExist:
            return Decimal('0')

        # Get tier-based rate
        rate       = cls._get_rate(referral.referrer)
        commission = (user_net_reward * rate / Decimal('100')).quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        )

        if commission <= 0:
            return Decimal('0')

        # Prevent double commission
        if ReferralCommission.objects.filter(
            conversion=conversion, referrer=referral.referrer
        ).exists():
            logger.info(f'Referral commission already paid: conv={conversion.id}')
            return Decimal('0')

        # Create commission record
        ReferralCommission.objects.create(
            referrer      =referral.referrer,
            referred_user =conversion.user,
            conversion    =conversion,
            commission_pct=rate,
            amount        =commission,
            is_paid       =True,
            paid_at       =timezone.now(),
        )

        # Credit referrer wallet
        from api.offer_inventory.repository import WalletRepository
        WalletRepository.credit_user(
            user_id    =referral.referrer_id,
            amount     =commission,
            source     ='referral',
            source_id  =str(conversion.id),
            description=f'Referral commission — {conversion.user.username}',
        )

        # Update referral lifetime earnings
        UserReferral.objects.filter(id=referral.id).update(
            total_earnings_generated=F('total_earnings_generated') + commission
        )

        logger.info(
            f'Referral commission paid | '
            f'referrer={referral.referrer.username} | '
            f'amount={commission} | rate={rate}%'
        )
        return commission

    @staticmethod
    def _get_rate(referrer) -> Decimal:
        """Tier-based commission rate lookup."""
        try:
            from api.offer_inventory.models import UserReferral, CommissionTier
            count = UserReferral.objects.filter(
                referrer=referrer, is_converted=True
            ).count()
            tier = CommissionTier.objects.filter(
                min_referrals__lte=count, is_active=True
            ).order_by('-min_referrals').first()
            if tier:
                return Decimal(str(tier.commission_rate))
        except Exception:
            pass
        return DEFAULT_RATE

    @staticmethod
    def get_summary(referrer) -> dict:
        """Referral earnings summary for a user."""
        from api.offer_inventory.models import ReferralCommission
        agg = ReferralCommission.objects.filter(
            referrer=referrer
        ).aggregate(
            total_earned=Sum('amount'),
            total_paid  =Sum('amount', filter=F('is_paid') == True),
        )
        return {
            'total_earned': float(agg['total_earned'] or 0),
            'total_paid'  : float(agg['total_paid']   or 0),
            'default_rate': float(DEFAULT_RATE),
        }

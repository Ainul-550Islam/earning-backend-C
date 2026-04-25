# api/payment_gateways/referral/ReferralEngine.py
# Referral commission calculation and payment engine

from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class ReferralEngine:
    """
    Handles all referral commission logic.
    Called after every successful deposit to check if referral commission is due.
    """

    def get_or_create_referral_link(self, user) -> 'ReferralLink':
        """Get or create referral link for a user."""
        from .models import ReferralLink
        link, _ = ReferralLink.objects.get_or_create(user=user)
        return link

    def register_referral(self, referred_user, referral_code: str) -> bool:
        """
        Register a referral when a new user signs up via referral link.
        Call this in your user registration view.
        """
        from .models import ReferralLink, Referral, ReferralProgram

        try:
            link = ReferralLink.objects.get(code=referral_code, is_active=True)
        except ReferralLink.DoesNotExist:
            return False

        # Don't allow self-referral
        if link.user == referred_user:
            return False

        # Don't allow double registration
        if Referral.objects.filter(referred_user=referred_user).exists():
            return False

        # Get program config
        try:
            program = ReferralProgram.objects.filter(is_active=True).first()
            months  = program.commission_months if program else 6
        except Exception:
            months  = 6

        commission_end = date.today() + timedelta(days=30 * months)

        Referral.objects.create(
            referrer      = link.user,
            referred_user = referred_user,
            referral_link = link,
            commission_end = commission_end,
        )

        # Update link stats
        link.total_signups += 1
        link.save(update_fields=['total_signups'])

        logger.info(f'Referral registered: {link.user.username} referred {referred_user.username}')
        return True

    def calculate_commission(self, referred_user, transaction_amount: Decimal) -> Decimal:
        """Calculate referral commission for a transaction."""
        from .models import Referral, ReferralProgram

        try:
            referral = Referral.objects.get(
                referred_user=referred_user,
                is_active=True,
                commission_end__gte=date.today(),
            )
        except Referral.DoesNotExist:
            return Decimal('0')

        try:
            program = ReferralProgram.objects.filter(is_active=True).first()
            pct     = program.commission_percent if program else Decimal('10')
        except Exception:
            pct = Decimal('10')

        return (transaction_amount * pct) / 100

    def credit_commission(self, referred_user, transaction_amount: Decimal, transaction_ref: str = '') -> dict:
        """
        Credit referral commission to referrer after a successful transaction.
        Call this in your deposit completion handler.
        """
        from .models import Referral, ReferralCommission, ReferralProgram

        try:
            referral = Referral.objects.select_related('referrer').get(
                referred_user=referred_user,
                is_active=True,
                commission_end__gte=date.today(),
            )
        except Referral.DoesNotExist:
            return {'credited': False, 'reason': 'No active referral'}

        try:
            program = ReferralProgram.objects.filter(is_active=True).first()
            pct     = program.commission_percent if program else Decimal('10')
        except Exception:
            pct = Decimal('10')

        commission_amount = (transaction_amount * pct) / 100

        if commission_amount <= 0:
            return {'credited': False, 'reason': 'Commission amount is zero'}

        # Create commission record
        commission = ReferralCommission.objects.create(
            referral           = referral,
            referrer           = referral.referrer,
            referred_user      = referred_user,
            original_amount    = transaction_amount,
            commission_amount  = commission_amount,
            commission_percent = pct,
            status             = 'pending',
            transaction_ref    = transaction_ref,
        )

        # Credit referrer balance immediately
        referrer = referral.referrer
        if hasattr(referrer, 'balance'):
            referrer.balance += commission_amount
            referrer.save(update_fields=['balance'])
            commission.status  = 'paid'
            commission.paid_at = timezone.now()
            commission.save(update_fields=['status', 'paid_at'])

        # Update referral link stats
        if referral.referral_link:
            referral.referral_link.total_earned += commission_amount
            referral.referral_link.save(update_fields=['total_earned'])

        referral.total_commission_paid += commission_amount
        referral.save(update_fields=['total_commission_paid'])

        logger.info(
            f'Commission credited: {referral.referrer.username} '
            f'+{commission_amount} ({pct}%) from {referred_user.username}'
        )

        return {
            'credited':  True,
            'referrer':  referral.referrer.username,
            'amount':    float(commission_amount),
            'percent':   float(pct),
            'commission': commission,
        }

    def get_referral_stats(self, user) -> dict:
        """Get referral statistics for a user."""
        from .models import ReferralLink, Referral, ReferralCommission

        try:
            link   = ReferralLink.objects.get(user=user)
        except ReferralLink.DoesNotExist:
            link = self.get_or_create_referral_link(user)

        referrals    = Referral.objects.filter(referrer=user)
        commissions  = ReferralCommission.objects.filter(referrer=user)
        total_earned = commissions.filter(status='paid').aggregate(
            t=__import__('django.db.models', fromlist=['Sum']).Sum('commission_amount')
        )['t'] or Decimal('0')

        return {
            'referral_code':   link.code,
            'referral_url':    link.full_url,
            'total_clicks':    link.total_clicks,
            'total_signups':   link.total_signups,
            'active_referrals': referrals.filter(is_active=True).count(),
            'total_referrals': referrals.count(),
            'total_earned':    float(total_earned),
            'pending_commission': float(
                commissions.filter(status='pending').aggregate(
                    t=__import__('django.db.models', fromlist=['Sum']).Sum('commission_amount')
                )['t'] or Decimal('0')
            ),
        }

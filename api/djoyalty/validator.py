# api/djoyalty/validator.py
"""
Djoyalty Validator -- High-level business validation rules।
Validates business logic, not just data types।
These validators are used across services and viewsets।

AUDIT FIX (v1): validate_earn() used a fragile __import__() dynamic call for
the Django Sum aggregation. This is unmockable in tests, fails silently
if the module path changes, and raises unexpected exceptions in restricted
environments.

FIXED: replaced with clean top-level `from django.db.models import Sum`
import. No functional change -- purely a correctness and maintainability fix।

AUDIT FIX (v2 -- Race Condition):
  validate_cashout() calls validate_redeem() which performs an independent
  LoyaltyPoints DB read।  CashoutService.create_request() also reads
  LoyaltyPoints independently, and then acquires select_for_update() before
  writing।  Under concurrent requests, all three reads can return the same
  balance before any write commits।

  FIX: validate_redeem() now accepts an optional `locked_balance` parameter।
  When CashoutService passes the balance from its locked row, validate_redeem()
  uses that value instead of performing a second DB read।  This eliminates
  the overdraft window entirely।  Callers that do NOT use select_for_update()
  continue to work as before (locked_balance=None triggers the DB read)।
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from django.db.models import Sum  # AUDIT FIX (v1): was __import__('django.db.models'...Sum)

logger = logging.getLogger(__name__)


class LoyaltyValidator:
    """
    High-level loyalty business rule validation।
    Returns (is_valid: bool, error_message: str)।
    """

    @staticmethod
    def validate_earn(customer, points: Decimal, source: str) -> Tuple[bool, str]:
        """Validate a points earn operation।"""
        if points <= 0:
            return False, 'Points must be positive.'

        if not customer.is_active:
            return False, 'Customer account is not active.'

        # Daily earn limit check
        try:
            from django.conf import settings
            from django.utils import timezone
            from .models.points import PointsLedger

            max_daily = getattr(
                settings, 'DJOYALTY', {}
            ).get('MAX_DAILY_EARN', 10000)

            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # AUDIT FIX (v1): replaced __import__('django.db.models', fromlist=['Sum']).Sum('points')
            # with clean Sum from top-level import above। Functionally identical,
            # but now testable, readable, and safe।
            today_earned = PointsLedger.objects.filter(
                customer=customer,
                txn_type='credit',
                created_at__gte=today_start,
            ).aggregate(total=Sum('points'))['total'] or Decimal('0')

            if today_earned + points > Decimal(str(max_daily)):
                return False, f'Daily earn limit ({max_daily}) would be exceeded.'
        except Exception:
            pass

        return True, ''

    @staticmethod
    def validate_redeem(
        customer,
        points: Decimal,
        locked_balance: Optional[Decimal] = None,
    ) -> Tuple[bool, str]:
        """
        Validate a points redemption।

        AUDIT FIX (v2): Added optional `locked_balance` parameter।
        When called from inside a select_for_update() block (e.g.,
        CashoutService.create_request()), the caller should pass the
        balance from the locked LoyaltyPoints row so this function does
        NOT perform a second independent DB read।  An independent read
        is vulnerable to the TOCTOU race: two concurrent cashouts can
        both pass the check before either commits the deduction।

        If locked_balance is None (default), the original DB-read
        behaviour is preserved for backward compatibility।
        """
        if points <= 0:
            return False, 'Redemption amount must be positive.'

        if not customer.is_active:
            return False, 'Customer account is not active.'

        try:
            if locked_balance is not None:
                # AUDIT FIX (v2): Use the pre-locked balance -- no second DB read।
                balance = locked_balance
            else:
                from .models.points import LoyaltyPoints
                lp = LoyaltyPoints.objects.filter(customer=customer).first()
                balance = lp.balance if lp else Decimal('0')

            if balance < points:
                return False, f'Insufficient points: {balance} available, {points} required.'
        except Exception as e:
            return False, f'Balance check failed: {e}'

        return True, ''

    @staticmethod
    def validate_cashout(customer, points: Decimal, method: str) -> Tuple[bool, str]:
        """Validate cashout request।"""
        # Check active
        if not customer.is_active:
            return False, 'Customer account is not active.'

        # Check verified
        if not getattr(customer, 'is_verified', True):
            return False, 'Customer account is not verified.'

        # Check balance using a regular (unlocked) read।
        # CashoutService will re-validate against the locked row in step 6।
        ok, msg = LoyaltyValidator.validate_redeem(customer, points)
        if not ok:
            return False, msg

        # Check fraud flags
        try:
            from .models.advanced import PointsAbuseLog
            flagged = PointsAbuseLog.objects.filter(
                customer=customer,
                is_resolved=False,
                risk_level__in=['high', 'critical'],
            ).exists()
            if flagged:
                return False, 'Cashout blocked: unresolved fraud flag on account.'
        except Exception:
            pass

        return True, ''

    @staticmethod
    def validate_points_transfer(sender, receiver, points: Decimal) -> Tuple[bool, str]:
        """Validate a points transfer between customers।"""
        if sender.id == receiver.id:
            return False, 'Cannot transfer points to yourself.'

        if not sender.is_active or not receiver.is_active:
            return False, 'Both customers must be active.'

        ok, msg = LoyaltyValidator.validate_redeem(sender, points)
        if not ok:
            return False, msg

        return True, ''

    @staticmethod
    def validate_referral(referrer, referred_customer) -> Tuple[bool, str]:
        """
        Validate a referral conversion।

        NOTE: The application-level exists() check here has a TOCTOU race
        condition (two concurrent requests both pass before either commits)।
        The DB-level UniqueConstraint `unique_referred_customer_active` added
        in migration 0014 is the hard backstop।  This check remains for
        user-friendly error messaging before hitting the DB constraint।
        """
        if referrer.id == referred_customer.id:
            return False, 'Cannot refer yourself.'

        # Check if already referred (application-level early exit)
        try:
            from .models.referral import ReferralConversion
            already = ReferralConversion.objects.filter(
                referred_customer=referred_customer,
                status__in=['approved', 'paid'],
            ).exists()
            if already:
                return False, 'This customer has already been referred.'
        except Exception:
            pass

        return True, ''

# api/wallet/services/withdrawal/WithdrawalLimitService.py
"""
Validates withdrawal amounts against tier-based limits.
Checks: min amount, max single amount, daily total, monthly total, daily count.
"""
import logging
from decimal import Decimal
from datetime import date

from django.db.models import Sum, Count
from django.utils import timezone

from ...models import WithdrawalLimit, WithdrawalRequest
from ...choices import WithdrawalStatus
from ...exceptions import WithdrawalLimitError, InvalidAmountError
from ...constants import MIN_WITHDRAWAL, MAX_WITHDRAWAL

logger = logging.getLogger("wallet.service.withdrawal_limit")


class WithdrawalLimitService:

    @staticmethod
    def validate(wallet, amount: Decimal, gateway: str = "ALL"):
        """
        Validate amount against all applicable limits.
        Raises WithdrawalLimitError or InvalidAmountError on violation.
        """
        amount = Decimal(str(amount))
        user   = wallet.user
        tier   = getattr(user, "tier", "FREE")

        # Absolute min/max
        if amount < MIN_WITHDRAWAL:
            raise InvalidAmountError(f"Minimum withdrawal: {MIN_WITHDRAWAL} BDT")
        if amount > MAX_WITHDRAWAL:
            raise InvalidAmountError(f"Maximum withdrawal: {MAX_WITHDRAWAL} BDT")

        # Available balance
        if amount > wallet.available_balance:
            from ...exceptions import InsufficientBalanceError
            raise InsufficientBalanceError(wallet.available_balance, amount)

        # Database-configured limits (tier + gateway + period)
        for limit in WithdrawalLimitService._get_applicable_limits(tier, gateway):
            WithdrawalLimitService._check_limit(wallet, amount, limit)

    @staticmethod
    def _get_applicable_limits(tier: str, gateway: str):
        """Return all WithdrawalLimit rows that apply to this tier + gateway."""
        from ...models import WithdrawalLimit
        return WithdrawalLimit.objects.filter(
            is_active=True,
            tier__in=[tier, "ALL"],
            gateway__in=[gateway, "ALL"],
        )

    @staticmethod
    def _check_limit(wallet, amount: Decimal, limit: WithdrawalLimit):
        """Check a single WithdrawalLimit row. Raises on violation."""
        user = wallet.user

        if amount < limit.min_amount:
            raise InvalidAmountError(
                f"Minimum withdrawal for {limit.gateway}: {limit.min_amount} BDT"
            )

        if amount > limit.max_single:
            raise WithdrawalLimitError(
                f"Maximum single withdrawal for {limit.gateway}: {limit.max_single} BDT"
            )

        # Period totals
        today      = date.today()
        period_qs  = WithdrawalRequest.objects.filter(
            user=user,
            status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED,
                        WithdrawalStatus.PROCESSING, WithdrawalStatus.COMPLETED],
        )

        if limit.period == "daily":
            period_qs = period_qs.filter(created_at__date=today)
        elif limit.period == "weekly":
            from datetime import timedelta
            week_start = today - timedelta(days=today.weekday())
            period_qs = period_qs.filter(created_at__date__gte=week_start)
        elif limit.period == "monthly":
            period_qs = period_qs.filter(
                created_at__year=today.year,
                created_at__month=today.month,
            )

        total_so_far = period_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        count_so_far = period_qs.count()

        if total_so_far + amount > limit.limit_amount:
            raise WithdrawalLimitError(
                f"{limit.period.capitalize()} withdrawal limit: {limit.limit_amount} BDT. "
                f"Used: {total_so_far}. Requested: {amount}."
            )

        if count_so_far >= limit.max_count:
            raise WithdrawalLimitError(
                f"{limit.period.capitalize()} withdrawal count limit: {limit.max_count}. "
                f"Used: {count_so_far}."
            )

    @staticmethod
    def get_remaining(user, wallet, gateway: str = "ALL") -> dict:
        """Return remaining limits for display in user dashboard."""
        tier    = getattr(user, "tier", "FREE")
        limits  = WithdrawalLimitService._get_applicable_limits(tier, gateway)
        today   = date.today()
        result  = {}

        for limit in limits:
            period_qs = WithdrawalRequest.objects.filter(
                user=user,
                status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED,
                            WithdrawalStatus.PROCESSING, WithdrawalStatus.COMPLETED],
            )
            if limit.period == "daily":
                period_qs = period_qs.filter(created_at__date=today)
            elif limit.period == "monthly":
                period_qs = period_qs.filter(
                    created_at__year=today.year, created_at__month=today.month
                )

            used = period_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
            count = period_qs.count()
            result[f"{limit.period}_{limit.gateway}"] = {
                "limit":     float(limit.limit_amount),
                "used":      float(used),
                "remaining": float(max(limit.limit_amount - used, Decimal("0"))),
                "count_limit": limit.max_count,
                "count_used":  count,
            }

        return result

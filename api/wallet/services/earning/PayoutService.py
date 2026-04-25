# api/wallet/services/earning/PayoutService.py
"""
CPAlead-style daily payout service.
  process_daily_payouts()  — pay everyone who earned $1+ today
  release_holds()          — release new publisher 30-day holds
  award_top_earner_bonuses()— monthly top earner bonus (up to 20%)
"""
import logging
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum

logger = logging.getLogger("wallet.service.payout")


class PayoutService:

    MIN_DAILY_PAYOUT = Decimal("1.00")   # CPAlead: $1 minimum

    @staticmethod
    @transaction.atomic
    def process_daily_payouts() -> dict:
        """
        CPAlead daily payment:
          earn $1+ today → paid tomorrow.
        Called by run_daily_payouts Celery task at 00:05.
        """
        from ..withdrawal.WithdrawalService import WithdrawalService
        from ...models.withdrawal import WithdrawalMethod
        from ...models_cpalead_extra import PayoutSchedule

        yesterday = date.today() - timedelta(days=1)
        processed = failed = skipped = 0

        for sched in PayoutSchedule.objects.filter(
            auto_payout=True, frequency="daily", hold_released=True,
        ).select_related("wallet__user"):
            wallet = sched.wallet
            try:
                # Check minimum
                if wallet.current_balance < sched.minimum_threshold:
                    skipped += 1
                    continue

                # Get primary payment method
                pm = WithdrawalMethod.objects.filter(
                    user=wallet.user, is_default=True, is_verified=True
                ).first()
                if not pm:
                    skipped += 1
                    continue

                # Create withdrawal
                wr = WithdrawalService.create(
                    wallet=wallet,
                    amount=wallet.current_balance,
                    payment_method=pm,
                    note=f"Daily auto-payout {date.today()}",
                )
                sched.last_payout_date   = date.today()
                sched.last_payout_amount = wallet.current_balance
                sched.total_payouts     += 1
                sched.save(update_fields=["last_payout_date","last_payout_amount","total_payouts","updated_at"])
                processed += 1

            except Exception as e:
                logger.error(f"Daily payout failed: user={wallet.user_id} err={e}")
                failed += 1

        logger.info(f"Daily payouts: processed={processed} failed={failed} skipped={skipped}")
        return {"processed": processed, "failed": failed, "skipped": skipped}

    @staticmethod
    @transaction.atomic
    def release_holds() -> int:
        """
        Release new publisher 30-day hold.
        Called daily at 2 AM.
        Returns count of released holds.
        """
        from ...models_cpalead_extra import PayoutSchedule
        cutoff = timezone.now() - timedelta(days=30)

        to_release = PayoutSchedule.objects.filter(
            hold_released=False,
            created_at__lte=cutoff,
        )
        count = to_release.count()
        to_release.update(hold_released=True)

        logger.info(f"Released {count} publisher holds")
        return count

    @staticmethod
    @transaction.atomic
    def award_top_earner_bonuses(period_days: int = 30) -> int:
        """
        CPAlead top earner bonus: top 5% earners get +20% bonus next month.
        Called on 1st of each month.
        Returns count of bonuses awarded.
        """
        from django.contrib.auth import get_user_model
        from ...models.core import WalletTransaction, Wallet
        from ...models_cpalead_extra import PerformanceBonus
        from django.utils import timezone
        from datetime import timedelta

        User = get_user_model()
        period_start = timezone.now() - timedelta(days=period_days)

        # Compute top earners
        earnings = WalletTransaction.objects.filter(
            type__in=["earning","reward","cpa","cpi","cpc","survey"],
            status="approved",
            created_at__gte=period_start,
        ).values("wallet__user").annotate(total=Sum("amount")).order_by("-total")

        total_earners = earnings.count()
        if total_earners < 5:
            return 0

        top_5pct = max(1, total_earners // 20)  # top 5%
        top_earners = earnings[:top_5pct]

        awarded = 0
        next_month_end = timezone.now() + timedelta(days=30)

        for entry in top_earners:
            try:
                wallet = Wallet.objects.get(user_id=entry["wallet__user"])
                # Expire old bonus
                PerformanceBonus.objects.filter(
                    user_id=entry["wallet__user"], bonus_type="top_earner", status="active"
                ).update(status="expired")

                PerformanceBonus.objects.create(
                    user_id=entry["wallet__user"],
                    wallet=wallet,
                    bonus_type="top_earner",
                    status="active",
                    bonus_percent=Decimal("20.00"),
                    period=f"top5pct_{date.today()}",
                    expires_at=next_month_end,
                    note=f"Top 5% earner: {entry['total']} BDT in {period_days}d",
                )
                awarded += 1
            except Exception as e:
                logger.error(f"Top earner bonus failed: {e}")

        logger.info(f"Top earner bonuses awarded: {awarded}/{total_earners}")
        return awarded

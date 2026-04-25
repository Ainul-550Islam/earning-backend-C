# api/wallet/services/WalletAnalyticsService.py
"""
Daily analytics computation service.
Computes WalletInsight, WithdrawalInsight, EarningInsight, LiabilityReport.
All methods are idempotent — can be re-run for the same date safely.
"""
import logging
from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum, Count, Avg, Max, Min, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from ..models import (
    Wallet, WalletTransaction, WithdrawalRequest, EarningRecord,
    WalletInsight, WithdrawalInsight, EarningInsight, LiabilityReport,
)
from ..choices import TransactionType, TransactionStatus, WithdrawalStatus, EarningSourceType

logger = logging.getLogger("wallet.service.analytics")


class WalletAnalyticsService:

    # ── WalletInsight ────────────────────────────────────────────────

    @staticmethod
    def compute_wallet_insight(wallet: Wallet, insight_date: date) -> WalletInsight:
        """
        Compute daily insight for a single wallet.
        Called per-wallet by compute_daily_insights Celery task.
        """
        start = timezone.datetime.combine(insight_date, timezone.datetime.min.time()).replace(tzinfo=timezone.utc)
        end   = timezone.datetime.combine(insight_date, timezone.datetime.max.time()).replace(tzinfo=timezone.utc)

        txns = WalletTransaction.objects.filter(
            wallet=wallet,
            created_at__range=(start, end),
            status__in=[TransactionStatus.APPROVED, TransactionStatus.COMPLETED],
        )

        credits    = txns.filter(amount__gt=0)
        debits     = txns.filter(amount__lt=0)
        earn_types = [TransactionType.EARNING, TransactionType.REWARD, TransactionType.CPA,
                      TransactionType.CPI, TransactionType.CPC, TransactionType.SURVEY]
        wd_types   = [TransactionType.WITHDRAWAL]

        total_credits = credits.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        total_debits  = abs(debits.aggregate(t=Sum("amount"))["t"] or Decimal("0"))

        # Opening balance = closing balance - net credits + net debits
        opening = wallet.current_balance - total_credits + total_debits

        # Earnings by source breakdown
        earning_records = EarningRecord.objects.filter(
            wallet=wallet, earned_at__date=insight_date
        )
        by_source = {}
        for record in earning_records:
            st = record.source_type
            by_source.setdefault(st, Decimal("0"))
            by_source[st] += record.amount

        insight, _ = WalletInsight.objects.update_or_create(
            wallet=wallet, date=insight_date,
            defaults=dict(
                opening_balance=opening,
                closing_balance=wallet.current_balance,
                peak_balance=max(opening, wallet.current_balance),
                total_credits=total_credits,
                total_credit_count=credits.count(),
                total_debits=total_debits,
                total_debit_count=debits.count(),
                txn_count=txns.count(),
                wd_count=txns.filter(type__in=wd_types).count(),
                earn_count=txns.filter(type__in=earn_types).count(),
                bonus_count=txns.filter(type=TransactionType.BONUS).count(),
                reversal_count=txns.filter(type=TransactionType.REVERSAL).count(),
                earnings_by_source={k: float(v) for k, v in by_source.items()},
                computed_at=timezone.now(),
            ),
        )
        return insight

    @staticmethod
    def compute_all_wallet_insights(insight_date: date = None) -> dict:
        """Compute WalletInsight for all wallets for a given date."""
        target = insight_date or date.today() - timedelta(days=1)
        ok = errors = 0
        for wallet in Wallet.objects.all():
            try:
                WalletAnalyticsService.compute_wallet_insight(wallet, target)
                ok += 1
            except Exception as e:
                errors += 1
                logger.error(f"WalletInsight error wallet={wallet.id}: {e}")
        return {"ok": ok, "errors": errors, "date": str(target)}

    # ── WithdrawalInsight ────────────────────────────────────────────

    @staticmethod
    def compute_withdrawal_insight(insight_date: date = None, currency: str = "BDT") -> WithdrawalInsight:
        """Platform-wide withdrawal analytics for a date."""
        target = insight_date or date.today() - timedelta(days=1)
        requests = WithdrawalRequest.objects.filter(created_at__date=target)

        completed = requests.filter(status=WithdrawalStatus.COMPLETED)
        rejected  = requests.filter(status=WithdrawalStatus.REJECTED)
        pending   = requests.filter(status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING])

        # Average processing time in minutes
        avg_time = Decimal("0")
        completed_with_time = completed.exclude(processed_at=None)
        if completed_with_time.exists():
            times = [(r.processed_at - r.created_at).total_seconds() / 60
                     for r in completed_with_time]
            avg_time = Decimal(str(sum(times) / len(times))).quantize(Decimal("0.01"))

        # By gateway breakdown
        from django.db.models import Value
        from django.db.models.functions import Coalesce
        by_gateway = {}
        gateways = requests.values_list("payment_method__method_type", flat=True).distinct()
        for gw in gateways:
            if gw:
                gw_qs = requests.filter(payment_method__method_type=gw)
                by_gateway[gw] = {
                    "count":  gw_qs.count(),
                    "amount": float(gw_qs.aggregate(t=Sum("amount"))["t"] or 0),
                }

        insight, _ = WithdrawalInsight.objects.update_or_create(
            date=target,
            defaults=dict(
                currency=currency,
                total_requested=requests.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
                total_processed=completed.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
                total_rejected=rejected.aggregate(t=Sum("amount"))["t"] or Decimal("0"),
                total_fees_collected=completed.aggregate(t=Sum("fee"))["t"] or Decimal("0"),
                request_count=requests.count(),
                completed_count=completed.count(),
                rejected_count=rejected.count(),
                pending_count=pending.count(),
                avg_time_to_process=avg_time,
                by_gateway=by_gateway,
                computed_at=timezone.now(),
            ),
        )
        return insight

    # ── EarningInsight ───────────────────────────────────────────────

    @staticmethod
    def compute_earning_insight(insight_date: date = None, currency: str = "BDT") -> EarningInsight:
        """Platform-wide earning analytics for a date."""
        target = insight_date or date.today() - timedelta(days=1)
        records = EarningRecord.objects.filter(earned_at__date=target)

        total         = records.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        total_events  = records.count()
        active_users  = records.values("wallet__user").distinct().count()
        avg_per_user  = (total / active_users).quantize(Decimal("0.0001")) if active_users else Decimal("0")
        avg_per_event = (total / total_events).quantize(Decimal("0.0001")) if total_events else Decimal("0")

        # By source breakdown
        by_source = {}
        top_source = top_source_amount = None
        for st in EarningSourceType:
            st_records = records.filter(source_type=st.value)
            count  = st_records.count()
            amount = st_records.aggregate(t=Sum("amount"))["t"] or Decimal("0")
            if count:
                by_source[st.value] = {"count": count, "amount": float(amount)}
                if top_source_amount is None or amount > top_source_amount:
                    top_source = st.value
                    top_source_amount = amount

        insight, _ = EarningInsight.objects.update_or_create(
            date=target,
            defaults=dict(
                currency=currency,
                total_earned=total,
                total_events=total_events,
                active_users=active_users,
                avg_per_user=avg_per_user,
                avg_per_event=avg_per_event,
                top_source=top_source or "",
                top_source_amount=top_source_amount or Decimal("0"),
                by_source=by_source,
                computed_at=timezone.now(),
            ),
        )
        return insight

    # ── LiabilityReport ─────────────────────────────────────────────

    @staticmethod
    def compute_liability(report_date: date = None, currency: str = "BDT") -> LiabilityReport:
        """
        Compute daily liability snapshot.
        Total = current + pending + frozen + bonus across all wallets.
        """
        target = report_date or date.today()
        agg = Wallet.objects.aggregate(
            total_current=Sum("current_balance"),
            total_pending=Sum("pending_balance"),
            total_frozen=Sum("frozen_balance"),
            total_bonus=Sum("bonus_balance"),
            total_reserved=Sum("reserved_balance"),
            total_wallets=Count("id"),
            locked_wallets=Count("id", filter=Q(is_locked=True)),
        )

        active_wallets = Wallet.objects.filter(current_balance__gt=0).count()

        pending_wds = WithdrawalRequest.objects.filter(
            status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING]
        )
        pending_wd_amount = pending_wds.aggregate(t=Sum("amount"))["t"] or Decimal("0")

        report, _ = LiabilityReport.objects.update_or_create(
            report_date=target,
            defaults=dict(
                currency=currency,
                total_current=agg["total_current"] or Decimal("0"),
                total_pending=agg["total_pending"] or Decimal("0"),
                total_frozen=agg["total_frozen"] or Decimal("0"),
                total_bonus=agg["total_bonus"] or Decimal("0"),
                total_reserved=agg["total_reserved"] or Decimal("0"),
                pending_wd_count=pending_wds.count(),
                pending_wd_amount=pending_wd_amount,
                total_wallets=agg["total_wallets"] or 0,
                active_wallets=active_wallets,
                locked_wallets=agg["locked_wallets"] or 0,
                generated_at=timezone.now(),
            ),
        )

        logger.info(f"Liability report: date={target} total={report.total_liability}")
        return report

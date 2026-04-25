# api/wallet/reporting/admin_report.py
"""Admin financial reports — liability, volume, fee income."""
import logging
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone

logger = logging.getLogger("wallet.reporting.admin")


class AdminReport:
    """Generate admin financial reports."""

    @staticmethod
    def daily_summary(report_date: date = None) -> dict:
        """Full daily financial summary."""
        if not report_date:
            report_date = date.today()
        from ..models.core import Wallet, WalletTransaction
        from ..models.withdrawal import WithdrawalRequest

        txns = WalletTransaction.objects.filter(
            created_at__date=report_date, status__in=["approved","completed"]
        )
        wds  = WithdrawalRequest.objects.filter(created_at__date=report_date)

        return {
            "date":                str(report_date),
            "total_wallets":       Wallet.objects.count(),
            "active_wallets":      Wallet.objects.filter(last_activity_at__date=report_date).count(),
            "locked_wallets":      Wallet.objects.filter(is_locked=True).count(),
            "total_credits":       float(txns.filter(amount__gt=0).aggregate(t=Sum("amount"))["t"] or 0),
            "total_debits":        float(txns.filter(amount__lt=0).aggregate(t=Sum("amount"))["t"] or 0),
            "total_txn_count":     txns.count(),
            "earning_txns":        txns.filter(type__in=["earning","reward","referral","cpa","cpi"]).count(),
            "total_earned":        float(txns.filter(type__in=["earning","reward","referral"]).aggregate(t=Sum("amount"))["t"] or 0),
            "withdrawals_pending": wds.filter(status="pending").count(),
            "withdrawals_approved":wds.filter(status="approved").count(),
            "withdrawals_done":    wds.filter(status="completed").count(),
            "withdrawal_volume":   float(wds.filter(status="completed").aggregate(t=Sum("amount"))["t"] or 0),
            "fee_income":          float(wds.filter(status="completed").aggregate(t=Sum("fee"))["t"] or 0),
            "total_liability":     float(Wallet.objects.aggregate(
                t=Sum("current_balance") + Sum("pending_balance") + Sum("bonus_balance"))["t"] or 0),
        }

    @staticmethod
    def top_earners(days: int = 30, limit: int = 20) -> list:
        """Top earners in the period."""
        from ..models.core import WalletTransaction
        cutoff = timezone.now() - timedelta(days=days)
        return list(WalletTransaction.objects.filter(
            type__in=["earning","reward","referral","cpa","cpi","cpc"],
            status__in=["approved","completed"],
            created_at__gte=cutoff,
        ).values("wallet__user__username").annotate(
            total=Sum("amount"), count=Count("id")
        ).order_by("-total")[:limit])

    @staticmethod
    def gateway_volume(days: int = 30) -> list:
        """Withdrawal volume by gateway."""
        from ..models.withdrawal import WithdrawalRequest
        from django.db.models.functions import TruncDate
        cutoff = timezone.now() - timedelta(days=days)
        return list(WithdrawalRequest.objects.filter(
            status="completed", created_at__gte=cutoff
        ).values("payment_method__method_type").annotate(
            volume=Sum("amount"), count=Count("id"), fees=Sum("fee")
        ).order_by("-volume"))

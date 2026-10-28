# api/wallet/analytics.py
"""Business analytics aggregations — platform-wide stats, trend analysis, cohort data."""
import logging
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone

logger = logging.getLogger("wallet.analytics")


class WalletAnalytics:
    """Platform-wide analytics aggregations."""

    @staticmethod
    def platform_overview(as_of: date = None) -> dict:
        """Complete platform financial overview."""
        from .models.core import Wallet, WalletTransaction
        from .models.withdrawal import WithdrawalRequest
        target = as_of or date.today()
        agg = Wallet.objects.aggregate(
            total_wallets=Count("id"), locked=Count("id", filter=Q(is_locked=True)),
            total_current=Sum("current_balance"), total_pending=Sum("pending_balance"),
            total_earned=Sum("total_earned"), total_withdrawn=Sum("total_withdrawn"),
            avg_balance=Avg("current_balance"),
        )
        today_earn = WalletTransaction.objects.filter(
            type__in=["earning","reward","cpa","cpi"], status="approved",
            created_at__date=target
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        today_wd = WalletTransaction.objects.filter(
            type="withdrawal", status__in=["approved","completed"],
            created_at__date=target
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        return {**{k: str(v) if isinstance(v, Decimal) else v for k, v in agg.items()},
                "today_earnings": str(today_earn), "today_withdrawals": str(abs(today_wd)),
                "pending_withdrawals": WithdrawalRequest.objects.filter(status="pending").count()}

    @staticmethod
    def daily_trend(days: int = 30) -> list:
        """Daily earnings + withdrawal trend for last N days."""
        from .models.core import WalletTransaction
        from django.db.models.functions import TruncDate
        cutoff = timezone.now() - timedelta(days=days)
        return list(WalletTransaction.objects.filter(
            created_at__gte=cutoff, status__in=["approved","completed"]
        ).annotate(day=TruncDate("created_at")).values("day").annotate(
            earnings=Sum("amount", filter=Q(type__in=["earning","reward","cpa","cpi"])),
            withdrawals=Sum("amount", filter=Q(type="withdrawal")),
            txn_count=Count("id"),
        ).order_by("day"))

    @staticmethod
    def top_gateways(days: int = 30) -> list:
        """Top withdrawal gateways by volume."""
        from .models.withdrawal import WithdrawalRequest
        cutoff = timezone.now() - timedelta(days=days)
        return list(WithdrawalRequest.objects.filter(
            status="completed", created_at__gte=cutoff
        ).values("payment_method__method_type").annotate(
            volume=Sum("amount"), count=Count("id"), fees=Sum("fee")
        ).order_by("-volume"))

    @staticmethod
    def user_cohort(cohort_month: str) -> dict:
        """Retention cohort analysis for users who joined in a given month."""
        from .models.core import Wallet
        year, month = map(int, cohort_month.split("-"))
        cohort_wallets = Wallet.objects.filter(
            created_at__year=year, created_at__month=month
        )
        total = cohort_wallets.count()
        active = cohort_wallets.filter(total_earned__gt=0).count()
        withdrawn = cohort_wallets.filter(total_withdrawn__gt=0).count()
        return {
            "cohort_month": cohort_month, "total_users": total,
            "active_earners": active, "withdrawers": withdrawn,
            "activation_rate": f"{active/total*100:.1f}%" if total else "0%",
            "withdrawal_rate": f"{withdrawn/total*100:.1f}%" if total else "0%",
        }

    @staticmethod
    def fee_income_summary(days: int = 30) -> dict:
        """Total fee income breakdown."""
        from .models.withdrawal import WithdrawalRequest
        cutoff = timezone.now() - timedelta(days=days)
        qs = WithdrawalRequest.objects.filter(status="completed", created_at__gte=cutoff)
        total_fee = qs.aggregate(t=Sum("fee"))["t"] or Decimal("0")
        by_gateway = list(qs.values("payment_method__method_type").annotate(
            fee_income=Sum("fee"), count=Count("id"), volume=Sum("amount")
        ).order_by("-fee_income"))
        return {"period_days": days, "total_fee_income": str(total_fee),
                "by_gateway": by_gateway}

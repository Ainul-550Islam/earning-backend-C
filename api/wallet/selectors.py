# api/wallet/selectors.py
"""
Selectors — read-only query layer (HackSoft Django Styleguide pattern).
https://github.com/HackSoftware/Django-Styleguide

Selectors ONLY read data. They NEVER mutate anything.
Services ONLY mutate data.
Views call selectors to READ and services to WRITE.

This separation makes testing trivially easy and prevents accidental mutations.

Usage in views:
    from .selectors import wallet_get_for_user, transactions_list_for_wallet
    wallet = wallet_get_for_user(user=request.user)
    txns   = transactions_list_for_wallet(wallet=wallet, filters=request.query_params)
"""
from decimal import Decimal
from typing import Optional
from django.db.models import QuerySet, Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta


# ══════════════════════════════════════════════════
# WALLET SELECTORS
# ══════════════════════════════════════════════════

def wallet_get_for_user(*, user) -> Optional[object]:
    """Get wallet for a specific user. Returns None if not found."""
    try:
        from .models.core import Wallet
        return Wallet.objects.select_related("user", "locked_by").get(user=user)
    except Exception:
        return None


def wallet_get_by_id(*, wallet_id: int) -> Optional[object]:
    """Get wallet by ID."""
    try:
        from .models.core import Wallet
        return Wallet.objects.select_related("user").get(id=wallet_id)
    except Exception:
        return None


def wallet_list(*, filters: dict = None) -> QuerySet:
    """List all wallets with optional filters."""
    from .models.core import Wallet
    qs = Wallet.objects.select_related("user").order_by("-created_at")
    if not filters:
        return qs
    if filters.get("is_locked") is not None:
        qs = qs.filter(is_locked=filters["is_locked"])
    if filters.get("currency"):
        qs = qs.filter(currency=filters["currency"])
    if filters.get("min_balance"):
        qs = qs.filter(current_balance__gte=Decimal(str(filters["min_balance"])))
    if filters.get("user_id"):
        qs = qs.filter(user_id=filters["user_id"])
    return qs


def wallet_balance_summary(*, wallet) -> dict:
    """Return all 5 balance types + totals for a wallet."""
    return {
        "current_balance":   str(wallet.current_balance),
        "pending_balance":   str(wallet.pending_balance),
        "frozen_balance":    str(wallet.frozen_balance),
        "bonus_balance":     str(wallet.bonus_balance),
        "reserved_balance":  getattr(wallet, "reserved_balance", Decimal("0")),
        "available_balance": str(wallet.available_balance),
        "total_balance":     str(
            wallet.current_balance
            + wallet.pending_balance
            + wallet.bonus_balance
        ),
        "total_earned":      str(wallet.total_earned),
        "total_withdrawn":   str(wallet.total_withdrawn),
        "is_locked":         wallet.is_locked,
        "currency":          wallet.currency,
    }


def wallet_total_liability() -> dict:
    """Aggregate total platform liability across all wallets."""
    from .models.core import Wallet
    return Wallet.objects.aggregate(
        total_current=Sum("current_balance"),
        total_pending=Sum("pending_balance"),
        total_frozen=Sum("frozen_balance"),
        total_bonus=Sum("bonus_balance"),
        total_wallets=Count("id"),
        locked_wallets=Count("id", filter=Q(is_locked=True)),
    )


# ══════════════════════════════════════════════════
# TRANSACTION SELECTORS
# ══════════════════════════════════════════════════

def transaction_list_for_wallet(*, wallet, filters: dict = None) -> QuerySet:
    """List transactions for a wallet, most recent first."""
    from .models.core import WalletTransaction
    qs = WalletTransaction.objects.select_related(
        "wallet__user", "created_by", "approved_by"
    ).filter(wallet=wallet).order_by("-created_at")

    if not filters:
        return qs
    if filters.get("type"):
        types = filters["type"].split(",") if isinstance(filters["type"], str) else [filters["type"]]
        qs = qs.filter(type__in=types)
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("date_from"):
        qs = qs.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(created_at__date__lte=filters["date_to"])
    if filters.get("min_amount"):
        qs = qs.filter(amount__gte=Decimal(str(filters["min_amount"])))
    return qs


def transaction_get(*, txn_id: str) -> Optional[object]:
    """Get single transaction by txn_id UUID."""
    try:
        from .models.core import WalletTransaction
        return WalletTransaction.objects.select_related(
            "wallet__user", "created_by", "approved_by"
        ).get(txn_id=txn_id)
    except Exception:
        return None


def transaction_daily_summary(*, wallet, date=None) -> dict:
    """Daily earning/withdrawal summary for a wallet."""
    from .models.core import WalletTransaction
    target_date = date or timezone.now().date()
    qs = WalletTransaction.objects.filter(
        wallet=wallet,
        status__in=["approved", "completed"],
        created_at__date=target_date,
    )
    earned = qs.filter(
        type__in=["earning", "reward", "referral", "bonus", "cpa", "cpi"]
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    withdrawn = qs.filter(type="withdrawal").aggregate(
        t=Sum("amount")
    )["t"] or Decimal("0")
    return {
        "date":              str(target_date),
        "earned":            str(earned),
        "withdrawn":         str(abs(withdrawn)),
        "transaction_count": qs.count(),
    }


# ══════════════════════════════════════════════════
# WITHDRAWAL SELECTORS
# ══════════════════════════════════════════════════

def withdrawal_list_for_user(*, user, filters: dict = None) -> QuerySet:
    """List withdrawals for a user."""
    from .models.withdrawal import WithdrawalRequest
    qs = WithdrawalRequest.objects.select_related(
        "user", "wallet", "payment_method", "processed_by"
    ).filter(user=user).order_by("-created_at")
    if filters and filters.get("status"):
        qs = qs.filter(status=filters["status"])
    return qs


def withdrawal_list_admin(*, filters: dict = None) -> QuerySet:
    """Admin: list all withdrawals with filters."""
    from .models.withdrawal import WithdrawalRequest
    qs = WithdrawalRequest.objects.select_related(
        "user", "wallet", "payment_method", "processed_by"
    ).order_by("-created_at")
    if not filters:
        return qs
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("gateway"):
        qs = qs.filter(payment_method__method_type=filters["gateway"])
    if filters.get("date_from"):
        qs = qs.filter(created_at__date__gte=filters["date_from"])
    return qs


def withdrawal_pending_count() -> int:
    """Count of pending withdrawals (for admin badge)."""
    from .models.withdrawal import WithdrawalRequest
    return WithdrawalRequest.objects.filter(status="pending").count()


def withdrawal_get(*, withdrawal_id: str) -> Optional[object]:
    """Get withdrawal by UUID."""
    try:
        from .models.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.select_related(
            "user", "wallet", "payment_method"
        ).get(withdrawal_id=withdrawal_id)
    except Exception:
        return None


# ══════════════════════════════════════════════════
# EARNING SELECTORS
# ══════════════════════════════════════════════════

def earning_breakdown_for_wallet(*, wallet, days: int = 30) -> dict:
    """Earning breakdown by source type for last N days."""
    from .models.earning import EarningRecord
    from django.db.models.functions import TruncDate

    cutoff = timezone.now() - timedelta(days=days)
    records = EarningRecord.objects.filter(
        wallet=wallet, earned_at__gte=cutoff
    )
    by_source = {}
    for r in records.values("source_type").annotate(
        total=Sum("amount"), count=Count("id")
    ):
        by_source[r["source_type"]] = {
            "total": str(r["total"]),
            "count": r["count"],
        }
    daily = list(records.annotate(date=TruncDate("earned_at")).values("date").annotate(
        total=Sum("amount"), count=Count("id")
    ).order_by("date"))

    return {
        "period_days": days,
        "by_source":   by_source,
        "daily_chart": [{"date": str(d["date"]), "total": str(d["total"])} for d in daily],
        "total":       str(records.aggregate(t=Sum("amount"))["t"] or Decimal("0")),
    }


def earning_top_earners(*, days: int = 30, limit: int = 20) -> list:
    """Top earners in the last N days."""
    from .models.earning import EarningRecord
    cutoff = timezone.now() - timedelta(days=days)
    return list(EarningRecord.objects.filter(
        earned_at__gte=cutoff
    ).values("wallet__user__username").annotate(
        total=Sum("amount"), txn_count=Count("id")
    ).order_by("-total")[:limit])


# ══════════════════════════════════════════════════
# NOTIFICATION SELECTORS
# ══════════════════════════════════════════════════

def notifications_for_user(*, user, unread_only: bool = False, limit: int = 20) -> QuerySet:
    """Get notifications for a user."""
    try:
        from .models.notification import WalletNotification
        qs = WalletNotification.objects.filter(user=user).order_by("-created_at")
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs[:limit]
    except Exception:
        return []


def notification_unread_count(*, user) -> int:
    """Count unread notifications."""
    try:
        from .models.notification import WalletNotification
        return WalletNotification.objects.filter(user=user, is_read=False).count()
    except Exception:
        return 0


# ══════════════════════════════════════════════════
# ANALYTICS SELECTORS
# ══════════════════════════════════════════════════

def platform_stats_today() -> dict:
    """Platform-wide stats for today (admin dashboard)."""
    from .models.core import Wallet, WalletTransaction
    from .models.withdrawal import WithdrawalRequest
    today = timezone.now().date()
    return {
        "total_wallets":        Wallet.objects.count(),
        "active_today":         Wallet.objects.filter(last_activity_at__date=today).count(),
        "locked_wallets":       Wallet.objects.filter(is_locked=True).count(),
        "pending_withdrawals":  WithdrawalRequest.objects.filter(status="pending").count(),
        "today_earnings":       str(WalletTransaction.objects.filter(
            type__in=["earning","reward","cpa","cpi"], status="approved",
            created_at__date=today,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")),
        "today_withdrawals":    str(abs(WalletTransaction.objects.filter(
            type="withdrawal", status__in=["approved","completed"],
            created_at__date=today,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0"))),
    }

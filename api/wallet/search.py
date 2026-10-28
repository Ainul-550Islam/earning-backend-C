# api/wallet/search.py
"""
Wallet search system — search across transactions, withdrawals,
users, audit logs. Uses Django ORM with Q objects for complex filters.

Usage:
    from .search import WalletSearch
    results = WalletSearch.transactions("01712345678", user=request.user)
"""
import logging
from decimal import Decimal
from typing import Optional
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("wallet.search")


class WalletSearch:
    """
    Centralized search across all wallet entities.
    All methods return QuerySets (lazy, chainable).
    """

    # ── Transaction search ────────────────────────────────────

    @staticmethod
    def transactions(query: str, user=None, limit: int = 50):
        """
        Search transactions by:
          - txn_id (UUID)
          - reference_id
          - description
          - amount (exact or partial)
        """
        from .models.core import WalletTransaction
        qs = WalletTransaction.objects.select_related(
            "wallet", "wallet__user", "created_by"
        )
        if user and not user.is_staff:
            qs = qs.filter(wallet__user=user)

        if not query:
            return qs.none()

        q = Q(txn_id__icontains=query) | Q(reference_id__icontains=query)
        if len(query) <= 20:
            q |= Q(description__icontains=query)
        try:
            amount = Decimal(str(query))
            q |= Q(amount=amount) | Q(amount=-amount)
        except Exception:
            pass

        return qs.filter(q).order_by("-created_at")[:limit]

    # ── Wallet search ──────────────────────────────────────────

    @staticmethod
    def wallets(query: str, admin_only: bool = True, limit: int = 50):
        """
        Admin: search wallets by username, email, or wallet ID.
        """
        from .models.core import Wallet
        if not admin_only:
            return Wallet.objects.none()

        qs = Wallet.objects.select_related("user")
        if not query:
            return qs.none()

        q = (
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) |
            Q(id__icontains=query)
        )
        try:
            wid = int(query)
            q |= Q(id=wid)
        except ValueError:
            pass

        return qs.filter(q).order_by("-created_at")[:limit]

    # ── Withdrawal search ─────────────────────────────────────

    @staticmethod
    def withdrawals(query: str, user=None, status: str = None, limit: int = 50):
        """
        Search withdrawals by:
          - withdrawal_id (UUID)
          - gateway_reference
          - account_number
          - username
        """
        from .models.withdrawal import WithdrawalRequest
        qs = WithdrawalRequest.objects.select_related(
            "user", "wallet", "payment_method", "processed_by"
        )
        if user and not user.is_staff:
            qs = qs.filter(user=user)
        if status:
            qs = qs.filter(status=status)

        if not query:
            return qs.order_by("-created_at")[:limit]

        q = (
            Q(withdrawal_id__icontains=query) |
            Q(gateway_reference__icontains=query) |
            Q(payment_method__account_number__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query)
        )
        try:
            amount = Decimal(str(query))
            q |= Q(amount=amount)
        except Exception:
            pass

        return qs.filter(q).order_by("-created_at")[:limit]

    # ── Earning records search ────────────────────────────────

    @staticmethod
    def earnings(query: str, user=None, source_type: str = None,
                 date_from=None, date_to=None, limit: int = 50):
        """Search earning records."""
        from .models.earning import EarningRecord
        qs = EarningRecord.objects.select_related("wallet", "wallet__user", "source")

        if user and not user.is_staff:
            qs = qs.filter(wallet__user=user)
        if source_type:
            qs = qs.filter(source_type=source_type)
        if date_from:
            qs = qs.filter(earned_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(earned_at__date__lte=date_to)

        if query:
            q = (
                Q(source_ref_id__icontains=query) |
                Q(country_code__iexact=query) |
                Q(wallet__user__username__icontains=query)
            )
            try:
                amount = Decimal(str(query))
                q |= Q(amount=amount)
            except Exception:
                pass
            qs = qs.filter(q)

        return qs.order_by("-earned_at")[:limit]

    # ── Audit log search ──────────────────────────────────────

    @staticmethod
    def audit_logs(query: str, action: str = None, target_type: str = None,
                   limit: int = 100):
        """Admin: search audit logs."""
        try:
            from .models.audit import AuditLog
            qs = AuditLog.objects.select_related("performed_by")

            if action:
                qs = qs.filter(action=action)
            if target_type:
                qs = qs.filter(target_type=target_type)
            if query:
                q = (
                    Q(detail__icontains=query) |
                    Q(performed_by__username__icontains=query) |
                    Q(ip_address__icontains=query)
                )
                try:
                    target_id = int(query)
                    q |= Q(target_id=target_id)
                except ValueError:
                    pass
                qs = qs.filter(q)

            return qs.order_by("-created_at")[:limit]
        except Exception:
            return []

    # ── Payment method search ─────────────────────────────────

    @staticmethod
    def payment_methods(query: str, user=None, verified_only: bool = False, limit: int = 20):
        """Search payment methods by account number or user."""
        from .models.withdrawal import WithdrawalMethod
        qs = WithdrawalMethod.objects.select_related("user")

        if user and not user.is_staff:
            qs = qs.filter(user=user)
        if verified_only:
            qs = qs.filter(is_verified=True)

        if query:
            q = (
                Q(account_number__icontains=query) |
                Q(account_name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(crypto_address__icontains=query)
            )
            qs = qs.filter(q)

        return qs.order_by("-is_default", "-created_at")[:limit]

    # ── Notification search ───────────────────────────────────

    @staticmethod
    def notifications(user, query: str = None, unread_only: bool = False,
                      event_type: str = None, limit: int = 20):
        """Search user notifications."""
        try:
            from .models.notification import WalletNotification
            qs = WalletNotification.objects.filter(user=user)
            if unread_only:
                qs = qs.filter(is_read=False)
            if event_type:
                qs = qs.filter(event_type=event_type)
            if query:
                qs = qs.filter(
                    Q(title__icontains=query) | Q(message__icontains=query)
                )
            return qs.order_by("-created_at")[:limit]
        except Exception:
            return []

    # ── Global search ─────────────────────────────────────────

    @staticmethod
    def global_search(query: str, user, is_admin: bool = False) -> dict:
        """
        Search across all wallet entities at once.
        Returns dict with results from each category.
        Used by admin dashboard and user search bar.
        """
        if not query or len(query) < 2:
            return {"query": query, "results": {}}

        results = {}

        if is_admin:
            wallets = WalletSearch.wallets(query, admin_only=True, limit=5)
            results["wallets"] = [
                {"id": w.id, "username": w.user.username,
                 "balance": str(w.current_balance), "is_locked": w.is_locked}
                for w in wallets
            ]

        txns = WalletSearch.transactions(query, user=user, limit=10)
        results["transactions"] = [
            {"txn_id": str(t.txn_id), "type": t.type,
             "amount": str(t.amount), "status": t.status,
             "created_at": str(t.created_at.date())}
            for t in txns
        ]

        wds = WalletSearch.withdrawals(query, user=user, limit=5)
        results["withdrawals"] = [
            {"withdrawal_id": str(w.withdrawal_id), "amount": str(w.amount),
             "status": w.status, "created_at": str(w.created_at.date())}
            for w in wds
        ]

        return {"query": query, "results": results}


class WalletFilter:
    """
    Advanced filter builder for wallet queries.
    Used by API filter backends and admin exports.
    """

    @staticmethod
    def build_transaction_filters(params: dict) -> Q:
        """Build Q object from filter params dict."""
        q = Q()
        if params.get("type"):
            q &= Q(type__in=params["type"].split(","))
        if params.get("status"):
            q &= Q(status__in=params["status"].split(","))
        if params.get("min_amount"):
            q &= Q(amount__gte=Decimal(params["min_amount"]))
        if params.get("max_amount"):
            q &= Q(amount__lte=Decimal(params["max_amount"]))
        if params.get("date_from"):
            q &= Q(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            q &= Q(created_at__date__lte=params["date_to"])
        if params.get("reference_id"):
            q &= Q(reference_id__icontains=params["reference_id"])
        if params.get("is_reversed") == "true":
            q &= Q(is_reversed=True)
        return q

    @staticmethod
    def build_withdrawal_filters(params: dict) -> Q:
        """Build Q object for withdrawal filters."""
        q = Q()
        if params.get("status"):
            q &= Q(status__in=params["status"].split(","))
        if params.get("gateway"):
            q &= Q(payment_method__method_type__in=params["gateway"].split(","))
        if params.get("min_amount"):
            q &= Q(amount__gte=Decimal(params["min_amount"]))
        if params.get("date_from"):
            q &= Q(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            q &= Q(created_at__date__lte=params["date_to"])
        if params.get("username"):
            q &= Q(user__username__icontains=params["username"])
        return q

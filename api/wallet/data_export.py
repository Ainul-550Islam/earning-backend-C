# api/wallet/data_export.py
"""
Data export service — GDPR-compliant user data export, bulk admin exports.
"""
import csv
import io
import json
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger("wallet.data_export")


class UserDataExporter:
    """GDPR Article 20: Right to data portability — export all user data."""

    @staticmethod
    def export_user_data(user) -> dict:
        """Export complete user wallet data as JSON (GDPR compliance)."""
        data = {"user_id": user.id, "username": user.username, "exported_at": timezone.now().isoformat()}
        try:
            from .models.core import Wallet, WalletTransaction
            wallet = Wallet.objects.filter(user=user).first()
            if wallet:
                data["wallet"] = {
                    "id": wallet.id, "currency": wallet.currency,
                    "current_balance": str(wallet.current_balance),
                    "total_earned": str(wallet.total_earned),
                    "total_withdrawn": str(wallet.total_withdrawn),
                    "created_at": wallet.created_at.isoformat(),
                }
                txns = WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")[:500]
                data["transactions"] = [
                    {"txn_id": str(t.txn_id), "type": t.type, "amount": str(t.amount),
                     "status": t.status, "created_at": t.created_at.isoformat()}
                    for t in txns
                ]
        except Exception as e:
            data["error"] = str(e)
        try:
            from .models.withdrawal import WithdrawalRequest, WithdrawalMethod
            wds = WithdrawalRequest.objects.filter(user=user).order_by("-created_at")[:100]
            data["withdrawals"] = [
                {"withdrawal_id": str(w.withdrawal_id), "amount": str(w.amount),
                 "status": w.status, "created_at": w.created_at.isoformat()}
                for w in wds
            ]
            methods = WithdrawalMethod.objects.filter(user=user)
            data["payment_methods"] = [
                {"type": m.method_type, "account_masked": f"****{m.account_number[-4:] if m.account_number else ''}",
                 "is_verified": m.is_verified}
                for m in methods
            ]
        except Exception: pass
        return data


class AdminBulkExporter:
    """Admin bulk export for finance/compliance teams."""

    @staticmethod
    def wallets_csv(active_only: bool = False) -> str:
        """Export all wallets as CSV."""
        from .models.core import Wallet
        from django.db.models import Sum
        qs = Wallet.objects.select_related("user")
        if active_only:
            qs = qs.filter(is_locked=False, total_earned__gt=0)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["user_id","username","email","current_balance","total_earned",
                          "total_withdrawn","is_locked","currency","created_at"])
        for w in qs:
            writer.writerow([w.user_id, w.user.username, w.user.email,
                              w.current_balance, w.total_earned, w.total_withdrawn,
                              w.is_locked, w.currency, w.created_at.date()])
        return out.getvalue()

    @staticmethod
    def withdrawal_report_csv(date_from=None, date_to=None, status: str = None) -> str:
        """Withdrawal report for finance team."""
        from .models.withdrawal import WithdrawalRequest
        qs = WithdrawalRequest.objects.select_related("user","payment_method","processed_by")
        if date_from: qs = qs.filter(created_at__date__gte=date_from)
        if date_to:   qs = qs.filter(created_at__date__lte=date_to)
        if status:    qs = qs.filter(status=status)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["withdrawal_id","username","amount","fee","net_amount","gateway",
                          "account","status","gateway_ref","created_at","processed_at"])
        for wr in qs.order_by("-created_at"):
            writer.writerow([str(wr.withdrawal_id), wr.user.username if wr.user else "",
                              wr.amount, wr.fee, wr.net_amount,
                              wr.payment_method.method_type if wr.payment_method else "",
                              wr.payment_method.account_number if wr.payment_method else "",
                              wr.status, wr.gateway_reference or "",
                              wr.created_at.date(), wr.processed_at.date() if wr.processed_at else ""])
        return out.getvalue()

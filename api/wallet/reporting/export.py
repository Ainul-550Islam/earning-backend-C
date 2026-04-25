# api/wallet/reporting/export.py
"""CSV/Excel export for transactions, withdrawals, earnings."""
import csv, io, logging
from datetime import datetime
from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger("wallet.reporting.export")


class WalletExporter:
    """Export wallet data to CSV or Excel."""

    @staticmethod
    def transactions_csv(wallet_id: int, date_from=None, date_to=None) -> str:
        """Export transactions as CSV."""
        from ..models.core import WalletTransaction
        qs = WalletTransaction.objects.filter(wallet_id=wallet_id).order_by("-created_at")
        if date_from: qs = qs.filter(created_at__date__gte=date_from)
        if date_to:   qs = qs.filter(created_at__date__lte=date_to)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date","Transaction ID","Type","Amount (BDT)","Fee","Status",
                          "Balance Before","Balance After","Description","Reference"])
        for txn in qs:
            writer.writerow([
                txn.created_at.strftime("%Y-%m-%d %H:%M"),
                str(txn.txn_id), txn.type, txn.amount,
                getattr(txn,"fee_amount",0), txn.status,
                txn.balance_before, txn.balance_after,
                txn.description[:100] if txn.description else "",
                txn.reference_id or "",
            ])
        return output.getvalue()

    @staticmethod
    def withdrawals_csv(date_from=None, date_to=None, status=None) -> str:
        """Admin export of all withdrawals as CSV."""
        from ..models.withdrawal import WithdrawalRequest
        qs = WithdrawalRequest.objects.select_related("user","wallet","payment_method").order_by("-created_at")
        if date_from: qs = qs.filter(created_at__date__gte=date_from)
        if date_to:   qs = qs.filter(created_at__date__lte=date_to)
        if status:    qs = qs.filter(status=status)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date","Withdrawal ID","Username","Amount (BDT)","Fee","Net","Gateway","Account","Status","Gateway Ref"])
        for wr in qs:
            writer.writerow([
                wr.created_at.strftime("%Y-%m-%d %H:%M"),
                str(wr.withdrawal_id),
                wr.user.username if wr.user else "",
                wr.amount, wr.fee, wr.net_amount,
                wr.payment_method.method_type if wr.payment_method else "",
                wr.payment_method.account_number if wr.payment_method else "",
                wr.status,
                wr.gateway_reference or "",
            ])
        return output.getvalue()

    @staticmethod
    def earnings_csv(wallet_id: int, days: int = 30) -> str:
        """Export earnings breakdown as CSV."""
        from ..models.earning import EarningRecord
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        qs = EarningRecord.objects.filter(wallet_id=wallet_id, earned_at__gte=cutoff).order_by("-earned_at")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date","Source Type","Amount (BDT)","Original Amount","Bonus %","Country"])
        for rec in qs:
            writer.writerow([
                rec.earned_at.strftime("%Y-%m-%d %H:%M"),
                rec.source_type, rec.amount, rec.original_amount,
                rec.bonus_percent or 0, rec.country_code or "",
            ])
        return output.getvalue()

    @staticmethod
    def as_http_response(content: str, filename: str) -> HttpResponse:
        """Wrap CSV content in Django HTTP response."""
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

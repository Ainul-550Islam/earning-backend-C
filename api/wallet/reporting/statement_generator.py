# api/wallet/reporting/statement_generator.py
"""Monthly account statement generator — CSV + PDF."""
import csv, io, logging
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

logger = logging.getLogger("wallet.reporting.statement")


class StatementGenerator:
    """Generate monthly/yearly account statements."""

    @staticmethod
    def generate(wallet, period_start: date, period_end: date,
                 period: str = "monthly") -> dict:
        """Generate statement for a wallet + period."""
        from ..models.core import WalletTransaction
        from ..models.statement import AccountStatement, StatementLine

        # Create statement record
        stmt, _ = AccountStatement.objects.get_or_create(
            wallet=wallet,
            period=period,
            period_start=period_start,
            defaults={
                "user": wallet.user,
                "period_end": period_end,
                "status": "generating",
            }
        )

        try:
            txns = WalletTransaction.objects.filter(
                wallet=wallet,
                created_at__date__gte=period_start,
                created_at__date__lte=period_end,
                status__in=["approved","completed"],
            ).order_by("created_at")

            # Calculate balances
            # Opening balance: wallet balance at start of period
            prev_txn = WalletTransaction.objects.filter(
                wallet=wallet,
                created_at__date__lt=period_start,
                status__in=["approved","completed"],
            ).order_by("-created_at").first()
            opening = prev_txn.balance_after if prev_txn else Decimal("0")

            total_credits = Decimal("0")
            total_debits  = Decimal("0")
            total_fees    = Decimal("0")
            running_bal   = opening

            # Statement lines
            lines = []
            for txn in txns:
                is_credit = txn.amount >= 0
                credit    = txn.amount if is_credit else Decimal("0")
                debit     = abs(txn.amount) if not is_credit else Decimal("0")
                running_bal = txn.balance_after or (running_bal + txn.amount)
                total_credits += credit
                total_debits  += debit
                if txn.type == "withdrawal_fee":
                    total_fees += abs(txn.amount)

                lines.append(StatementLine(
                    statement=stmt,
                    txn_id=str(txn.txn_id),
                    date=txn.created_at.date(),
                    description=txn.description or txn.get_type_display(),
                    txn_type=txn.type,
                    credit=credit,
                    debit=debit,
                    balance=running_bal,
                    reference=txn.reference_id or "",
                ))

            # Bulk create lines
            StatementLine.objects.filter(statement=stmt).delete()
            StatementLine.objects.bulk_create(lines, batch_size=500)

            # Update statement record
            stmt.opening_balance = opening
            stmt.closing_balance = running_bal
            stmt.total_credits   = total_credits
            stmt.total_debits    = total_debits
            stmt.total_fees      = total_fees
            stmt.txn_count       = len(lines)
            stmt.status          = "ready"
            stmt.generated_at    = timezone.now()
            stmt.save()

            logger.info(f"Statement generated: wallet={wallet.id} period={period_start}→{period_end}")
            return {"success": True, "statement_id": stmt.id, "txn_count": len(lines)}

        except Exception as e:
            stmt.status = "failed"
            stmt.save(update_fields=["status"])
            logger.error(f"Statement generation failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def to_csv(statement_id: int) -> str:
        """Export statement as CSV string."""
        from ..models.statement import AccountStatement, StatementLine
        try:
            stmt  = AccountStatement.objects.get(id=statement_id)
            lines = StatementLine.objects.filter(statement=stmt).order_by("date","id")

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Date","Description","Type","Credit (BDT)","Debit (BDT)","Balance (BDT)","Reference"])
            writer.writerow([f"Statement: {stmt.period_start} to {stmt.period_end}","","","","","",""])
            writer.writerow([f"Opening Balance: {stmt.opening_balance}","","","","","",""])
            for line in lines:
                writer.writerow([
                    line.date, line.description, line.txn_type,
                    line.credit or "", line.debit or "",
                    line.balance, line.reference,
                ])
            writer.writerow(["","TOTALS","",stmt.total_credits,stmt.total_debits,stmt.closing_balance,""])
            return output.getvalue()
        except Exception as e:
            logger.error(f"CSV export error: {e}")
            return ""

"""
INTEGRATIONS/accounting_integration.py — Accounting Software Integration
Supports: Tally, QuickBooks, local accounting
"""
import csv
import io
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


def export_transactions_for_accounting(tenant, from_date, to_date) -> str:
    """Export financial transactions in standard accounting CSV format."""
    from api.marketplace.models import PaymentTransaction, SellerPayout
    from api.marketplace.enums import PaymentStatus, PayoutStatus

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date","Type","Reference","Description","Debit","Credit","Account","Currency"
    ])

    # Revenue (successful payments)
    txns = PaymentTransaction.objects.filter(
        tenant=tenant, status=PaymentStatus.SUCCESS,
        completed_at__date__range=[from_date, to_date],
    )
    for tx in txns:
        writer.writerow([
            tx.completed_at.strftime("%Y-%m-%d"),
            "PAYMENT",
            str(tx.transaction_id)[:12],
            f"Order {tx.order.order_number}",
            str(tx.amount), "", "Revenue", "BDT",
        ])

    # Payouts (expenses)
    payouts = SellerPayout.objects.filter(
        tenant=tenant, status=PayoutStatus.COMPLETED,
        processed_at__date__range=[from_date, to_date],
    )
    for payout in payouts:
        writer.writerow([
            payout.processed_at.strftime("%Y-%m-%d"),
            "PAYOUT",
            f"PAYOUT-{payout.pk}",
            f"Seller Payout: {payout.seller.store_name}",
            "", str(payout.amount), "Expenses:SellerPayouts", "BDT",
        ])

    return output.getvalue()


def generate_profit_loss(tenant, from_date, to_date) -> dict:
    """Simple P&L statement."""
    from api.marketplace.models import PaymentTransaction, SellerPayout, OrderItem
    from api.marketplace.enums import PaymentStatus, PayoutStatus
    from django.db.models import Sum

    revenue = PaymentTransaction.objects.filter(
        tenant=tenant, status=PaymentStatus.SUCCESS,
        completed_at__date__range=[from_date, to_date],
        amount__gt=0,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    commissions = OrderItem.objects.filter(
        tenant=tenant, created_at__date__range=[from_date, to_date],
    ).aggregate(t=Sum("commission_amount"))["t"] or Decimal("0")

    payouts = SellerPayout.objects.filter(
        tenant=tenant, status=PayoutStatus.COMPLETED,
        processed_at__date__range=[from_date, to_date],
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    net_profit = commissions - (revenue - commissions - payouts)

    return {
        "period":          f"{from_date} to {to_date}",
        "gross_revenue":   str(revenue),
        "platform_commission": str(commissions),
        "seller_payouts":  str(payouts),
        "net_profit":      str(commissions),  # Platform keeps commission
        "currency":        "BDT",
    }

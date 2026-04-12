"""
DATABASE_MODELS/payment_table.py — Payment Table Reference & Queries
"""
from api.marketplace.models import PaymentTransaction, EscrowHolding, RefundRequest
from api.marketplace.enums import PaymentStatus, EscrowStatus, RefundStatus
from django.db.models import Sum, Count


def payment_dashboard(tenant) -> dict:
    txns    = PaymentTransaction.objects.filter(tenant=tenant, amount__gt=0)
    escrows = EscrowHolding.objects.filter(tenant=tenant)
    refunds = RefundRequest.objects.filter(tenant=tenant)
    return {
        "total_collected":   str(txns.filter(status=PaymentStatus.SUCCESS).aggregate(t=Sum("amount"))["t"] or 0),
        "escrow_holding":    str(escrows.filter(status=EscrowStatus.HOLDING).aggregate(t=Sum("net_amount"))["t"] or 0),
        "escrow_disputed":   str(escrows.filter(status=EscrowStatus.DISPUTED).aggregate(t=Sum("net_amount"))["t"] or 0),
        "pending_refunds":   refunds.filter(status=RefundStatus.REQUESTED).count(),
        "refunds_approved":  str(refunds.filter(status=RefundStatus.PROCESSED).aggregate(t=Sum("amount_approved"))["t"] or 0),
        "failed_payments":   txns.filter(status=PaymentStatus.FAILED).count(),
    }


__all__ = [
    "PaymentTransaction","EscrowHolding","RefundRequest",
    "payment_dashboard",
]

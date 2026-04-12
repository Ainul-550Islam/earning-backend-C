"""
DATABASE_MODELS/transaction_table.py — Financial Transaction Reference
"""
from api.marketplace.models import PaymentTransaction, EscrowHolding, RefundRequest
from api.marketplace.PAYMENT_SETTLEMENT.payment_split import PaymentSplitEngine, get_split_summary
from api.marketplace.PAYMENT_SETTLEMENT.settlement_report import generate_settlement_summary
from django.db.models import Sum, Count
from api.marketplace.enums import PaymentStatus


def daily_transaction_volume(tenant, date=None) -> dict:
    from django.utils import timezone
    d = date or timezone.now().date()
    qs = PaymentTransaction.objects.filter(tenant=tenant, initiated_at__date=d, amount__gt=0)
    agg = qs.aggregate(
        total=Sum("amount"),
        success=Sum("amount", filter=__import__("django.db.models",fromlist=["Q"]).Q(status=PaymentStatus.SUCCESS)),
        count=Count("id"),
    )
    return {
        "date":    str(d),
        "total":   str(agg["total"] or 0),
        "success": str(agg["success"] or 0),
        "count":   agg["count"] or 0,
    }


__all__ = [
    "PaymentTransaction","EscrowHolding","RefundRequest",
    "PaymentSplitEngine","get_split_summary","generate_settlement_summary",
    "daily_transaction_volume",
]

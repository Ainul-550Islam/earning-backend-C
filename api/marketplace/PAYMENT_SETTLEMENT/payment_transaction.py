"""
PAYMENT_SETTLEMENT/payment_transaction.py — Payment Transaction Management
===========================================================================
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from api.marketplace.models import PaymentTransaction
from api.marketplace.enums import PaymentStatus, PaymentMethod


def get_successful_transactions(tenant):
    return PaymentTransaction.objects.filter(tenant=tenant, status=PaymentStatus.SUCCESS)


def total_collected(tenant) -> Decimal:
    agg = get_successful_transactions(tenant).aggregate(t=Sum("amount"))
    return agg["t"] or Decimal("0")


def get_transaction_by_gateway_id(gateway_id: str) -> PaymentTransaction:
    return PaymentTransaction.objects.filter(gateway_transaction_id=gateway_id).first()


def get_user_transactions(user, tenant, limit: int = 50):
    return PaymentTransaction.objects.filter(
        user=user, tenant=tenant
    ).order_by("-initiated_at")[:limit]


def transaction_summary(tenant, from_date=None, to_date=None) -> dict:
    qs = PaymentTransaction.objects.filter(tenant=tenant, amount__gt=0)
    if from_date:
        qs = qs.filter(initiated_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(initiated_at__date__lte=to_date)

    agg = qs.aggregate(
        total=Sum("amount"),
        success_total=Sum("amount", filter=Q(status=PaymentStatus.SUCCESS)),
        failed_count=Count("id",  filter=Q(status=PaymentStatus.FAILED)),
        success_count=Count("id", filter=Q(status=PaymentStatus.SUCCESS)),
        refund_total=Sum("refunded_amount"),
    )
    total_count = qs.count()
    return {
        "total_volume":    str(agg["total"] or 0),
        "collected":       str(agg["success_total"] or 0),
        "refunded":        str(agg["refund_total"] or 0),
        "success_count":   agg["success_count"] or 0,
        "failed_count":    agg["failed_count"] or 0,
        "total_count":     total_count,
        "success_rate":    round((agg["success_count"] or 0) / max(1, total_count) * 100, 1),
    }


def method_breakdown(tenant) -> list:
    return list(
        PaymentTransaction.objects.filter(tenant=tenant, status=PaymentStatus.SUCCESS)
        .values("method")
        .annotate(count=Count("id"), volume=Sum("amount"))
        .order_by("-volume")
    )


def refund_transaction(tx: PaymentTransaction, amount: Decimal, reason: str = "") -> PaymentTransaction:
    """Mark a transaction as refunded."""
    tx.status = PaymentStatus.REFUNDED
    tx.refunded_amount = amount
    tx.refunded_at     = timezone.now()
    tx.failure_reason  = reason or "Refunded"
    tx.save(update_fields=["status","refunded_amount","refunded_at","failure_reason"])
    return tx


def detect_duplicate_payment(order, method: str, time_window_minutes: int = 5) -> bool:
    """Detect if a payment attempt is a duplicate within the time window."""
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=time_window_minutes)
    return PaymentTransaction.objects.filter(
        order=order, method=method,
        status__in=[PaymentStatus.PENDING, PaymentStatus.INITIATED, PaymentStatus.SUCCESS],
        initiated_at__gte=cutoff,
    ).exists()

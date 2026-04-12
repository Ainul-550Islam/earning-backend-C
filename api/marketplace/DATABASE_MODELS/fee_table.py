"""
DATABASE_MODELS/fee_table.py — Platform Fee Table Reference
"""
from api.marketplace.PAYMENT_SETTLEMENT.fee_manager import (
    PlatformFeeConfig, get_payment_processing_fee,
    get_withdrawal_fee, listing_fee_for_category,
    PAYMENT_PROCESSING_FEES,
)
from django.db.models import Sum


def fee_revenue(tenant, days: int = 30) -> dict:
    """Estimate platform fee revenue from processing fees."""
    from api.marketplace.models import PaymentTransaction
    from api.marketplace.enums import PaymentStatus
    from django.utils import timezone
    from decimal import Decimal
    since = timezone.now() - timezone.timedelta(days=days)
    txns  = PaymentTransaction.objects.filter(
        tenant=tenant, status=PaymentStatus.SUCCESS, completed_at__gte=since
    )
    total_fee = Decimal("0")
    for tx in txns:
        total_fee += get_payment_processing_fee(tx.method, tx.amount)
    return {"processing_fees": str(total_fee.quantize(Decimal("0.01"))), "days": days}


__all__ = [
    "PlatformFeeConfig","get_payment_processing_fee","get_withdrawal_fee",
    "listing_fee_for_category","PAYMENT_PROCESSING_FEES","fee_revenue",
]

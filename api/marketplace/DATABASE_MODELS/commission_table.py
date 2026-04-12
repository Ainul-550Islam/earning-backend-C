"""
DATABASE_MODELS/commission_table.py — Commission Table Reference
"""
from api.marketplace.models import CommissionConfig
from api.marketplace.PAYMENT_SETTLEMENT.commission_calculator import CommissionCalculator, calculate
from django.db.models import Sum, Avg
from api.marketplace.models import OrderItem


def commission_summary(tenant, days: int = 30) -> dict:
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    agg = OrderItem.objects.filter(tenant=tenant, created_at__gte=since).aggregate(
        total_commission=Sum("commission_amount"),
        total_gmv=Sum("subtotal"),
        avg_rate=Avg("commission_rate"),
    )
    return {
        "total_commission": str(agg["total_commission"] or 0),
        "total_gmv":        str(agg["total_gmv"] or 0),
        "avg_rate":         str(round(agg["avg_rate"] or 0, 2)) + "%",
        "take_rate":        round(
            (float(agg["total_commission"] or 0) / max(1, float(agg["total_gmv"] or 1))) * 100, 2
        ),
    }


__all__ = [
    "CommissionConfig","CommissionCalculator","calculate","commission_summary"
]

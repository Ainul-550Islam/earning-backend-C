"""
SELLER_MANAGEMENT/seller_commission.py — Seller Commission Helpers
"""
from decimal import Decimal
from django.db.models import Sum
from api.marketplace.models import CommissionConfig, OrderItem, SellerProfile
from api.marketplace.PAYMENT_SETTLEMENT.commission_calculator import CommissionCalculator


def get_commission_rate(category, tenant=None) -> Decimal:
    """Get applicable commission rate for a category."""
    calc = CommissionCalculator()
    rate, _ = calc.calculate(Decimal("100"), category, tenant)
    return rate


def seller_commission_history(seller: SellerProfile, days: int = 30) -> list:
    """Get commission paid by seller in recent period."""
    from django.utils import timezone
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        OrderItem.objects.filter(seller=seller, created_at__gte=since)
        .values("order__order_number","commission_rate","commission_amount","seller_net","created_at")
        .order_by("-created_at")[:100]
    )


def seller_commission_summary(seller: SellerProfile) -> dict:
    agg = OrderItem.objects.filter(seller=seller).aggregate(
        total_gmv=Sum("subtotal"),
        total_commission=Sum("commission_amount"),
        total_net=Sum("seller_net"),
    )
    gmv        = float(agg["total_gmv"] or 0)
    commission = float(agg["total_commission"] or 0)
    return {
        "total_gmv":        str(agg["total_gmv"] or 0),
        "total_commission": str(agg["total_commission"] or 0),
        "total_net":        str(agg["total_net"] or 0),
        "effective_rate":   round(commission / gmv * 100, 2) if gmv else 0,
    }


def preview_commission(amount: Decimal, category, tenant) -> dict:
    """Preview what commission will be charged before listing."""
    return CommissionCalculator.preview(amount, category, tenant)


def get_all_commission_configs(tenant) -> list:
    return list(
        CommissionConfig.objects.filter(tenant=tenant, is_active=True)
        .select_related("category")
        .order_by("category__level","category__name")
        .values("id","category__name","rate","flat_fee","effective_from")
    )

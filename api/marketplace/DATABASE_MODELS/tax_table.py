"""
DATABASE_MODELS/tax_table.py — Tax & VAT Table Reference
"""
from api.marketplace.PAYMENT_SETTLEMENT.tax_calculator import (
    calculate_vat, price_inclusive_of_vat, price_exclusive_of_vat,
    get_vat_rate, order_tax_breakdown, is_vat_exempt, vat_invoice_data, VAT_RATES
)
from api.marketplace.INTEGRATIONS.tax_provider_integration import (
    calculate_bd_vat, tax_breakdown, get_effective_tax_rate
)
from django.db.models import Sum
from api.marketplace.models import Order, OrderItem


def total_vat_collected(tenant, from_date=None, to_date=None) -> str:
    qs = OrderItem.objects.filter(tenant=tenant)
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)
    total_revenue = qs.aggregate(t=Sum("subtotal"))["t"] or 0
    from decimal import Decimal
    vat = (Decimal(str(total_revenue)) * Decimal("0.15")).quantize(Decimal("0.01"))
    return str(vat)


__all__ = [
    "calculate_vat","price_inclusive_of_vat","price_exclusive_of_vat",
    "get_vat_rate","order_tax_breakdown","is_vat_exempt","VAT_RATES",
    "calculate_bd_vat","tax_breakdown","get_effective_tax_rate",
    "total_vat_collected",
]

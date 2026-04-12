"""
PAYMENT_SETTLEMENT/tax_calculator.py — VAT & Tax Computation (Bangladesh)
==========================================================================
"""
from decimal import Decimal
from api.marketplace.constants import DEFAULT_VAT_RATE

# Bangladesh VAT rates by product type
VAT_RATES = {
    "default":      Decimal("0.15"),  # 15% standard
    "electronics":  Decimal("0.15"),
    "fashion":      Decimal("0.15"),
    "food":         Decimal("0.00"),  # exempt
    "medicine":     Decimal("0.00"),  # exempt
    "books":        Decimal("0.00"),  # exempt
    "software":     Decimal("0.15"),
    "mobile_phones":Decimal("0.15"),
}


def get_vat_rate(category_slug: str = "default") -> Decimal:
    return VAT_RATES.get(category_slug, VAT_RATES["default"])


def calculate_vat(amount: Decimal, category_slug: str = "default") -> Decimal:
    """Calculate VAT amount for a given price."""
    rate = get_vat_rate(category_slug)
    return (amount * rate).quantize(Decimal("0.01"))


def price_inclusive_of_vat(amount: Decimal, category_slug: str = "default") -> Decimal:
    """Calculate final price inclusive of VAT."""
    rate = get_vat_rate(category_slug)
    return (amount * (1 + rate)).quantize(Decimal("0.01"))


def price_exclusive_of_vat(vat_inclusive_price: Decimal, category_slug: str = "default") -> Decimal:
    """Extract base price from VAT-inclusive price."""
    rate = get_vat_rate(category_slug)
    return (vat_inclusive_price / (1 + rate)).quantize(Decimal("0.01"))


def order_tax_breakdown(order) -> dict:
    """Calculate full tax breakdown for an order."""
    from api.marketplace.models import OrderItem
    items = OrderItem.objects.filter(order=order).select_related("variant__product__category")
    total_tax = Decimal("0")
    line_items = []
    for item in items:
        cat_slug = item.variant.product.category.slug if item.variant and item.variant.product.category else "default"
        vat = calculate_vat(item.subtotal, cat_slug)
        total_tax += vat
        line_items.append({
            "product":    item.product_name,
            "subtotal":   str(item.subtotal),
            "vat_rate":   str(get_vat_rate(cat_slug) * 100) + "%",
            "vat_amount": str(vat),
        })
    return {
        "order_number": order.order_number,
        "line_items":   line_items,
        "total_tax":    str(total_tax.quantize(Decimal("0.01"))),
        "currency":     "BDT",
    }


def is_vat_exempt(category_slug: str) -> bool:
    return get_vat_rate(category_slug) == Decimal("0")


def vat_invoice_data(order) -> dict:
    """Generate data for a VAT invoice compliant with NBR requirements."""
    return {
        "invoice_title":   "TAX INVOICE",
        "invoice_number":  f"VATINV-{order.order_number}",
        "seller_name":     order.items.first().seller.store_name if order.items.exists() else "",
        "buyer_name":      order.shipping_name,
        "buyer_address":   order.shipping_address,
        "vat_breakdown":   order_tax_breakdown(order),
        "issue_date":      order.created_at.strftime("%Y-%m-%d"),
    }

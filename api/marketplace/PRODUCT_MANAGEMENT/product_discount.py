"""
PRODUCT_MANAGEMENT/product_discount.py — Product Discount Engine
=================================================================
Handles all discount types: campaign, sale price, bulk, combo, clearance.
"""
from decimal import Decimal
from typing import Optional
from django.utils import timezone


def apply_campaign_discount(price: Decimal, campaign) -> Decimal:
    """Apply a PromotionCampaign discount to a price."""
    if campaign.discount_type == "percent":
        discounted = price * (1 - campaign.discount_value / 100)
    else:
        discounted = price - campaign.discount_value
    return max(Decimal("0"), discounted).quantize(Decimal("0.01"))


def calculate_sale_discount(base_price: Decimal, sale_price: Decimal) -> dict:
    """Calculate discount amount and percentage between base and sale price."""
    if sale_price >= base_price or base_price == 0:
        return {"amount": Decimal("0"), "percent": 0}
    amount  = base_price - sale_price
    percent = round(amount / base_price * 100, 1)
    return {"amount": amount.quantize(Decimal("0.01")), "percent": percent}


def apply_bulk_discount(price: Decimal, quantity: int) -> Decimal:
    """
    Tiered bulk discount:
    5-9 units   → 5% off
    10-19 units → 10% off
    20+ units   → 15% off
    """
    if quantity >= 20:
        discount_pct = Decimal("15")
    elif quantity >= 10:
        discount_pct = Decimal("10")
    elif quantity >= 5:
        discount_pct = Decimal("5")
    else:
        return price

    discount = price * discount_pct / 100
    return (price - discount).quantize(Decimal("0.01"))


def get_best_price(product, quantity: int = 1, campaign=None, coupon=None) -> dict:
    """
    Resolve the best applicable price for a product.
    Priority: sale_price > campaign > bulk > base_price
    """
    base  = product.base_price
    price = product.effective_price  # sale_price if set, else base_price

    applied_discounts = []

    # Campaign discount on top of effective price
    if campaign and campaign.is_live:
        campaign_price = apply_campaign_discount(price, campaign)
        if campaign_price < price:
            applied_discounts.append(f"Campaign: {campaign.name}")
            price = campaign_price

    # Bulk discount
    if quantity >= 5:
        bulk_price = apply_bulk_discount(price, quantity)
        if bulk_price < price:
            applied_discounts.append(f"Bulk discount (qty {quantity})")
            price = bulk_price

    total_discount = base - price
    discount_pct   = round(total_discount / base * 100, 1) if base > 0 else 0

    return {
        "original_price":   str(base),
        "final_price":      str(price.quantize(Decimal("0.01"))),
        "discount_amount":  str(max(Decimal("0"), total_discount).quantize(Decimal("0.01"))),
        "discount_percent": discount_pct,
        "applied_discounts":applied_discounts,
        "line_total":       str((price * quantity).quantize(Decimal("0.01"))),
    }


def schedule_clearance(product, discount_percent: Decimal, duration_hours: int = 24) -> dict:
    """Mark product for clearance sale."""
    from datetime import timedelta
    starts = timezone.now()
    ends   = starts + timedelta(hours=duration_hours)
    sale_price = product.base_price * (1 - discount_percent / 100)
    product.sale_price = sale_price.quantize(Decimal("0.01"))
    product.save(update_fields=["sale_price"])
    return {
        "product_id":    product.pk,
        "sale_price":    str(product.sale_price),
        "discount":      f"{discount_percent}%",
        "starts":        starts.isoformat(),
        "ends":          ends.isoformat(),
    }


def remove_discount(product) -> None:
    """Remove sale price (revert to base price)."""
    product.sale_price = None
    product.save(update_fields=["sale_price"])

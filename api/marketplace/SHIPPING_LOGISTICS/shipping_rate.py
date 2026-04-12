"""
SHIPPING_LOGISTICS/shipping_rate.py — Shipping Rate Calculation
================================================================
"""
from decimal import Decimal
from api.marketplace.constants import FREE_SHIPPING_THRESHOLD, DEFAULT_SHIPPING_RATE

# Zone-based rates (BDT)
ZONE_RATES = {
    "inside_dhaka":   Decimal("60"),
    "outside_dhaka":  Decimal("110"),
    "divisional":     Decimal("100"),
    "remote":         Decimal("150"),
}

# Express delivery surcharge
EXPRESS_SURCHARGE = Decimal("50")

# Per-kg additional charge after 0.5kg
PER_KG_RATE = Decimal("20")


def get_shipping_rate(subtotal: Decimal, weight_grams: int = 0, zone: str = "outside_dhaka",
                      is_express: bool = False, free_shipping: bool = False) -> Decimal:
    """Calculate shipping rate based on subtotal, weight, and zone."""
    if free_shipping or subtotal >= Decimal(str(FREE_SHIPPING_THRESHOLD)):
        return Decimal("0.00")

    base_rate = ZONE_RATES.get(zone, Decimal(str(DEFAULT_SHIPPING_RATE)))

    # Weight surcharge (above 0.5kg)
    weight_kg = Decimal(str(weight_grams / 1000))
    extra_weight = max(Decimal("0"), weight_kg - Decimal("0.5"))
    weight_charge = (extra_weight * PER_KG_RATE).quantize(Decimal("0.01"))

    rate = base_rate + weight_charge

    if is_express:
        rate += EXPRESS_SURCHARGE

    return rate


def calculate_shipping_fee(order_amount: Decimal, weight_grams: int = 0,
                            delivery_city: str = "", is_express: bool = False) -> dict:
    """Full shipping fee calculation with zone detection."""
    from api.marketplace.SHIPPING_LOGISTICS.shipping_zone import get_zone_for_city

    zone = get_zone_for_city(delivery_city) if delivery_city else "outside_dhaka"
    fee  = get_shipping_rate(order_amount, weight_grams, zone, is_express)

    is_free = fee == Decimal("0.00")
    reason  = "Free shipping on orders above 500 BDT" if is_free else ""

    return {
        "shipping_fee":     str(fee),
        "is_free":          is_free,
        "zone":             zone,
        "base_rate":        str(ZONE_RATES.get(zone, DEFAULT_SHIPPING_RATE)),
        "weight_grams":     weight_grams,
        "is_express":       is_express,
        "free_reason":      reason,
        "estimated_days":   _estimate_days(zone, is_express),
    }


def _estimate_days(zone: str, is_express: bool) -> str:
    days_map = {
        "inside_dhaka":   ("Same day", "Next day"),
        "outside_dhaka":  ("2-3 days", "1-2 days"),
        "divisional":     ("2-3 days", "1-2 days"),
        "remote":         ("4-7 days", "2-4 days"),
    }
    regular, express = days_map.get(zone, ("3-5 days", "2-3 days"))
    return express if is_express else regular


def get_all_zone_rates() -> dict:
    """Return all zone rates for display."""
    return {k: str(v) for k, v in ZONE_RATES.items()}


def free_shipping_progress(subtotal: Decimal) -> dict:
    """Progress toward free shipping threshold."""
    threshold = Decimal(str(FREE_SHIPPING_THRESHOLD))
    if subtotal >= threshold:
        return {"achieved": True, "remaining": "0", "progress_pct": 100}
    remaining = threshold - subtotal
    progress  = int(subtotal / threshold * 100)
    return {
        "achieved":     False,
        "remaining":    str(remaining.quantize(Decimal("0.01"))),
        "progress_pct": progress,
        "threshold":    str(threshold),
        "message":      f"Add {remaining.quantize(Decimal('0.01'))} BDT more for free shipping!",
    }

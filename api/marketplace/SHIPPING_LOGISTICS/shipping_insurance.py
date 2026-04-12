"""
SHIPPING_LOGISTICS/shipping_insurance.py — Shipping Insurance Management
"""
from decimal import Decimal


INSURANCE_RATE = Decimal("0.015")   # 1.5% of declared value
MIN_PREMIUM    = Decimal("10.00")   # minimum 10 BDT
MAX_COVERAGE   = Decimal("50000")   # max 50,000 BDT


def calculate_premium(declared_value: Decimal) -> Decimal:
    """Calculate insurance premium for a shipment."""
    premium = declared_value * INSURANCE_RATE
    return max(MIN_PREMIUM, min(premium, declared_value * INSURANCE_RATE)).quantize(Decimal("0.01"))


def is_eligible(order_value: Decimal) -> bool:
    """Orders above 1000 BDT are eligible for shipping insurance."""
    return order_value >= Decimal("1000")


def insurance_options(order_value: Decimal) -> list:
    """Return available insurance options for an order."""
    if not is_eligible(order_value):
        return []
    premium = calculate_premium(order_value)
    return [
        {
            "id":          "basic",
            "name":        "Basic Coverage",
            "coverage":    str(min(order_value, MAX_COVERAGE)),
            "premium":     str(premium),
            "description": "Covers loss or damage during transit",
        },
        {
            "id":          "extended",
            "name":        "Extended Coverage",
            "coverage":    str(min(order_value * 2, MAX_COVERAGE)),
            "premium":     str(premium * Decimal("1.5")),
            "description": "Covers loss, damage, and theft",
        },
    ]

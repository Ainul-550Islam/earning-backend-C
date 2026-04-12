# api/publisher_tools/payment_settlement/withholding_tax.py
"""Withholding Tax — Tax calculation per country."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

WITHHOLDING_TAX_RATES = {
    "US":  Decimal("30.00"),
    "GB":  Decimal("20.00"),
    "CA":  Decimal("25.00"),
    "AU":  Decimal("10.00"),
    "IN":  Decimal("10.00"),
    "BD":  Decimal("10.00"),
    "PK":  Decimal("10.00"),
    "NG":  Decimal("10.00"),
    "GH":  Decimal("8.00"),
    "KE":  Decimal("5.00"),
    "SG":  Decimal("0.00"),
    "AE":  Decimal("0.00"),
    "DEFAULT": Decimal("0.00"),
}

TREATY_RATES = {
    ("US", "IN"): Decimal("15.00"),
    ("US", "PK"): Decimal("12.00"),
    ("US", "BD"): Decimal("10.00"),
}


def calculate_withholding_tax(amount: Decimal, country: str, has_w8: bool = False) -> Dict:
    rate = WITHHOLDING_TAX_RATES.get(country.upper(), WITHHOLDING_TAX_RATES["DEFAULT"])
    if has_w8 and country.upper() != "US":
        rate = Decimal("0.00")
    tax = (amount * rate / 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return {
        "gross_amount": float(amount),
        "country": country,
        "tax_rate_pct": float(rate),
        "tax_amount": float(tax),
        "net_amount": float(amount - tax),
        "has_w8_form": has_w8,
    }


def get_tax_rate(country: str, has_treaty: bool = False) -> Decimal:
    rate = WITHHOLDING_TAX_RATES.get(country.upper(), WITHHOLDING_TAX_RATES["DEFAULT"])
    return rate


def is_tax_exempt(country: str) -> bool:
    return WITHHOLDING_TAX_RATES.get(country.upper(), Decimal("0")) == Decimal("0")

# api/publisher_tools/payment_settlement/currency_converter.py
"""Currency Converter — Multi-currency support."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict
from django.core.cache import cache


# Static fallback rates (production-এ live API থেকে fetch করো)
FALLBACK_RATES_TO_USD = {
    "USD": Decimal("1.0000"), "EUR": Decimal("1.0850"), "GBP": Decimal("1.2700"),
    "BDT": Decimal("0.0091"), "INR": Decimal("0.0120"), "PKR": Decimal("0.0035"),
    "CAD": Decimal("0.7400"), "AUD": Decimal("0.6600"), "SGD": Decimal("0.7400"),
    "AED": Decimal("0.2720"), "SAR": Decimal("0.2670"), "MYR": Decimal("0.2130"),
}


def get_exchange_rate(from_currency: str, to_currency: str = "USD") -> Decimal:
    """Exchange rate fetch করে। Cache থেকে serve করে।"""
    cache_key = f"fx:{from_currency}:{to_currency}"
    cached = cache.get(cache_key)
    if cached:
        return Decimal(str(cached))
    if from_currency == to_currency:
        return Decimal("1.0000")
    from_rate = FALLBACK_RATES_TO_USD.get(from_currency.upper(), Decimal("1.0"))
    to_rate   = FALLBACK_RATES_TO_USD.get(to_currency.upper(), Decimal("1.0"))
    rate = (from_rate / to_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    cache.set(cache_key, float(rate), 3600)
    return rate


def convert(amount: Decimal, from_currency: str, to_currency: str = "USD") -> Dict:
    rate = get_exchange_rate(from_currency, to_currency)
    converted = (amount * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return {
        "original_amount": float(amount),
        "original_currency": from_currency.upper(),
        "converted_amount": float(converted),
        "target_currency": to_currency.upper(),
        "exchange_rate": float(rate),
    }


def format_amount(amount: Decimal, currency: str) -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "BDT": "৳", "INR": "₹"}
    symbol = symbols.get(currency.upper(), currency.upper() + " ")
    return f"{symbol}{float(amount):,.2f}"

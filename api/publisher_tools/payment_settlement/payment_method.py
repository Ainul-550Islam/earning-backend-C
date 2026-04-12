# api/publisher_tools/payment_settlement/payment_method.py
"""Payment Method — Payment method validation and management."""
from decimal import Decimal
from typing import Dict


PAYMENT_METHOD_FEES = {
    "bkash":         {"flat": Decimal("0.50"),  "pct": Decimal("0")},
    "nagad":         {"flat": Decimal("0.50"),  "pct": Decimal("0")},
    "rocket":        {"flat": Decimal("0.50"),  "pct": Decimal("0")},
    "paypal":        {"flat": Decimal("1.00"),  "pct": Decimal("2.00")},
    "bank_transfer": {"flat": Decimal("5.00"),  "pct": Decimal("0")},
    "wire":          {"flat": Decimal("25.00"), "pct": Decimal("0")},
    "payoneer":      {"flat": Decimal("3.00"),  "pct": Decimal("0")},
    "crypto_usdt":   {"flat": Decimal("1.00"),  "pct": Decimal("0")},
    "crypto_btc":    {"flat": Decimal("5.00"),  "pct": Decimal("0")},
}

PAYMENT_METHOD_MIN_THRESHOLDS = {
    "bkash": 5.0, "nagad": 5.0, "rocket": 5.0, "paypal": 10.0,
    "bank_transfer": 100.0, "wire": 500.0, "payoneer": 50.0,
    "crypto_usdt": 10.0, "crypto_btc": 50.0,
}


def calculate_fee(payment_method: str, amount: Decimal) -> Dict:
    fees = PAYMENT_METHOD_FEES.get(payment_method, {"flat": Decimal("0"), "pct": Decimal("0")})
    flat = fees["flat"]
    pct_amount = amount * (fees["pct"] / 100)
    total_fee = flat + pct_amount
    net = max(Decimal("0"), amount - total_fee)
    return {"gross": float(amount), "flat_fee": float(flat), "pct_fee": float(pct_amount), "total_fee": float(total_fee), "net": float(net)}


def validate_payment_details(payment_method: str, details: dict) -> Dict:
    required_fields = {
        "bkash":         ["phone_number"],
        "nagad":         ["phone_number"],
        "rocket":        ["phone_number"],
        "paypal":        ["email"],
        "bank_transfer": ["account_number", "bank_name"],
        "wire":          ["account_number", "swift_code", "bank_name"],
        "payoneer":      ["payoneer_id"],
        "crypto_usdt":   ["wallet_address", "network"],
        "crypto_btc":    ["wallet_address"],
    }
    required = required_fields.get(payment_method, [])
    missing = [f for f in required if not details.get(f)]
    return {"valid": len(missing) == 0, "missing_fields": missing}


def get_minimum_threshold(payment_method: str) -> float:
    return PAYMENT_METHOD_MIN_THRESHOLDS.get(payment_method, 10.0)

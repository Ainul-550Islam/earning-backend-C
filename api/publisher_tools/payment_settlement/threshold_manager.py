# api/publisher_tools/payment_settlement/threshold_manager.py
"""Threshold Manager — Payout threshold management."""
from decimal import Decimal
from typing import Dict, List


DEFAULT_THRESHOLDS = {
    "bkash": Decimal("5.00"), "nagad": Decimal("5.00"), "rocket": Decimal("5.00"),
    "paypal": Decimal("10.00"), "bank_transfer": Decimal("100.00"), "wire": Decimal("500.00"),
    "payoneer": Decimal("50.00"), "crypto_usdt": Decimal("10.00"), "crypto_btc": Decimal("50.00"),
}


def get_effective_threshold(publisher, payment_method: str) -> Decimal:
    from api.publisher_tools.models import PayoutThreshold
    threshold = PayoutThreshold.objects.filter(publisher=publisher, payment_method=payment_method, is_primary=True).first()
    if threshold:
        return threshold.minimum_threshold
    return DEFAULT_THRESHOLDS.get(payment_method, Decimal("10.00"))


def check_threshold_met(publisher, payment_method: str = None) -> Dict:
    from api.publisher_tools.models import PayoutThreshold
    if payment_method:
        threshold_val = get_effective_threshold(publisher, payment_method)
    else:
        primary = PayoutThreshold.objects.filter(publisher=publisher, is_primary=True).first()
        threshold_val = primary.minimum_threshold if primary else Decimal("100.00")
        payment_method = primary.payment_method if primary else "bank_transfer"
    available = publisher.available_balance
    met = available >= threshold_val
    return {
        "met": met, "available": float(available), "threshold": float(threshold_val),
        "payment_method": payment_method, "gap": float(max(Decimal("0"), threshold_val - available)),
    }


def get_all_thresholds(publisher) -> List[Dict]:
    from api.publisher_tools.models import PayoutThreshold
    return list(
        PayoutThreshold.objects.filter(publisher=publisher).values(
            "payment_method", "minimum_threshold", "payment_frequency", "is_primary", "is_verified"
        )
    )

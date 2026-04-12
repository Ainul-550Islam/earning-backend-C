"""MARKETPLACE_SAFETY/fraud_detection.py — Fraud detection helpers"""
from api.marketplace.models import Order, PaymentTransaction
from api.marketplace.enums import PaymentStatus
from django.db.models import Count


FRAUD_SIGNALS = {
    "multiple_failed_payments": 3,
    "orders_per_day_limit": 10,
}


def check_fraud_signals(user, tenant) -> list:
    """Returns list of triggered fraud signals."""
    signals = []
    failed_txns = PaymentTransaction.objects.filter(
        user=user, tenant=tenant, status=PaymentStatus.FAILED
    ).count()
    if failed_txns >= FRAUD_SIGNALS["multiple_failed_payments"]:
        signals.append(f"HIGH_FAILED_PAYMENTS: {failed_txns} failed transactions")

    from django.utils import timezone
    today_orders = Order.objects.filter(
        user=user, tenant=tenant,
        created_at__date=timezone.now().date()
    ).count()
    if today_orders >= FRAUD_SIGNALS["orders_per_day_limit"]:
        signals.append(f"HIGH_ORDER_RATE: {today_orders} orders today")

    return signals

"""ORDER_MANAGEMENT/order_payment.py — Order Payment Helpers"""
from api.marketplace.models import Order, PaymentTransaction
from api.marketplace.enums import PaymentStatus


def get_payment_status(order: Order) -> dict:
    txn = PaymentTransaction.objects.filter(order=order).order_by("-initiated_at").first()
    return {
        "is_paid": order.is_paid,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "method": order.payment_method,
        "transaction_id": str(txn.transaction_id) if txn else None,
        "gateway_ref": txn.gateway_transaction_id if txn else None,
        "status": txn.status if txn else None,
    }


def mark_cod_collected(order: Order, collected_by=None):
    """Mark Cash on Delivery as collected by rider."""
    order.is_paid = True
    order.payment_method = "cod"
    from django.utils import timezone
    order.paid_at = timezone.now()
    order.save(update_fields=["is_paid", "paid_at", "payment_method"])
    PaymentTransaction.objects.create(
        tenant=order.tenant, order=order, user=order.user,
        method="cod", amount=order.total_price, currency="BDT",
        status=PaymentStatus.SUCCESS,
        completed_at=order.paid_at,
        gateway_response={"collected_by": str(collected_by)},
    )
    return order

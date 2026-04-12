"""PAYMENT_PROCESSING/refund_manager.py — Refund processing manager."""
import logging
from decimal import Decimal
from ..models import PaymentTransaction

logger = logging.getLogger(__name__)


class RefundManager:
    """Handles refund requests for payment transactions."""

    @classmethod
    def initiate(cls, transaction_id: str, amount: Decimal = None,
                  reason: str = "") -> dict:
        try:
            txn = PaymentTransaction.objects.get(txn_id=transaction_id, status="success")
        except PaymentTransaction.DoesNotExist:
            return {"success": False, "error": "Transaction not found or not eligible."}

        refund_amount = amount or txn.amount
        if refund_amount > txn.amount:
            return {"success": False, "error": "Refund amount exceeds transaction amount."}

        try:
            from .payment_gateway import BasePaymentGateway
            gw     = BasePaymentGateway.gateway_for(txn.gateway)
            result = gw.refund(str(txn.txn_id), refund_amount)
            PaymentTransaction.objects.filter(pk=txn.pk).update(status="refunded")
            logger.info("Refund processed: txn=%s amount=%s", transaction_id, refund_amount)
            return {"success": True, "refund_amount": str(refund_amount), "gateway_result": result}
        except Exception as e:
            logger.error("Refund failed: txn=%s error=%s", transaction_id, e)
            return {"success": False, "error": str(e)}

    @classmethod
    def eligible(cls, txn) -> bool:
        from datetime import timedelta
        from django.utils import timezone
        return (txn.status == "success" and
                txn.completed_at and
                (timezone.now() - txn.completed_at).days <= 30)

"""PAYMENT_PROCESSING/dispute_manager.py — Payment dispute handling."""
import logging
from ..models import PaymentTransaction

logger = logging.getLogger(__name__)


class DisputeManager:
    """Manages payment disputes and chargebacks."""

    @classmethod
    def open_dispute(cls, transaction_id: str, user, reason: str) -> dict:
        try:
            txn = PaymentTransaction.objects.get(txn_id=transaction_id, user=user)
        except PaymentTransaction.DoesNotExist:
            return {"success": False, "error": "Transaction not found."}
        PaymentTransaction.objects.filter(pk=txn.pk).update(status="disputed")
        logger.warning("Dispute opened: txn=%s user=%s reason=%s",
                        transaction_id, user.id, reason)
        return {"success": True, "status": "disputed", "transaction_id": transaction_id}

    @classmethod
    def resolve(cls, transaction_id: str, resolution: str = "merchant_wins") -> dict:
        final_status = "refunded" if resolution == "customer_wins" else "success"
        updated = PaymentTransaction.objects.filter(
            txn_id=transaction_id, status="disputed"
        ).update(status=final_status)
        return {"updated": bool(updated), "resolution": resolution, "final_status": final_status}

    @classmethod
    def open_disputes(cls, tenant=None) -> list:
        qs = PaymentTransaction.objects.filter(status="disputed")
        if tenant:
            qs = qs.filter(tenant=tenant)
        return list(qs.select_related("user").order_by("-initiated_at").values(
            "txn_id", "user__username", "amount", "currency", "initiated_at"
        ))

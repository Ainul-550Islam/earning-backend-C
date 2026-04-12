"""
PAYMENT_SETTLEMENT/dispute_resolution.py — Payment-layer Dispute Hooks
Re-exports dispute resolution for use within the payment settlement context.
Prevents circular imports by being an adapter layer.
"""
from api.marketplace.DISPUTE_RESOLUTION.dispute_resolution import (
    DisputeResolutionService,
    DisputeWindowExpired,
    DisputeAlreadyExists,
    DisputeNotOpen,
    RefundBeforeArbitration,
    DISPUTE_WINDOW_DAYS,
)
from api.marketplace.DISPUTE_RESOLUTION.dispute_model import (
    Dispute, DisputeMessage, DisputeEvidence, DisputeArbitration
)


def freeze_escrow_on_dispute(dispute: Dispute):
    """Freeze escrow when a dispute is raised."""
    from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager
    from api.marketplace.models import EscrowHolding
    try:
        escrow = EscrowHolding.objects.get(order_item=dispute.order_item)
        EscrowManager.freeze_for_dispute(escrow)
    except EscrowHolding.DoesNotExist:
        pass


def release_or_refund_on_verdict(dispute: Dispute, verdict: str, admin_user):
    """After admin arbitration, resolve the escrow accordingly."""
    from api.marketplace.PAYMENT_SETTLEMENT.escrow_manager import EscrowManager
    from api.marketplace.models import EscrowHolding
    from api.marketplace.enums import EscrowStatus
    try:
        escrow = EscrowHolding.objects.get(
            order_item=dispute.order_item, status=EscrowStatus.DISPUTED
        )
        decision = "release" if verdict == "seller_wins" else "refund"
        EscrowManager.admin_resolve(escrow, decision, admin_user)
    except EscrowHolding.DoesNotExist:
        pass


__all__ = [
    "DisputeResolutionService","Dispute","DisputeMessage","DisputeEvidence",
    "DisputeArbitration","DISPUTE_WINDOW_DAYS",
    "freeze_escrow_on_dispute","release_or_refund_on_verdict",
]

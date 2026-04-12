"""
DATABASE_MODELS/dispute_table.py — Dispute Table Reference
"""
from api.marketplace.DISPUTE_RESOLUTION.dispute_model import (
    Dispute, DisputeMessage, DisputeEvidence, DisputeArbitration
)
from api.marketplace.DISPUTE_RESOLUTION.dispute_analytics import dispute_summary, seller_dispute_rate
from api.marketplace.enums import DisputeStatus


def open_disputes(tenant) -> list:
    return list(
        Dispute.objects.filter(
            tenant=tenant, status__in=[DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]
        ).select_related("order","raised_by","against_seller").order_by("created_at")
    )


def dispute_resolution_time(tenant) -> float:
    """Average days to resolve disputes."""
    resolved = Dispute.objects.filter(tenant=tenant, resolved_at__isnull=False)
    if not resolved.exists():
        return 0.0
    total_days = sum((d.resolved_at - d.created_at).days for d in resolved)
    return round(total_days / resolved.count(), 1)


__all__ = [
    "Dispute","DisputeMessage","DisputeEvidence","DisputeArbitration",
    "dispute_summary","seller_dispute_rate",
    "open_disputes","dispute_resolution_time",
]

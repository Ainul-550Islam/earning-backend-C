"""Payout Queue views.py — user-facing timeline endpoints."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PayoutItem


def _iso(dt):
    return dt.isoformat() if dt else None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payout_timeline(request):
    """
    Return user payout items with a 3-step timeline:
    Submitted -> Under Audit -> Payout Sent
    """

    user = request.user

    # Pending items: show only what is not terminal yet.
    pending_statuses = ["QUEUED", "PROCESSING", "RETRYING"]

    base_qs = (
        PayoutItem.objects.select_related("batch")
        .filter(user=user)
        .order_by("-created_at")
    )

    pending_items = base_qs.filter(status__in=pending_statuses)[:10]
    recent_items = base_qs[:20]

    def map_item(item):
        batch = item.batch

        submitted_at = _iso(item.created_at)

        under_audit_at = None
        if item.status in {"PROCESSING", "RETRYING"}:
            under_audit_at = _iso(batch.started_at or item.processed_at)

        # Some deployments may have batch.started_at populated slightly before item.status.
        if not under_audit_at and batch.started_at and item.status in {"QUEUED", "PROCESSING", "RETRYING"}:
            under_audit_at = _iso(batch.started_at)

        payout_sent_at = None
        if item.status == "SUCCESS":
            payout_sent_at = _iso(batch.completed_at or item.processed_at)

        return {
            "id": str(item.id),
            "batch_id": str(batch.id),
            "gateway": str(item.gateway),
            "account_number": item.account_number,
            "status": str(item.status),
            "status_display": item.get_status_display() if hasattr(item, "get_status_display") else str(item.status),
            "amount": float(item.net_amount),
            "gross_amount": float(item.gross_amount),
            "fee_amount": float(item.fee_amount),
            "created_at": submitted_at,
            "processed_at": _iso(item.processed_at),
            "submitted_at": submitted_at,
            "under_audit_at": under_audit_at,
            "payout_sent_at": payout_sent_at,
            "error_message": item.error_message or None,
        }

    pending = [map_item(i) for i in pending_items]
    recent = [map_item(i) for i in recent_items]

    return Response(
        {
            "success": True,
            "message": "Success",
            "data": {
                "pending": pending,
                "recent": recent,
            },
        }
    )


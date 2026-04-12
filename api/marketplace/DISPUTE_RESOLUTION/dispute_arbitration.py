"""
DISPUTE_RESOLUTION/dispute_arbitration.py — Arbitration Helpers
"""
from .dispute_model import Dispute, DisputeArbitration
from api.marketplace.enums import DisputeStatus


def get_pending_arbitrations(tenant) -> list:
    return list(
        Dispute.objects.filter(
            tenant=tenant,
            status__in=[DisputeStatus.UNDER_REVIEW, DisputeStatus.ESCALATED],
        ).select_related("order","raised_by","against_seller","order_item")
        .prefetch_related("evidences","messages")
        .order_by("created_at")
    )


def arbitration_history(tenant, admin_user=None) -> list:
    qs = DisputeArbitration.objects.filter(dispute__tenant=tenant)
    if admin_user:
        qs = qs.filter(admin=admin_user)
    from django.db.models import Count
    return list(
        qs.values("verdict","admin__username")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def arbitration_stats(tenant) -> dict:
    from django.db.models import Count
    arbs = DisputeArbitration.objects.filter(dispute__tenant=tenant)
    total = arbs.count()
    by_verdict = dict(arbs.values("verdict").annotate(c=Count("id")).values_list("verdict","c"))
    return {
        "total":           total,
        "buyer_wins":      by_verdict.get("buyer_wins", 0),
        "seller_wins":     by_verdict.get("seller_wins", 0),
        "partial":         by_verdict.get("partial", 0),
        "buyer_win_rate":  round(by_verdict.get("buyer_wins",0) / max(1,total) * 100, 1),
        "seller_win_rate": round(by_verdict.get("seller_wins",0) / max(1,total) * 100, 1),
    }

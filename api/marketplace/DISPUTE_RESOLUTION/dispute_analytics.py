"""
DISPUTE_RESOLUTION/dispute_analytics.py — Dispute Analytics & Reporting
"""
from django.db.models import Count, Avg
from django.utils import timezone
from .dispute_model import Dispute


def dispute_summary(tenant, days: int = 30) -> dict:
    since = timezone.now() - timezone.timedelta(days=days)
    qs    = Dispute.objects.filter(tenant=tenant, created_at__gte=since)
    by_status = dict(qs.values("status").annotate(c=Count("id")).values_list("status","c"))
    by_type   = dict(qs.values("dispute_type").annotate(c=Count("id")).values_list("dispute_type","c"))
    total = qs.count()
    resolved = qs.filter(resolved_at__isnull=False)
    avg_days = None
    if resolved.exists():
        avg_resolution = resolved.annotate(
            days=__import__("django.db.models",fromlist=["ExpressionWrapper"]).ExpressionWrapper(
                __import__("django.db.models",fromlist=["F"]).F("resolved_at") -
                __import__("django.db.models",fromlist=["F"]).F("created_at"),
                output_field=__import__("django.db.models",fromlist=["DurationField"]).DurationField()
            )
        )
    return {
        "total":          total,
        "by_status":      by_status,
        "by_type":        by_type,
        "resolution_rate":round(resolved.count() / max(1, total) * 100, 1),
        "open_disputes":  by_status.get("open", 0) + by_status.get("under_review", 0),
    }


def seller_dispute_rate(tenant, days: int = 30) -> list:
    from api.marketplace.models import OrderItem
    since = timezone.now() - timezone.timedelta(days=days)
    result = []
    disputes_by_seller = (
        Dispute.objects.filter(tenant=tenant, created_at__gte=since)
        .values("against_seller__store_name","against_seller__pk")
        .annotate(count=Count("id"))
        .order_by("-count")[:20]
    )
    for row in disputes_by_seller:
        total_orders = OrderItem.objects.filter(
            seller_id=row["against_seller__pk"], created_at__gte=since
        ).values("order").distinct().count()
        rate = round(row["count"] / max(1, total_orders) * 100, 1)
        result.append({
            "seller":       row["against_seller__store_name"],
            "disputes":     row["count"],
            "orders":       total_orders,
            "dispute_rate": rate,
            "risk_level":   "high" if rate > 5 else ("medium" if rate > 2 else "low"),
        })
    return result

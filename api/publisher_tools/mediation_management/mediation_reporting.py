# api/publisher_tools/mediation_management/mediation_reporting.py
"""Mediation Reporting — Revenue and performance reports."""
from decimal import Decimal
from datetime import timedelta, date
from typing import Dict, List
from django.db.models import Sum, Avg
from django.utils import timezone


def generate_waterfall_report(publisher, start_date: date, end_date: date) -> Dict:
    """Publisher-এর waterfall performance report।"""
    from api.publisher_tools.models import MediationGroup, PublisherEarning
    groups = MediationGroup.objects.filter(
        ad_unit__publisher=publisher, is_active=True
    ).select_related("ad_unit")
    report = {"publisher_id": publisher.publisher_id, "period": {"start": str(start_date), "end": str(end_date)}, "groups": []}
    for group in groups:
        agg = PublisherEarning.objects.filter(
            ad_unit=group.ad_unit, date__range=[start_date, end_date],
        ).aggregate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), requests=Sum("ad_requests"), ecpm=Avg("ecpm"))
        items = group.waterfall_items.filter(status="active").order_by("priority")
        report["groups"].append({
            "group_id":   str(group.id),
            "name":       group.name,
            "ad_unit":    group.ad_unit.unit_id,
            "type":       group.mediation_type,
            "revenue":    float(agg.get("revenue") or 0),
            "impressions":agg.get("impressions") or 0,
            "fill_rate":  round((agg.get("impressions") or 0) / max(agg.get("requests") or 1, 1) * 100, 2),
            "avg_ecpm":   float(agg.get("ecpm") or 0),
            "networks":   [{"rank": i.priority, "name": i.network.name, "ecpm": float(i.avg_ecpm)} for i in items],
        })
    return report


def generate_network_roi_report(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    from django.db.models import Sum, Avg
    start = timezone.now().date() - timedelta(days=days)
    data = list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start, network__isnull=False)
        .values("network__name", "network__network_type").annotate(
            revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"),
        ).order_by("-revenue")
    )
    total = sum(float(d.get("revenue") or 0) for d in data)
    for d in data:
        d["revenue_share_pct"] = round(float(d.get("revenue") or 0) / total * 100, 2) if total > 0 else 0
        d["revenue"] = float(d.get("revenue") or 0)
        d["impressions"] = d.get("impressions") or 0
        d["ecpm"] = float(d.get("ecpm") or 0)
    return data

# api/publisher_tools/mediation_management/mediation_analytics.py
"""Mediation Analytics — Waterfall and bidding performance analytics."""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List
from django.db.models import Sum, Avg, Count
from django.utils import timezone


def get_mediation_performance(group, days: int = 30) -> Dict:
    """Mediation group performance report।"""
    from api.publisher_tools.models import WaterfallItem, PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    items = group.waterfall_items.filter(status="active").order_by("priority")
    agg = PublisherEarning.objects.filter(ad_unit=group.ad_unit, date__gte=start).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        requests=Sum("ad_requests"), ecpm=Avg("ecpm"),
    )
    return {
        "group_id":      str(group.id),
        "name":          group.name,
        "mediation_type":group.mediation_type,
        "period_days":   days,
        "total_revenue": float(agg.get("revenue") or 0),
        "total_impressions": agg.get("impressions") or 0,
        "fill_rate":     round((agg.get("impressions") or 0) / max(agg.get("requests") or 1, 1) * 100, 2),
        "avg_ecpm":      float(agg.get("ecpm") or 0),
        "waterfall_items": [
            {"rank": item.priority, "network": item.network.name, "floor": float(item.floor_ecpm),
             "ecpm": float(item.avg_ecpm), "fill": float(item.fill_rate), "revenue": float(item.total_revenue)}
            for item in items
        ],
    }


def get_network_comparison(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start, network__isnull=False)
        .values("network__name").annotate(
            revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
            ecpm=Avg("ecpm"), fill_rate=Avg("fill_rate"), count=Count("id"),
        ).order_by("-revenue")
    )


def calculate_mediation_efficiency(group) -> float:
    """Mediation efficiency score (0-100)।"""
    fill  = float(group.fill_rate)
    ecpm  = float(group.avg_ecpm)
    items = group.waterfall_items.filter(status="active").count()
    score = fill * 0.50 + min(100, ecpm / 5.0 * 100) * 0.30 + min(100, items / 5 * 100) * 0.20
    return round(score, 2)

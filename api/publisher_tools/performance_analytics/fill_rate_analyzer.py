# api/publisher_tools/performance_analytics/fill_rate_analyzer.py
"""Fill Rate Analyzer — Ad fill rate monitoring and optimization."""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List
from django.db.models import Sum, Avg
from django.utils import timezone


def get_fill_rate_by_unit(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("ad_unit__unit_id", "ad_unit__name", "ad_unit__format")
        .annotate(
            impressions=Sum("impressions"), requests=Sum("ad_requests"),
            fill_rate=Avg("fill_rate"), revenue=Sum("publisher_revenue"),
        ).order_by("fill_rate")
    )


def get_fill_rate_by_country(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("country", "country_name")
        .annotate(impressions=Sum("impressions"), requests=Sum("ad_requests"), fill_rate=Avg("fill_rate"))
        .order_by("fill_rate")[:20]
    )


def identify_fill_rate_issues(publisher, threshold: float = 50.0) -> List[Dict]:
    units = get_fill_rate_by_unit(publisher)
    issues = []
    for unit in units:
        fill = float(unit.get("fill_rate") or 0)
        if fill < threshold:
            issues.append({
                **unit,
                "fill_rate": fill,
                "severity": "critical" if fill < 20 else "high" if fill < 35 else "medium",
                "recommendation": "Add more ad networks to waterfall" if fill < 30 else "Check floor price — may be too high",
            })
    return issues


def calculate_revenue_impact_of_low_fill(unit, target_fill_rate: float = 80.0) -> Dict:
    """Low fill rate-এর revenue impact estimate করে।"""
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=30)
    agg = PublisherEarning.objects.filter(ad_unit=unit, date__gte=start).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        requests=Sum("ad_requests"), ecpm=Avg("ecpm"),
    )
    current_fill = float(agg.get("impressions") or 0) / max(float(agg.get("requests") or 1), 1) * 100
    current_rev = float(agg.get("revenue") or 0)
    potential_rev = current_rev * (target_fill_rate / max(current_fill, 0.01))
    return {
        "unit_id": unit.unit_id,
        "current_fill_rate": round(current_fill, 2),
        "target_fill_rate": target_fill_rate,
        "current_revenue_30d": current_rev,
        "potential_revenue_30d": round(potential_rev, 4),
        "potential_uplift": round(potential_rev - current_rev, 4),
    }

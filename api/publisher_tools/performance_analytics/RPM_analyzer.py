# api/publisher_tools/performance_analytics/RPM_analyzer.py
"""RPM Analyzer — Revenue per mille (thousand pageviews) analysis."""
from datetime import timedelta
from typing import Dict, List
from django.db.models import Sum, Avg
from django.utils import timezone


def calculate_site_rpm(site, days: int = 30) -> Dict:
    """Site-এর RPM calculate করে।"""
    from api.publisher_tools.models import PublisherEarning
    from api.publisher_tools.site_management.site_analytics import SiteTrafficData
    start = timezone.now().date() - timedelta(days=days)
    revenue = float(
        PublisherEarning.objects.filter(site=site, date__gte=start)
        .aggregate(r=Sum("publisher_revenue")).get("r") or 0
    )
    pageviews = sum(
        SiteTrafficData.objects.filter(site=site, date__gte=start)
        .values_list("pageviews", flat=True)
    )
    rpm = round(revenue / pageviews * 1000, 4) if pageviews > 0 else 0
    return {"site_id": site.site_id, "domain": site.domain, "period_days": days,
            "total_revenue": revenue, "total_pageviews": pageviews, "rpm": rpm}


def get_rpm_by_publisher(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning, Site
    start = timezone.now().date() - timedelta(days=days)
    results = []
    for site in Site.objects.filter(publisher=publisher, status="active"):
        results.append(calculate_site_rpm(site, days))
    return sorted(results, key=lambda x: x["rpm"], reverse=True)


def get_rpm_benchmarks() -> Dict:
    return {
        "news":          {"low": 1.0, "medium": 3.0, "high": 8.0},
        "blog":          {"low": 0.5, "medium": 2.0, "high": 5.0},
        "technology":    {"low": 2.0, "medium": 5.0, "high": 12.0},
        "finance":       {"low": 3.0, "medium": 8.0, "high": 20.0},
        "entertainment": {"low": 0.5, "medium": 1.5, "high": 4.0},
        "gaming":        {"low": 1.0, "medium": 3.0, "high": 8.0},
    }


def compare_rpm_to_benchmark(site, rpm: float) -> Dict:
    benchmarks = get_rpm_benchmarks()
    category = site.category
    bench = benchmarks.get(category, {"low": 1.0, "medium": 3.0, "high": 8.0})
    if rpm >= bench["high"]:
        tier = "excellent"
    elif rpm >= bench["medium"]:
        tier = "good"
    elif rpm >= bench["low"]:
        tier = "average"
    else:
        tier = "poor"
    return {"rpm": rpm, "benchmark": bench, "tier": tier,
            "gap_to_high": round(bench["high"] - rpm, 4),
            "recommendation": f"Focus on {category} content optimization" if tier in ("average","poor") else "Maintain current strategy"}

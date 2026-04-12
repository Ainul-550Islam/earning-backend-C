# api/publisher_tools/ad_unit_management/ad_unit_performance.py
"""Ad Unit Performance — Detailed performance analytics."""
from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Avg, Count, Max, Min
from django.utils import timezone


def get_unit_performance_report(ad_unit, days: int = 30) -> dict:
    """Ad unit comprehensive performance report।"""
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    agg = PublisherEarning.objects.filter(ad_unit=ad_unit, date__gte=start).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        clicks=Sum("clicks"), requests=Sum("ad_requests"),
        avg_ecpm=Avg("ecpm"), avg_ctr=Avg("ctr"), avg_fill=Avg("fill_rate"),
        max_ecpm=Max("ecpm"), min_ecpm=Min("ecpm"),
    )
    rev = agg.get("revenue") or Decimal("0")
    imp = agg.get("impressions") or 0
    return {
        "unit_id":     ad_unit.unit_id,
        "unit_name":   ad_unit.name,
        "format":      ad_unit.format,
        "period_days": days,
        "revenue":     float(rev),
        "impressions": imp,
        "clicks":      agg.get("clicks") or 0,
        "ecpm":        float(rev / imp * 1000) if imp > 0 else 0,
        "avg_ecpm":    float(agg.get("avg_ecpm") or 0),
        "max_ecpm":    float(agg.get("max_ecpm") or 0),
        "min_ecpm":    float(agg.get("min_ecpm") or 0),
        "fill_rate":   float(agg.get("avg_fill") or 0),
        "ctr":         float(agg.get("avg_ctr") or 0),
        "floor_price": float(ad_unit.floor_price),
        "status":      ad_unit.status,
    }


def get_unit_daily_trend(ad_unit, days: int = 30) -> list:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(ad_unit=ad_unit, date__gte=start)
        .values("date").annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))
        .order_by("date")
    )


def compare_unit_performance(unit1, unit2, days: int = 30) -> dict:
    """Two ad units performance compare করে।"""
    r1 = get_unit_performance_report(unit1, days)
    r2 = get_unit_performance_report(unit2, days)
    def pct_diff(a, b):
        return round((a - b) / b * 100, 2) if b > 0 else 0
    return {
        "unit1": r1, "unit2": r2,
        "ecpm_diff_pct":    pct_diff(r1["ecpm"], r2["ecpm"]),
        "fill_diff_pct":    pct_diff(r1["fill_rate"], r2["fill_rate"]),
        "revenue_diff_pct": pct_diff(r1["revenue"], r2["revenue"]),
        "winner": unit1.unit_id if r1["revenue"] >= r2["revenue"] else unit2.unit_id,
    }

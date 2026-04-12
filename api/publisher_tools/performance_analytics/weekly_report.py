# api/publisher_tools/performance_analytics/weekly_report.py
"""Weekly Report — Weekly earnings summary and analysis."""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
from django.db.models import Sum, Avg
from django.utils import timezone


def generate_weekly_report(publisher, week_start: date = None) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    if not week_start:
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    agg = PublisherEarning.objects.filter(publisher=publisher, date__range=[week_start, week_end]).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        clicks=Sum("clicks"), ecpm=Avg("ecpm"), fill=Avg("fill_rate"),
    )
    daily = list(
        PublisherEarning.objects.filter(publisher=publisher, date__range=[week_start, week_end])
        .values("date").annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"))
        .order_by("date")
    )
    # Compare with previous week
    prev_start = week_start - timedelta(days=7)
    prev_end   = week_start - timedelta(days=1)
    prev = PublisherEarning.objects.filter(publisher=publisher, date__range=[prev_start, prev_end]).aggregate(revenue=Sum("publisher_revenue"))
    curr_rev = float(agg.get("revenue") or 0)
    prev_rev = float(prev.get("revenue") or 0)
    wow_change = round((curr_rev - prev_rev) / max(prev_rev, 0.01) * 100, 2)
    return {
        "week_start":   str(week_start), "week_end": str(week_end),
        "total_revenue":curr_rev, "prev_week_revenue": prev_rev, "wow_change_pct": wow_change,
        "impressions":  agg.get("impressions") or 0, "clicks": agg.get("clicks") or 0,
        "avg_ecpm":     float(agg.get("ecpm") or 0), "avg_fill": float(agg.get("fill") or 0),
        "daily_breakdown": [{**d, "revenue": float(d.get("revenue") or 0)} for d in daily],
    }

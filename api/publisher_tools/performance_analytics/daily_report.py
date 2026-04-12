# api/publisher_tools/performance_analytics/daily_report.py
"""Daily Report — Daily earnings reports and summaries."""
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List
from django.db.models import Sum, Avg, Count
from django.utils import timezone


def generate_daily_report(publisher, report_date: date = None) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    if not report_date:
        report_date = timezone.now().date() - timedelta(days=1)
    agg = PublisherEarning.objects.filter(publisher=publisher, date=report_date).aggregate(
        gross=Sum("gross_revenue"), publisher=Sum("publisher_revenue"),
        impressions=Sum("impressions"), clicks=Sum("clicks"),
        requests=Sum("ad_requests"), ecpm=Avg("ecpm"), fill=Avg("fill_rate"),
    )
    # By country
    by_country = list(
        PublisherEarning.objects.filter(publisher=publisher, date=report_date)
        .values("country", "country_name").annotate(revenue=Sum("publisher_revenue")).order_by("-revenue")[:5]
    )
    # By unit
    by_unit = list(
        PublisherEarning.objects.filter(publisher=publisher, date=report_date)
        .values("ad_unit__unit_id", "ad_unit__name").annotate(revenue=Sum("publisher_revenue")).order_by("-revenue")[:5]
    )
    return {
        "date":            str(report_date),
        "publisher_id":    publisher.publisher_id,
        "gross_revenue":   float(agg.get("gross") or 0),
        "publisher_revenue": float(agg.get("publisher") or 0),
        "impressions":     agg.get("impressions") or 0,
        "clicks":          agg.get("clicks") or 0,
        "ad_requests":     agg.get("requests") or 0,
        "avg_ecpm":        float(agg.get("ecpm") or 0),
        "avg_fill_rate":   float(agg.get("fill") or 0),
        "top_countries":   by_country,
        "top_ad_units":    by_unit,
    }


def get_daily_comparison(publisher, days: int = 7) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start)
        .values("date").annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), ecpm=Avg("ecpm"))
        .order_by("date")
    )

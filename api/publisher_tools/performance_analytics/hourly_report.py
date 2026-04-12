# api/publisher_tools/performance_analytics/hourly_report.py
"""Hourly Report — Hourly earnings and performance reports."""
from decimal import Decimal
from datetime import date
from typing import Dict, List
from django.db.models import Sum, Avg


def generate_hourly_report(publisher, report_date: date) -> Dict:
    from api.publisher_tools.models import PublisherEarning
    data = list(
        PublisherEarning.objects.filter(
            publisher=publisher, date=report_date, granularity="hourly",
        ).values("hour").annotate(
            revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
            clicks=Sum("clicks"), requests=Sum("ad_requests"), ecpm=Avg("ecpm"),
        ).order_by("hour")
    )
    total_rev = sum(float(d.get("revenue") or 0) for d in data)
    peak_hour = max(data, key=lambda x: float(x.get("revenue") or 0), default=None)
    return {
        "publisher_id": publisher.publisher_id,
        "date":         str(report_date),
        "total_revenue":total_rev,
        "total_impressions": sum(d.get("impressions") or 0 for d in data),
        "peak_hour":    peak_hour.get("hour") if peak_hour else None,
        "peak_revenue": float(peak_hour.get("revenue") or 0) if peak_hour else 0,
        "hours":        [{**d, "revenue": float(d.get("revenue") or 0), "ecpm": float(d.get("ecpm") or 0)} for d in data],
    }


def get_best_hours(publisher, days: int = 30) -> List[Dict]:
    from api.publisher_tools.models import PublisherEarning
    from django.utils import timezone
    from datetime import timedelta
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(publisher=publisher, date__gte=start, granularity="hourly")
        .values("hour").annotate(avg_revenue=Avg("publisher_revenue"), avg_ecpm=Avg("ecpm"))
        .order_by("-avg_revenue")[:5]
    )

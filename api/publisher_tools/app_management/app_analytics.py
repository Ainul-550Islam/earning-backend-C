# api/publisher_tools/app_management/app_analytics.py
"""App Analytics — Revenue and performance analytics for apps."""
from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Avg, Count
from django.utils import timezone


def get_app_performance_summary(app, days: int = 30) -> dict:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    agg = PublisherEarning.objects.filter(app=app, date__gte=start).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"),
        clicks=Sum("clicks"), requests=Sum("ad_requests"),
    )
    rev = agg.get("revenue") or Decimal("0")
    imp = agg.get("impressions") or 0
    return {
        "app_id":     app.app_id,
        "app_name":   app.name,
        "platform":   app.platform,
        "period_days": days,
        "revenue":    float(rev),
        "impressions": imp,
        "clicks":     agg.get("clicks") or 0,
        "ecpm":       float(rev / imp * 1000) if imp > 0 else 0,
        "fill_rate":  float(imp / (agg.get("requests") or 1) * 100),
        "store_rating": float(app.store_rating),
        "quality_score": app.quality_score,
    }


def get_app_revenue_by_format(app, days: int = 30) -> list:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(app=app, date__gte=start)
        .values("earning_type")
        .annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"))
        .order_by("-revenue")
    )


def get_app_top_countries(app, days: int = 30, limit: int = 10) -> list:
    from api.publisher_tools.models import PublisherEarning
    start = timezone.now().date() - timedelta(days=days)
    return list(
        PublisherEarning.objects.filter(app=app, date__gte=start)
        .values("country", "country_name")
        .annotate(revenue=Sum("publisher_revenue"), impressions=Sum("impressions"))
        .order_by("-revenue")[:limit]
    )

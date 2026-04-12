# api/publisher_tools/performance_analytics/real_time_analytics.py
"""Real-time Analytics — Live dashboard data."""
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta


def get_live_stats(publisher) -> dict:
    """Current hour live stats।"""
    cache_key = f"live_stats:{publisher.publisher_id}:{timezone.now().strftime('%Y%m%d%H')}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    from api.publisher_tools.models import PublisherEarning, TrafficSafetyLog
    now = timezone.now()
    today = now.date()
    agg = PublisherEarning.objects.filter(publisher=publisher, date=today).aggregate(
        __import__("django.db.models", fromlist=["Sum"]).Sum.__func__
        if False else None
    )
    from django.db.models import Sum
    agg = PublisherEarning.objects.filter(publisher=publisher, date=today).aggregate(
        revenue=Sum("publisher_revenue"), impressions=Sum("impressions"), clicks=Sum("clicks"),
    )
    ivt_today = TrafficSafetyLog.objects.filter(
        publisher=publisher, detected_at__date=today, is_false_positive=False,
    ).count()
    data = {
        "timestamp":        now.isoformat(),
        "today_revenue":    float(agg.get("revenue") or 0),
        "today_impressions":agg.get("impressions") or 0,
        "today_clicks":     agg.get("clicks") or 0,
        "ivt_today":        ivt_today,
        "account_status":   publisher.status,
        "pending_balance":  float(publisher.pending_balance),
    }
    cache.set(cache_key, data, 60)
    return data


def get_realtime_fill_rate(unit_id: str) -> float:
    """Current hour fill rate।"""
    hour = timezone.now().strftime("%Y%m%d%H")
    impressions = cache.get(f"impressions:{unit_id}:{hour}", 0)
    requests    = cache.get(f"requests:{unit_id}:{hour}", 0)
    return round(impressions / requests * 100, 2) if requests > 0 else 0.0


def track_ad_request(unit_id: str):
    """Ad request track করে।"""
    key = f"requests:{unit_id}:{timezone.now().strftime('%Y%m%d%H')}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, 7200)
    return count

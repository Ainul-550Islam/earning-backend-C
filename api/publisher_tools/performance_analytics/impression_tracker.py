# api/publisher_tools/performance_analytics/impression_tracker.py
"""Impression Tracker — Real-time impression counting and validation."""
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone


def track_impression(unit_id: str, context: dict) -> dict:
    """Single impression track করে।"""
    from api.publisher_tools.fraud_prevention.invalid_traffic_detector import detect_invalid_traffic
    fraud_result = detect_invalid_traffic({**context, "event_type": "impression", "ad_unit_id": unit_id})
    if fraud_result["should_block"]:
        return {"tracked": False, "reason": "fraud_blocked", "score": fraud_result["fraud_score"]}
    # Increment counter in cache
    cache_key = f"impressions:{unit_id}:{timezone.now().strftime('%Y%m%d%H')}"
    count = cache.get(cache_key, 0) + 1
    cache.set(cache_key, count, 7200)
    return {"tracked": True, "impression_count": count, "fraud_score": fraud_result["fraud_score"]}


def get_hourly_impressions(unit_id: str) -> int:
    cache_key = f"impressions:{unit_id}:{timezone.now().strftime('%Y%m%d%H')}"
    return cache.get(cache_key, 0)


def get_daily_impressions(unit_id: str) -> int:
    today = timezone.now().strftime("%Y%m%d")
    total = 0
    for hour in range(24):
        total += cache.get(f"impressions:{unit_id}:{today}{hour:02d}", 0)
    return total


def flush_impressions_to_db(publisher):
    """Cache থেকে impression counts DB-তে flush করে।"""
    from api.publisher_tools.models import AdUnit, PublisherEarning
    units = AdUnit.objects.filter(publisher=publisher, status="active")
    today = timezone.now().date()
    for unit in units:
        count = get_daily_impressions(unit.unit_id)
        if count > 0:
            unit.total_impressions += count
            unit.save(update_fields=["total_impressions", "updated_at"])
    return {"flushed_at": timezone.now().isoformat(), "units_updated": units.count()}

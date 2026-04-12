# api/publisher_tools/performance_analytics/click_tracker.py
"""Click Tracker — Click counting, validation, deduplication."""
from django.core.cache import cache
from django.utils import timezone


def track_click(unit_id: str, context: dict) -> dict:
    """Single click track করে। Fraud check করে।"""
    from api.publisher_tools.fraud_prevention.invalid_traffic_detector import detect_invalid_traffic, check_click_velocity
    import hashlib
    # Velocity check
    user_key = hashlib.md5(f"{context.get('ip_address','')}:{context.get('device_id','')}".encode()).hexdigest()
    velocity = check_click_velocity(user_key, unit_id)
    if velocity["is_suspicious"]:
        return {"tracked": False, "reason": "velocity_fraud", "count": velocity["click_count_in_window"]}
    # Fraud check
    fraud = detect_invalid_traffic({**context, "event_type": "click", "ad_unit_id": unit_id})
    if fraud["should_block"]:
        return {"tracked": False, "reason": "fraud_blocked", "score": fraud["fraud_score"]}
    # Dedup — same IP+unit within 60s
    dedup_key = f"click_dedup:{unit_id}:{context.get('ip_address','')}"
    if cache.get(dedup_key):
        return {"tracked": False, "reason": "duplicate_click"}
    cache.set(dedup_key, True, 60)
    # Track
    count_key = f"clicks:{unit_id}:{timezone.now().strftime('%Y%m%d%H')}"
    count = cache.get(count_key, 0) + 1
    cache.set(count_key, count, 7200)
    return {"tracked": True, "click_count": count, "fraud_score": fraud["fraud_score"]}


def get_click_through_rate(unit_id: str) -> float:
    """Current hour CTR।"""
    hour = timezone.now().strftime("%Y%m%d%H")
    clicks = cache.get(f"clicks:{unit_id}:{hour}", 0)
    impressions = cache.get(f"impressions:{unit_id}:{hour}", 0)
    return round(clicks / impressions * 100, 4) if impressions > 0 else 0.0

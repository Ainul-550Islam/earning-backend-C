# api/publisher_tools/fraud_prevention/click_fraud_detector.py
"""Click Fraud Detector — Advanced click fraud detection."""
import hashlib
from typing import Dict
from django.core.cache import cache
from django.utils import timezone


def detect_click_fraud(context: dict) -> Dict:
    """Comprehensive click fraud detection।"""
    ip = context.get("ip_address", "")
    device_id = context.get("device_id", "")
    unit_id = context.get("ad_unit_id", "")
    user_agent = context.get("user_agent", "")
    signals = []
    score = 0

    # 1. Click velocity check
    user_key = hashlib.md5(f"{ip}:{device_id}".encode()).hexdigest()
    velocity_key = f"click_velocity:{user_key}:{unit_id}"
    click_count = cache.get(velocity_key, 0) + 1
    cache.set(velocity_key, click_count, 60)
    if click_count > 5:
        score += 60; signals.append(f"high_velocity:{click_count}_in_60s")

    # 2. Duplicate click check (same IP+unit within 5 min)
    dedup_key = f"click_dedup:{ip}:{unit_id}:5min"
    if cache.get(dedup_key):
        score += 70; signals.append("duplicate_click_5min")
    else:
        cache.set(dedup_key, True, 300)

    # 3. Rapid multiple ad unit clicks
    multi_key = f"multi_unit_clicks:{user_key}"
    units_clicked = cache.get(multi_key, set())
    if not isinstance(units_clicked, set):
        units_clicked = set()
    units_clicked.add(unit_id)
    cache.set(multi_key, units_clicked, 300)
    if len(units_clicked) > 10:
        score += 40; signals.append(f"clicking_many_units:{len(units_clicked)}")

    # 4. Bot UA check
    from .bot_detector import detect_bot_from_ua
    bot_result = detect_bot_from_ua(user_agent)
    if bot_result["is_bot"]:
        score += bot_result["score"]; signals.append(f"bot_ua:{bot_result['reason']}")

    fraud_type = "click_fraud"
    if click_count > 5:
        fraud_type = "click_flooding"
    elif cache.get(dedup_key):
        fraud_type = "click_injection"

    return {
        "is_fraud":      score >= 50,
        "fraud_type":    fraud_type,
        "fraud_score":   min(100, score),
        "signals":       signals,
        "click_count_1m":click_count,
        "should_block":  score >= 80,
    }


def detect_click_injection(context: dict) -> bool:
    """Click injection detection — rapid click after install।"""
    install_time = context.get("install_time_ms")
    click_time   = context.get("click_time_ms")
    if install_time and click_time:
        diff_sec = abs(click_time - install_time) / 1000
        if diff_sec < 5:
            return True
    return False

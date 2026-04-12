# api/publisher_tools/fraud_prevention/impression_fraud_detector.py
"""Impression Fraud Detector — Ad stacking, hidden ads, pixel stuffing."""
from typing import Dict


def detect_impression_fraud(context: dict) -> Dict:
    """Impression fraud signals detect করে।"""
    score = 0
    signals = []
    ad_size = context.get("ad_size", "")
    position = context.get("position", "")
    visibility_pct = context.get("visibility_pct", 100)
    z_index = context.get("z_index", 0)
    element_width = context.get("element_width", 300)
    element_height = context.get("element_height", 250)

    # Hidden ad detection
    if visibility_pct < 10:
        score += 70; signals.append(f"hidden_ad_visibility:{visibility_pct}%")

    # Pixel stuffing (1x1 or very small)
    if element_width < 5 and element_height < 5:
        score += 90; signals.append("pixel_stuffing_1x1")
    elif element_width < 50 or element_height < 20:
        score += 50; signals.append("ad_too_small_for_format")

    # Ad stacking — z-index too high suggests stacking
    if z_index > 9000:
        score += 40; signals.append(f"suspicious_z_index:{z_index}")

    # Off-screen placement
    scroll_x = context.get("scroll_x", 0)
    scroll_y = context.get("scroll_y", 0)
    ad_x = context.get("ad_x", 0)
    ad_y = context.get("ad_y", 0)
    viewport_w = context.get("viewport_width", 1920)
    viewport_h = context.get("viewport_height", 1080)
    if ad_x < -100 or ad_y < -100 or ad_x > viewport_w + 100 or ad_y > viewport_h + 100:
        score += 60; signals.append("off_screen_placement")

    return {
        "is_fraud":   score >= 50,
        "fraud_type": "impression_fraud" if score >= 50 else "clean",
        "score":      min(100, score),
        "signals":    signals,
        "should_block": score >= 80,
    }


def check_viewability_fraud(impression_data: dict) -> bool:
    """Viewability fraud check — instant 100% viewability is suspicious."""
    time_to_viewable = impression_data.get("time_to_viewable_ms", 0)
    viewability_pct = impression_data.get("viewability_pct", 0)
    # Instant viewability with 100% is suspicious
    if time_to_viewable < 100 and viewability_pct == 100:
        return True
    return False

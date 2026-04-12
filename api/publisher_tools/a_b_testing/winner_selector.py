# api/publisher_tools/a_b_testing/winner_selector.py
"""Winner Selector — Auto-select test winner based on statistical criteria."""
from typing import Optional, Dict
from django.db import transaction


def select_winner(test) -> Optional[object]:
    """Statistical criteria-based winner selection।"""
    if not test.can_declare_winner():
        return None
    variants = list(test.variants.filter(total_impressions__gte=test.min_sample_size))
    if len(variants) < 2:
        return None
    control = next((v for v in variants if v.is_control), None)
    if not control:
        return None
    best = None
    best_confidence = 0.0
    for variant in variants:
        if variant.is_control:
            continue
        from .confidence_calculator import calculate_confidence
        confidence = calculate_confidence(control, variant)
        uplift = float(variant.ecpm) - float(control.ecpm)
        if confidence >= float(test.confidence_level) and uplift > 0 and confidence > best_confidence:
            best = variant
            best_confidence = confidence
    if best:
        from .test_manager import calculate_uplift
        uplift_pct = calculate_uplift(float(control.ecpm), float(best.ecpm))
        with transaction.atomic():
            test.declare_winner(best, "statistical_sig", f"Confidence: {best_confidence:.1f}%, eCPM uplift: {uplift_pct:.1f}%")
        return best
    return None


def get_winner_recommendation(test) -> Dict:
    """Winner recommendation with reasoning।"""
    analysis = __import__("api.publisher_tools.a_b_testing.test_analyzer", fromlist=["analyze_test"]).analyze_test(test)
    best = None
    best_ecpm = 0
    for v in analysis.get("variants", []):
        if v.get("ecpm", 0) > best_ecpm:
            best_ecpm = v["ecpm"]
            best = v
    return {
        "recommended_winner":  best.get("id") if best else None,
        "name":                best.get("name") if best else None,
        "ecpm":                best_ecpm,
        "confidence":          best.get("confidence") if best else 0,
        "can_conclude":        analysis.get("can_conclude", False),
        "reason":              "Highest eCPM with statistical significance" if best else "Insufficient data",
    }

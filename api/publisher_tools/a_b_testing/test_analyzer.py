# api/publisher_tools/a_b_testing/test_analyzer.py
"""A/B Test Analyzer — Statistical analysis of test results."""
from typing import Dict, List


def analyze_test(test) -> Dict:
    """Complete test analysis with statistical significance。"""
    variants = list(test.variants.all())
    if len(variants) < 2:
        return {"status": "insufficient_variants", "can_conclude": False}
    control = next((v for v in variants if v.is_control), variants[0])
    results = []
    for variant in variants:
        data = {
            "id": str(variant.id), "name": variant.name,
            "is_control": variant.is_control,
            "impressions": variant.total_impressions,
            "clicks": variant.total_clicks,
            "revenue": float(variant.total_revenue),
            "ecpm": float(variant.ecpm),
            "ctr": float(variant.ctr),
            "fill_rate": float(variant.fill_rate),
        }
        if not variant.is_control and control.total_impressions > 0:
            from .confidence_calculator import calculate_confidence
            from .test_manager import calculate_uplift
            confidence = calculate_confidence(control, variant)
            uplift = calculate_uplift(float(control.ecpm), float(variant.ecpm))
            data.update({"confidence": confidence, "ecpm_uplift_pct": uplift, "is_significant": confidence >= float(test.confidence_level)})
        results.append(data)
    min_impressions = min(v.total_impressions for v in variants)
    can_conclude = min_impressions >= test.min_sample_size and test.duration_days >= test.min_duration_days
    return {
        "test_id":       test.test_id,
        "name":          test.name,
        "status":        test.status,
        "duration_days": test.duration_days,
        "can_conclude":  can_conclude,
        "has_winner":    test.has_winner,
        "winner":        str(test.winner_variant.id) if test.winner_variant else None,
        "variants":      results,
    }


def find_best_variant(test) -> object:
    """Best performing variant identify করে।"""
    variants = list(test.variants.filter(total_impressions__gte=test.min_sample_size))
    if not variants:
        return None
    return max(variants, key=lambda v: float(v.ecpm))

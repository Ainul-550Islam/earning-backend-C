# api/publisher_tools/a_b_testing/confidence_calculator.py
"""Confidence Calculator — Statistical confidence calculation."""
import math


def calculate_confidence(control_variant, test_variant) -> float:
    """Statistical confidence between two variants।"""
    n1 = control_variant.total_impressions
    x1 = int(float(control_variant.total_revenue) * 1000)  # proxy for conversions
    n2 = test_variant.total_impressions
    x2 = int(float(test_variant.total_revenue) * 1000)
    if n1 == 0 or n2 == 0:
        return 0.0
    p1 = x1 / max(n1, 1)
    p2 = x2 / max(n2, 1)
    p_pool = (x1 + x2) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return 0.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    if se == 0:
        return 0.0
    z = abs(p1 - p2) / se
    confidence = (1 + math.erf(z / math.sqrt(2))) / 2 * 100
    return round(confidence, 2)


def required_sample_size(baseline_rate: float, mde: float, confidence: float = 0.95, power: float = 0.80) -> int:
    """Statistical power-এর জন্য required sample size।"""
    if baseline_rate <= 0 or baseline_rate >= 1:
        return 1000
    z_alpha = 1.96 if confidence >= 0.95 else 1.645
    z_beta  = 0.842 if power >= 0.80 else 0.674
    p1 = baseline_rate
    p2 = min(0.99, baseline_rate * (1 + mde / 100))
    p_avg = (p1 + p2) / 2
    n = (z_alpha * math.sqrt(2 * p_avg * (1-p_avg)) + z_beta * math.sqrt(p1*(1-p1) + p2*(1-p2)))**2 / (p2-p1)**2
    return max(1000, math.ceil(n))


def is_statistically_significant(confidence: float, required: float = 95.0) -> bool:
    return confidence >= required

# api/publisher_tools/a_b_testing/hypothesis_tester.py
"""Hypothesis Tester — Statistical hypothesis testing."""
import math
from typing import Dict


def two_proportion_z_test(n1: int, x1: int, n2: int, x2: int) -> Dict:
    """Two-proportion z-test।"""
    if n1 == 0 or n2 == 0:
        return {"z_score": 0, "p_value": 1.0, "significant": False}
    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return {"z_score": 0, "p_value": 1.0, "significant": False}
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    if se == 0:
        return {"z_score": 0, "p_value": 1.0, "significant": False}
    z = abs(p1 - p2) / se
    # Approximate p-value from z-score
    def norm_cdf(x):
        return (1.0 + math.erf(x / math.sqrt(2))) / 2
    p_value = 2 * (1 - norm_cdf(z))
    return {
        "z_score": round(z, 4),
        "p_value": round(p_value, 6),
        "p1": round(p1, 6), "p2": round(p2, 6),
        "significant": p_value < 0.05,
        "confidence": round((1 - p_value) * 100, 2),
    }


def welch_t_test(mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int) -> Dict:
    """Welch's t-test for means comparison (eCPM, revenue)."""
    if n1 < 2 or n2 < 2 or std1 == 0 or std2 == 0:
        return {"t_score": 0, "significant": False, "confidence": 0}
    se = math.sqrt((std1**2/n1) + (std2**2/n2))
    if se == 0:
        return {"t_score": 0, "significant": False, "confidence": 0}
    t = abs(mean1 - mean2) / se
    # Simplified critical value check
    significant = t > 1.96
    confidence = min(100, round(t / 1.96 * 95, 2))
    return {
        "t_score": round(t, 4),
        "significant": significant,
        "confidence": confidence,
        "mean_diff": round(mean1 - mean2, 6),
        "relative_diff_pct": round((mean1 - mean2) / max(abs(mean2), 0.001) * 100, 2),
    }

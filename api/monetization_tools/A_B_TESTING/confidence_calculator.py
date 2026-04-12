"""A_B_TESTING/confidence_calculator.py — Confidence interval calculator."""
import math
from decimal import Decimal


class ConfidenceCalculator:
    """Computes confidence intervals for A/B test metrics."""

    @staticmethod
    def proportion_ci(successes: int, trials: int,
                       confidence: float = 0.95) -> dict:
        if not trials:
            return {"lower": 0, "upper": 0, "mean": 0}
        p    = successes / trials
        z    = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645
        se   = math.sqrt(p * (1 - p) / trials)
        return {
            "mean":  round(p, 6),
            "lower": max(0, round(p - z * se, 6)),
            "upper": min(1, round(p + z * se, 6)),
            "z":     z,
            "confidence_pct": confidence * 100,
        }

    @staticmethod
    def relative_uplift_ci(p1: float, n1: int,
                            p2: float, n2: int,
                            confidence: float = 0.95) -> dict:
        ci1   = ConfidenceCalculator.proportion_ci(int(p1 * n1), n1, confidence)
        ci2   = ConfidenceCalculator.proportion_ci(int(p2 * n2), n2, confidence)
        uplift = ((p2 - p1) / p1 * 100) if p1 else 0
        return {
            "variant_a": ci1, "variant_b": ci2,
            "uplift_pct": round(uplift, 2),
        }

    @staticmethod
    def power(p1: float, p2: float, n: int, alpha: float = 0.05) -> float:
        z_alpha = 1.96
        se      = math.sqrt(p1*(1-p1)/n + p2*(1-p2)/n)
        if se == 0:
            return 1.0
        z_beta  = abs(p1 - p2) / se - z_alpha
        cdf     = (1 + math.erf(z_beta / math.sqrt(2))) / 2
        return round(cdf, 4)

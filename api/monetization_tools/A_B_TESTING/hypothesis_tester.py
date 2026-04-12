"""A_B_TESTING/hypothesis_tester.py — Statistical hypothesis testing."""
import math
from decimal import Decimal


class HypothesisTester:
    """Z-test and Chi-square significance testing for A/B results."""

    @staticmethod
    def z_score(p1: float, p2: float, n1: int, n2: int) -> float:
        if n1 == 0 or n2 == 0:
            return 0.0
        p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
        se     = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return 0.0
        return (p1 - p2) / se

    @staticmethod
    def p_value(z_score: float) -> float:
        """Two-tailed p-value from z-score using normal approximation."""
        import math
        return 2 * (1 - HypothesisTester._normal_cdf(abs(z_score)))

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return (1 + math.erf(x / math.sqrt(2))) / 2

    @classmethod
    def is_significant(cls, p1: float, n1: int,
                        p2: float, n2: int,
                        alpha: float = 0.05) -> dict:
        z = cls.z_score(p1, p2, n1, n2)
        p = cls.p_value(z)
        return {
            "z_score":       round(z, 4),
            "p_value":       round(p, 4),
            "significant":   p < alpha,
            "confidence_pct": round((1 - alpha) * 100, 1),
            "winner":        "A" if p1 > p2 else "B" if p < alpha else None,
        }

    @classmethod
    def min_sample_size(cls, baseline_cvr: float, min_detectable_effect: float = 0.05,
                         alpha: float = 0.05, power: float = 0.80) -> int:
        z_alpha = 1.96  # for alpha=0.05
        z_beta  = 0.84  # for power=0.80
        p1      = baseline_cvr
        p2      = baseline_cvr * (1 + min_detectable_effect)
        diff    = p2 - p1
        if diff == 0:
            return 10000
        n = ((z_alpha + z_beta) ** 2 * (p1 * (1-p1) + p2 * (1-p2))) / (diff ** 2)
        return math.ceil(n)

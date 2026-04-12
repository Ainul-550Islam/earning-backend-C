"""
api/ai_engine/TESTING_EVALUATION/ab_test_evaluator.py
======================================================
A/B Test Evaluator — statistical A/B test analysis।
p-value, confidence interval, winner declaration।
"""
import logging, math
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)

class ABTestEvaluator:
    """Statistical A/B test evaluation engine।"""

    def evaluate(self, experiment_id: str) -> dict:
        """DB থেকে experiment data load করে evaluate করো।"""
        try:
            from ..models import ABTestExperiment
            exp = ABTestExperiment.objects.get(id=experiment_id)
            variants = exp.variants or []
            if len(variants) < 2:
                return {"status": "insufficient_variants"}
            control = variants[0]
            test    = variants[1]
            result  = self.compare_variants(
                control_conversions=int(control.get("conversions", 0)),
                test_conversions=   int(test.get("conversions", 0)),
                control_visitors=   int(control.get("visitors", 1)),
                test_visitors=      int(test.get("visitors", 1)),
            )
            result["experiment_id"] = str(experiment_id)
            result["experiment_name"] = exp.name
            return result
        except Exception as e:
            logger.error(f"A/B eval error: {e}")
            return {"error": str(e)}

    def compare_variants(self, control_conversions: int, test_conversions: int,
                          control_visitors: int, test_visitors: int,
                          alpha: float = 0.05) -> dict:
        """Two variants statistical comparison।"""
        ctrl_cvr = control_conversions / max(control_visitors, 1)
        test_cvr = test_conversions    / max(test_visitors, 1)
        lift     = (test_cvr - ctrl_cvr) / max(ctrl_cvr, 0.001)

        # Z-test for proportions
        p_pool = (control_conversions + test_conversions) / max(control_visitors + test_visitors, 1)
        se     = math.sqrt(p_pool * (1 - p_pool) * (1/max(control_visitors,1) + 1/max(test_visitors,1)))
        z      = (test_cvr - ctrl_cvr) / max(se, 0.0001)
        p_val  = self._two_tailed_p(abs(z))
        ci_low  = round((test_cvr - ctrl_cvr) - 1.96 * se, 6)
        ci_high = round((test_cvr - ctrl_cvr) + 1.96 * se, 6)

        significant = p_val < alpha
        winner = "test" if significant and test_cvr > ctrl_cvr else                  "control" if significant and ctrl_cvr > test_cvr else "inconclusive"

        return {
            "control_cvr":    round(ctrl_cvr, 4),
            "test_cvr":       round(test_cvr, 4),
            "lift_pct":       round(lift * 100, 2),
            "z_score":        round(z, 4),
            "p_value":        round(p_val, 6),
            "significant":    significant,
            "confidence":     round(1 - p_val, 4),
            "winner":         winner,
            "ci_95":          [ci_low, ci_high],
            "sample_sizes":   {"control": control_visitors, "test": test_visitors},
            "recommendation": self._recommendation(winner, lift, significant),
        }

    def _two_tailed_p(self, z: float) -> float:
        t = 1 / (1 + 0.2316419 * abs(z))
        poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
        phi  = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z**2) * poly
        return round(2 * (1 - phi), 8)

    def _recommendation(self, winner: str, lift: float, significant: bool) -> str:
        if not significant:
            return "Continue test — not enough data for significance."
        if winner == "test" and lift >= 0.10:
            return f"🚀 Deploy test variant — {lift:.1%} lift, statistically significant."
        if winner == "test":
            return f"Consider deploying test — {lift:.1%} positive lift."
        if winner == "control":
            return "Keep control — test variant underperforms."
        return "Inconclusive — run longer or increase sample size."

    def required_sample_size(self, baseline_rate: float,
                              minimum_effect: float = 0.05,
                              alpha: float = 0.05, power: float = 0.80) -> int:
        p1 = baseline_rate
        p2 = baseline_rate + minimum_effect
        pb = (p1 + p2) / 2
        z_a = 1.96; z_b = 0.842
        n = (z_a * math.sqrt(2 * pb * (1-pb)) + z_b * math.sqrt(p1*(1-p1) + p2*(1-p2)))**2
        n /= max((p2 - p1)**2, 0.0001)
        return max(100, int(math.ceil(n)))

    def sequential_test(self, n_tests: int, alpha: float = 0.05) -> float:
        """Bonferroni correction for multiple tests।"""
        return round(alpha / max(n_tests, 1), 6)

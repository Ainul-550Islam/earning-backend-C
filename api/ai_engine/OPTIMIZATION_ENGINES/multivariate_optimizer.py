"""
api/ai_engine/OPTIMIZATION_ENGINES/multivariate_optimizer.py
=============================================================
Multivariate Test (MVT) Optimizer।
Multiple variables simultaneously test করো।
Landing pages, offer cards, email templates, push notifications।
"""

import logging
import math
from typing import List, Dict, Optional
from itertools import product as itertools_product

logger = logging.getLogger(__name__)


class MultivariateOptimizer:
    """
    Multivariate testing and optimization engine।
    Full factorial ও fractional factorial designs।
    """

    def create_test_matrix(self, variables: Dict[str, List]) -> List[Dict]:
        """
        All variable combinations এর test matrix তৈরি করো।
        variables: {"button_color": ["red","blue"], "headline": ["A","B","C"]}
        """
        keys   = list(variables.keys())
        values = list(variables.values())
        combos = list(itertools_product(*values))

        matrix = []
        for i, combo in enumerate(combos):
            variant = {k: v for k, v in zip(keys, combo)}
            variant["variant_id"]  = f"variant_{i+1:03d}"
            variant["variant_name"] = "_".join(str(v)[:5] for v in combo)
            matrix.append(variant)

        return matrix

    def analyze(self, variants: List[Dict],
                 metric: str = "conversion_rate") -> dict:
        """Multivariate test results analyze করো।"""
        if not variants:
            return {"error": "No variant data"}

        # Find best variant
        best    = max(variants, key=lambda v: float(v.get(metric, 0)))
        worst   = min(variants, key=lambda v: float(v.get(metric, 0)))
        avg_val = sum(float(v.get(metric, 0)) for v in variants) / len(variants)

        best_val = float(best.get(metric, 0))
        lift     = ((best_val - avg_val) / max(avg_val, 0.001)) * 100

        return {
            "metric":        metric,
            "total_variants": len(variants),
            "best_variant":  best,
            "worst_variant": worst,
            "avg_value":     round(avg_val, 4),
            "best_value":    round(best_val, 4),
            "lift_vs_avg":   round(lift, 2),
            "recommendation": f"Deploy {best.get('variant_id','best')} — {lift:.1f}% lift over average",
        }

    def calculate_required_sample(self, baseline_rate: float,
                                   min_detectable_effect: float = 0.05,
                                   power: float = 0.80,
                                   alpha: float = 0.05) -> int:
        """Required sample size per variant calculate করো।"""
        p1 = baseline_rate
        p2 = baseline_rate + min_detectable_effect
        p_bar = (p1 + p2) / 2
        z_alpha = 1.96  # 95% confidence
        z_beta  = 0.842 # 80% power

        n = (z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) +
             z_beta  * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
        n = n / max((p2 - p1) ** 2, 0.0001)

        return max(100, int(math.ceil(n)))

    def interaction_analysis(self, variants: List[Dict],
                              factors: List[str],
                              metric: str = "conversion_rate") -> dict:
        """Factor interactions analyze করো।"""
        interactions = {}
        for factor in factors:
            factor_groups: Dict = {}
            for v in variants:
                key = str(v.get(factor, "unknown"))
                val = float(v.get(metric, 0))
                factor_groups.setdefault(key, []).append(val)

            for key, vals in factor_groups.items():
                avg = sum(vals) / len(vals)
                factor_groups[key] = round(avg, 4)

            interactions[factor] = factor_groups

        return {
            "factor_main_effects": interactions,
            "metric":             metric,
        }

    def winner_decision(self, variants: List[Dict],
                         metric: str = "conversion_rate",
                         min_confidence: float = 0.95) -> dict:
        """Statistical winner select করো।"""
        if len(variants) < 2:
            return {"winner": variants[0] if variants else None, "confident": False}

        best = max(variants, key=lambda v: float(v.get(metric, 0)))
        others = [v for v in variants if v != best]

        # Simple check: best vs second best
        second = max(others, key=lambda v: float(v.get(metric, 0)))
        best_val   = float(best.get(metric, 0))
        second_val = float(second.get(metric, 0))
        lift       = (best_val - second_val) / max(second_val, 0.001) * 100

        # Sample size check
        total_sample  = sum(int(v.get("impressions", 0)) for v in variants)
        min_required  = self.calculate_required_sample(second_val) * len(variants)
        enough_sample = total_sample >= min_required

        confident = lift >= 5 and enough_sample

        return {
            "winner":          best if confident else None,
            "confident":       confident,
            "lift_pct":        round(lift, 2),
            "total_sample":    total_sample,
            "min_sample_needed": min_required,
            "recommendation":  f"Deploy {best.get('variant_id')} — {lift:.1f}% better" if confident else "Collect more data",
        }

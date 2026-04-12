"""A_B_TESTING/multivariate_testing.py — Multivariate test (MVT) support."""
import itertools
from typing import List, Dict


class MultivariateTestBuilder:
    """Builds multivariate tests from multiple factor combinations."""

    @classmethod
    def generate_combinations(cls, factors: Dict[str, List]) -> List[dict]:
        """
        Generate all variant combinations from factors.
        factors = {"headline": ["A", "B"], "cta": ["Buy", "Learn More"]}
        returns [{"headline": "A", "cta": "Buy"}, ...]
        """
        keys   = list(factors.keys())
        values = list(factors.values())
        combos = list(itertools.product(*values))
        return [dict(zip(keys, combo)) for combo in combos]

    @classmethod
    def equal_weight_variants(cls, combinations: List[dict]) -> List[dict]:
        n      = len(combinations)
        weight = max(1, 100 // n)
        return [{"name": f"V{i+1}", "config": c, "weight": weight}
                for i, c in enumerate(combinations)]

    @classmethod
    def create_mvt(cls, name: str, factors: Dict[str, List],
                    tenant=None, **kwargs):
        from .test_creator import ABTestCreator
        combos   = cls.generate_combinations(factors)
        variants = cls.equal_weight_variants(combos)
        return ABTestCreator.create(name, variants, tenant=tenant, **kwargs)

    @classmethod
    def winning_combination(cls, results: dict) -> dict:
        variants = results.get("variants", [])
        if not variants:
            return {}
        return max(variants, key=lambda v: float(v.get("cvr", 0)))

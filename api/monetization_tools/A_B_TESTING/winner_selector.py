"""A_B_TESTING/winner_selector.py — Automatic winner selection logic."""
import logging
from ..models import ABTest

logger = logging.getLogger(__name__)


class WinnerSelector:
    """Selects and declares the winning A/B variant."""

    @classmethod
    def check_and_declare(cls, test_id: int, alpha: float = 0.05) -> dict:
        from .test_analyzer import TestAnalyzer
        from .hypothesis_tester import HypothesisTester

        results  = TestAnalyzer.results(test_id)
        variants = results.get("variants", [])
        if len(variants) < 2:
            return {"declared": False, "reason": "need at least 2 variants"}

        # Check minimum sample size
        total_assigned = sum(v["assigned"] for v in variants)
        test = ABTest.objects.get(pk=test_id)
        if total_assigned < (test.min_sample_size or 1000):
            return {"declared": False, "reason": "insufficient sample size",
                    "total": total_assigned, "needed": test.min_sample_size}

        a, b  = variants[0], variants[1]
        p1    = float(a["cvr"]) / 100
        p2    = float(b["cvr"]) / 100
        sig   = HypothesisTester.is_significant(p1, a["assigned"], p2, b["assigned"], alpha)

        if not sig["significant"]:
            return {"declared": False, "reason": "not statistically significant",
                    "p_value": sig["p_value"]}

        winner = a["name"] if p1 >= p2 else b["name"]
        cls.declare(test, winner)
        return {"declared": True, "winner": winner, "p_value": sig["p_value"],
                "z_score": sig["z_score"]}

    @classmethod
    def declare(cls, test, variant_name: str):
        from ..services import ABTestService
        ABTestService.declare_winner(test, variant_name)
        logger.info("A/B winner declared: test=%s variant=%s", test.name, variant_name)

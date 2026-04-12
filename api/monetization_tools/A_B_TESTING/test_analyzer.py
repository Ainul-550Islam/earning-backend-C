"""A_B_TESTING/test_analyzer.py — A/B test result analysis."""
from decimal import Decimal
from typing import dict as Dict


class TestAnalyzer:
    """Analyzes A/B test results for statistical significance."""

    @classmethod
    def results(cls, test_id: int) -> dict:
        from ..models import ABTest, ABTestAssignment
        from django.db.models import Count, Q
        try:
            test = ABTest.objects.get(pk=test_id)
        except ABTest.DoesNotExist:
            return {}

        variants = test.variants or []
        output   = {"test_id": test_id, "test_name": test.name,
                    "status": test.status, "variants": []}

        for v in variants:
            name    = v["name"]
            total   = ABTestAssignment.objects.filter(test=test, variant_name=name).count()
            conv    = ABTestAssignment.objects.filter(
                test=test, variant_name=name, converted=True
            ).count()
            cvr     = (Decimal(conv) / total * 100).quantize(Decimal("0.0001")) if total else Decimal("0")
            output["variants"].append({
                "name": name, "assigned": total,
                "converted": conv, "cvr": cvr,
            })

        return output

    @classmethod
    def compare(cls, test_id: int) -> dict:
        results  = cls.results(test_id)
        variants = results.get("variants", [])
        if len(variants) < 2:
            return results
        best = max(variants, key=lambda v: float(v["cvr"]))
        worst = min(variants, key=lambda v: float(v["cvr"]))
        lift  = Decimal("0")
        if worst["cvr"] and worst["cvr"] > 0:
            lift = ((best["cvr"] - worst["cvr"]) / worst["cvr"] * 100).quantize(Decimal("0.01"))
        results["best_variant"]  = best["name"]
        results["worst_variant"] = worst["name"]
        results["lift_pct"]      = lift
        return results

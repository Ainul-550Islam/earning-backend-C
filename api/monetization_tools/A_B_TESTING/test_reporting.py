"""A_B_TESTING/test_reporting.py — A/B test reporting and export."""
from decimal import Decimal


class ABTestReporter:
    """Generates A/B test reports in various formats."""

    @classmethod
    def full_report(cls, test_id: int) -> dict:
        from .test_analyzer import TestAnalyzer
        from .confidence_calculator import ConfidenceCalculator
        from .hypothesis_tester import HypothesisTester
        from ..models import ABTest
        try:
            test = ABTest.objects.get(pk=test_id)
        except ABTest.DoesNotExist:
            return {}

        results  = TestAnalyzer.compare(test_id)
        variants = results.get("variants", [])

        report = {
            "test_id":        test_id,
            "test_name":      test.name,
            "status":         test.status,
            "started_at":     str(test.started_at) if test.started_at else None,
            "ended_at":       str(test.ended_at) if test.ended_at else None,
            "winner":         test.winner_variant,
            "traffic_split":  test.traffic_split,
            "variants":       variants,
            "lift":           results.get("lift_pct"),
            "significance":   None,
        }

        if len(variants) >= 2:
            a, b = variants[0], variants[1]
            p1   = float(a["cvr"]) / 100
            p2   = float(b["cvr"]) / 100
            sig  = HypothesisTester.is_significant(p1, a["assigned"], p2, b["assigned"])
            report["significance"] = sig

        return report

    @classmethod
    def to_csv_rows(cls, test_id: int) -> list:
        report   = cls.full_report(test_id)
        rows     = [["Variant", "Assigned", "Converted", "CVR%"]]
        for v in report.get("variants", []):
            rows.append([v["name"], v["assigned"], v["converted"], str(v["cvr"])])
        return rows

    @classmethod
    def summary_card(cls, test_id: int) -> dict:
        report = cls.full_report(test_id)
        return {
            "name":    report.get("test_name"),
            "status":  report.get("status"),
            "winner":  report.get("winner", "TBD"),
            "lift":    report.get("lift"),
            "total":   sum(v["assigned"] for v in report.get("variants", [])),
        }

"""
Test Report — Generates comprehensive test execution reports.
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class TestReport:
    """
    Generates detailed test reports including:
    - Overall pass/fail summary
    - Per-suite breakdown
    - Coverage metrics
    - Compliance mapping
    - Trend analysis
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

    def run(self) -> dict:
        """Generate a comprehensive test report."""
        return self.generate()

    def generate(self, test_results: List[dict] = None,
                  suite_name: str = "DR System Test Suite") -> dict:
        """Generate a complete test execution report."""
        results = test_results or []
        total = len(results)
        passed = sum(1 for r in results if r.get("passed", False))
        failed = total - passed
        pass_rate = (passed / total * 100) if total else 0.0
        report = {
            "report_type": "dr_test_report",
            "suite_name": suite_name,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "pass_rate_percent": round(pass_rate, 2),
                "overall_status": "PASSED" if failed == 0 else "FAILED",
            },
            "results": results,
            "compliance_mapping": self._map_to_compliance(results),
            "recommendations": self._generate_recommendations(results),
        }
        return report

    def generate_drill_report(self, drill_results: List[dict]) -> dict:
        """Generate a DR drill specific test report."""
        passed_drills = [d for d in drill_results if d.get("passed")]
        failed_drills = [d for d in drill_results if not d.get("passed")]
        avg_rto = None
        if drill_results:
            rtos = [d.get("achieved_rto_seconds") for d in drill_results
                    if d.get("achieved_rto_seconds") is not None]
            avg_rto = sum(rtos) / len(rtos) if rtos else None
        return {
            "report_type": "drill_report",
            "generated_at": datetime.utcnow().isoformat(),
            "total_drills": len(drill_results),
            "passed_drills": len(passed_drills),
            "failed_drills": len(failed_drills),
            "pass_rate_percent": round(len(passed_drills) / max(len(drill_results), 1) * 100, 2),
            "avg_rto_seconds": round(avg_rto, 2) if avg_rto else None,
            "failed_drill_names": [d.get("name", "") for d in failed_drills],
        }

    def export_json(self, report: dict, output_path: str) -> bool:
        """Export report to JSON file."""
        try:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Report exported: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Report export failed: {e}")
            return False

    def export_markdown(self, report: dict) -> str:
        """Convert report to Markdown format."""
        summary = report.get("summary", {})
        lines = [
            f"# {report.get('suite_name', 'Test Report')}",
            f"**Generated:** {report.get('generated_at', '')}",
            "",
            "## Summary",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Tests | {summary.get('total_tests', 0)} |",
            f"| Passed | {summary.get('passed', 0)} |",
            f"| Failed | {summary.get('failed', 0)} |",
            f"| Pass Rate | {summary.get('pass_rate_percent', 0):.1f}% |",
            f"| Status | **{summary.get('overall_status', 'UNKNOWN')}** |",
            "",
        ]
        if report.get("recommendations"):
            lines.append("## Recommendations")
            for rec in report["recommendations"]:
                lines.append(f"- {rec}")
        return ""
    pass  # continuation-fixed

    def _map_to_compliance(self, results: List[dict]) -> Dict:
        """Map test results to compliance framework requirements."""
        frameworks = {
            "HIPAA": {
                "backup_tests": "164.312(a)(2)(i) - Unique user identification",
                "restore_tests": "164.308(a)(7)(ii)(B) - Disaster recovery plan",
                "failover_tests": "164.308(a)(7)(ii)(C) - Emergency mode operation",
                "integrity_tests": "164.312(c)(2) - Integrity controls",
            },
            "SOC2": {
                "backup_tests": "CC9.1 - Risk mitigation",
                "restore_tests": "A1.3 - Recovery testing",
                "failover_tests": "A1.2 - Environmental protections",
            }
        }
        passed_suites = {r.get("suite", "") for r in results if r.get("passed")}
        compliance = {}
        for framework, mappings in frameworks.items():
            framework_compliance = {}
            for suite, requirement in mappings.items():
                framework_compliance[requirement] = suite in passed_suites
            compliance[framework] = {
                "requirements": framework_compliance,
                "compliant": all(framework_compliance.values()),
            }
        return compliance

    def _generate_recommendations(self, results: List[dict]) -> List[str]:
        """Generate actionable recommendations from test results."""
        recommendations = []
        failed = [r for r in results if not r.get("passed")]
        if not failed:
            recommendations.append("All tests passed. Maintain current DR procedures.")
            return recommendations
        for result in failed:
            suite = result.get("suite", "")
            if "backup" in suite:
                recommendations.append("Review backup configuration and storage connectivity.")
            elif "restore" in suite:
                recommendations.append("Run a restore drill to verify backup recoverability.")
            elif "failover" in suite:
                recommendations.append("Review failover thresholds and network configuration.")
            elif "integrity" in suite:
                recommendations.append("Investigate data corruption risk — review checksum policies.")
        return list(set(recommendations))


class TestTestReport:
    """Tests for the test reporter."""

    def test_generate_with_empty_results(self):
        reporter = TestReport()
        report = reporter.generate([], "Empty Suite")
        assert report["summary"]["total_tests"] == 0
        assert report["summary"]["overall_status"] == "PASSED"
        assert report["summary"]["pass_rate_percent"] == 0.0

    def test_generate_with_mixed_results(self):
        reporter = TestReport()
        results = [
            {"suite": "backup_tests", "passed": True},
            {"suite": "restore_tests", "passed": False},
            {"suite": "failover_tests", "passed": True},
        ]
        report = reporter.generate(results)
        assert report["summary"]["total_tests"] == 3
        assert report["summary"]["passed"] == 2
        assert report["summary"]["failed"] == 1
        assert report["summary"]["overall_status"] == "FAILED"
        assert round(report["summary"]["pass_rate_percent"]) == 67

    def test_markdown_export_contains_summary(self):
        reporter = TestReport()
        report = reporter.generate([{"suite": "test", "passed": True}])
        md = reporter.export_markdown(report)
        assert "## Summary" in md
        assert "Pass Rate" in md
        assert "PASSED" in md

    def test_compliance_mapping_generated(self):
        reporter = TestReport()
        results = [
            {"suite": "backup_tests", "passed": True},
            {"suite": "restore_tests", "passed": True},
        ]
        report = reporter.generate(results)
        assert "compliance_mapping" in report
        assert "HIPAA" in report["compliance_mapping"]
        assert "SOC2" in report["compliance_mapping"]

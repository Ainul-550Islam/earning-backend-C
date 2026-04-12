# api/publisher_tools/a_b_testing/test_reporting.py
"""Test Reporting — A/B test reports and insights."""
from typing import Dict, List
from django.utils import timezone


def generate_test_summary_report(publisher) -> Dict:
    """Publisher-এর সব test-এর summary report।"""
    from .test_manager import ABTest
    tests = ABTest.objects.filter(publisher=publisher).order_by("-created_at")
    running    = tests.filter(status="running")
    completed  = tests.filter(status="completed")
    with_winners = completed.exclude(winner_variant=None)
    return {
        "publisher_id":   publisher.publisher_id,
        "total_tests":    tests.count(),
        "running":        running.count(),
        "completed":      completed.count(),
        "with_winners":   with_winners.count(),
        "win_rate":       round(with_winners.count() / max(completed.count(), 1) * 100, 2),
        "active_tests":   [{"id": t.test_id, "name": t.name, "type": t.test_type, "days": t.duration_days} for t in running[:5]],
        "recent_winners": [{"id": t.test_id, "name": t.name, "winner": t.winner_variant.name if t.winner_variant else None} for t in with_winners[:5]],
    }


def get_test_roi(test) -> Dict:
    """Test ROI — winner implementation-এর expected impact।"""
    if not test.winner_variant:
        return {"status": "no_winner"}
    control = test.variants.filter(is_control=True).first()
    winner  = test.winner_variant
    if not control or not winner:
        return {"status": "insufficient_data"}
    ecpm_uplift = float(winner.ecpm) - float(control.ecpm)
    monthly_imp = max(control.total_impressions, winner.total_impressions) * 30
    monthly_uplift = ecpm_uplift * monthly_imp / 1000
    return {
        "test_id":          test.test_id,
        "winner":           winner.name,
        "ecpm_uplift":      ecpm_uplift,
        "ecpm_uplift_pct":  round(ecpm_uplift / max(float(control.ecpm), 0.01) * 100, 2),
        "est_monthly_uplift_usd": round(monthly_uplift, 4),
        "est_annual_uplift_usd":  round(monthly_uplift * 12, 4),
        "confidence":       float(test.confidence_achieved or 0),
    }


def get_learnings_from_completed_tests(publisher, limit: int = 10) -> List[Dict]:
    from .test_manager import ABTest
    tests = ABTest.objects.filter(publisher=publisher, status="completed").exclude(winner_variant=None).order_by("-concluded_at")[:limit]
    return [
        {"test": t.test_id, "type": t.test_type, "winner": t.winner_variant.name, "config": t.winner_variant.config,
         "confidence": float(t.confidence_achieved or 0), "notes": t.conclusion_notes}
        for t in tests
    ]

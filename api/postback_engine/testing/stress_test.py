"""
testing/stress_test.py
────────────────────────
Stress test for PostbackEngine — finds breaking points.
Gradually increases load until failure rate exceeds threshold.
"""
from __future__ import annotations
import logging
import time
from .load_test import run_load_test

logger = logging.getLogger(__name__)


def run_stress_test(
    start_concurrent: int = 10,
    max_concurrent: int = 200,
    step: int = 10,
    total_per_step: int = 100,
    failure_threshold_pct: float = 5.0,
) -> dict:
    """
    Stress test: ramp up concurrency until failure rate exceeds threshold.
    Returns breaking point metrics.
    """
    results = []
    breaking_point = None

    concurrent = start_concurrent
    while concurrent <= max_concurrent:
        logger.info("Stress test: concurrent=%d", concurrent)
        result = run_load_test(concurrent=concurrent, total=total_per_step)
        failure_rate = (result["failed"] / result["total_requests"]) * 100
        result["concurrent"] = concurrent
        result["failure_rate_pct"] = round(failure_rate, 1)
        results.append(result)

        if failure_rate >= failure_threshold_pct and breaking_point is None:
            breaking_point = concurrent
            logger.warning("Breaking point found at concurrent=%d (failure_rate=%.1f%%)", concurrent, failure_rate)
            break

        concurrent += step
        time.sleep(1)  # Brief pause between ramp steps

    return {
        "breaking_point_concurrent": breaking_point,
        "failure_threshold_pct": failure_threshold_pct,
        "steps": results,
        "max_rps_achieved": max((r["requests_per_second"] for r in results), default=0),
    }

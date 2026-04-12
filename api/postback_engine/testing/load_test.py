"""
testing/load_test.py
─────────────────────
Load test for PostbackEngine.
Fires high-volume concurrent postbacks to measure throughput.

Usage:
    python manage.py shell -c "
    from api.postback_engine.testing.load_test import run_load_test
    run_load_test(concurrent=50, total=500)
    "
"""
from __future__ import annotations
import concurrent.futures
import time
import random
import logging
from typing import List

logger = logging.getLogger(__name__)


def _fire_single_postback(payload: dict) -> dict:
    """Fire a single postback and return result metrics."""
    start = time.time()
    try:
        from api.postback_engine.postback_handlers.cpa_network_handler import get_handler
        from unittest.mock import patch, MagicMock
        handler = get_handler(payload.get("network", "cpalead"))
        # Mock DB/Redis calls for pure pipeline performance test
        with patch("api.postback_engine.postback_handlers.base_handler.PostbackRawLog.objects.create") as mock_create,              patch("api.postback_engine.fraud_detection.velocity_checker.velocity_checker.check"),              patch("api.postback_engine.conversion_tracking.conversion_deduplicator.conversion_deduplicator.assert_not_duplicate"):
            mock_log = MagicMock()
            mock_create.return_value = mock_log
            result = handler.execute(
                raw_payload=payload, method="GET", query_string="",
                headers={}, source_ip="10.0.0.1",
            )
        duration_ms = (time.time() - start) * 1000
        return {"success": True, "status": result.status, "duration_ms": duration_ms}
    except Exception as exc:
        return {"success": False, "error": str(exc), "duration_ms": (time.time() - start) * 1000}


def run_load_test(concurrent: int = 20, total: int = 100) -> dict:
    """
    Run a load test with concurrent postbacks.
    Returns summary metrics.
    """
    payloads = [
        {
            "network": "cpalead",
            "sub1": f"user_{i:06d}",
            "amount": f"{random.uniform(0.01, 2.00):.2f}",
            "oid": f"offer_{random.randint(1, 10):03d}",
            "sid": f"txn_{i:010d}",
        }
        for i in range(total)
    ]

    start_time = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
        futures = [executor.submit(_fire_single_postback, p) for p in payloads]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    total_time = time.time() - start_time
    successes = [r for r in results if r.get("success")]
    durations = [r["duration_ms"] for r in results]

    summary = {
        "total_requests": total,
        "successful": len(successes),
        "failed": total - len(successes),
        "total_time_seconds": round(total_time, 2),
        "requests_per_second": round(total / total_time, 1),
        "avg_latency_ms": round(sum(durations) / len(durations), 1),
        "min_latency_ms": round(min(durations), 1),
        "max_latency_ms": round(max(durations), 1),
        "p95_latency_ms": round(sorted(durations)[int(len(durations) * 0.95)], 1),
    }
    logger.info("Load test complete: %s", summary)
    return summary

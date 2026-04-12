"""
testing/benchmark.py
─────────────────────
Performance benchmarks for critical PostbackEngine paths.
Measures: adapter normalisation, fraud scoring, dedup hash, macro expansion.
"""
from __future__ import annotations
import time
import logging
from decimal import Decimal
from typing import Callable

logger = logging.getLogger(__name__)


def _benchmark(name: str, fn: Callable, iterations: int = 10000) -> dict:
    """Run a function N times and return timing metrics."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)

    return {
        "name": name,
        "iterations": iterations,
        "avg_ms": round(sum(times) / len(times), 4),
        "min_ms": round(min(times), 4),
        "max_ms": round(max(times), 4),
        "total_ms": round(sum(times), 2),
        "throughput_per_sec": round(1000 / (sum(times) / len(times))),
    }


def run_benchmarks(iterations: int = 10000) -> dict:
    """Run all benchmarks. Returns dict of results."""
    from api.postback_engine.network_adapters.adapters import get_adapter
    from api.postback_engine.fraud_detection.bot_detector import BotDetector
    from api.postback_engine.conversion_tracking.conversion_deduplicator import ConversionDeduplicator
    from api.postback_engine.utils import sha256_hex, expand_url_macros

    adapter = get_adapter("cpalead")
    bot_detector = BotDetector()
    dedup = ConversionDeduplicator()
    sample_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0) AppleWebKit/605.1.15"
    sample_payload = {"sub1": "user_123", "amount": "0.50", "oid": "offer_001", "sid": "txn_001"}
    sample_template = "https://tracker.com/?click={click_id}&payout={payout}&user={user_id}"
    sample_ctx = {"click_id": "abc123", "payout": "0.50", "user_id": "user_456"}

    results = [
        _benchmark("adapter.normalise", lambda: adapter.normalise(sample_payload), iterations),
        _benchmark("adapter.normalise_status('1')", lambda: adapter.normalise_status("1"), iterations),
        _benchmark("adapter.expand_macros", lambda: adapter.expand_macros(sample_template, sample_ctx), iterations),
        _benchmark("bot_detector.check_user_agent", lambda: bot_detector.check_user_agent(sample_ua), iterations),
        _benchmark("dedup._hash", lambda: dedup._hash("lead_user_123"), iterations),
        _benchmark("sha256_hex", lambda: sha256_hex("1.2.3.4"), iterations),
    ]

    summary = {
        "benchmarks": results,
        "slowest": max(results, key=lambda x: x["avg_ms"])["name"],
        "fastest": min(results, key=lambda x: x["avg_ms"])["name"],
    }

    for r in results:
        logger.info("BENCH %s: avg=%.4fms throughput=%d/s", r["name"], r["avg_ms"], r["throughput_per_sec"])

    return summary


if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()
    results = run_benchmarks(iterations=10000)
    for r in results["benchmarks"]:
        print(f"{r['name']:45s} avg={r['avg_ms']:7.4f}ms  {r['throughput_per_sec']:,}/s")

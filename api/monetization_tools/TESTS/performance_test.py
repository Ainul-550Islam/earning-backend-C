"""TESTS/performance_test.py - Performance benchmarks."""
import time
from decimal import Decimal


class PerformanceTestSuite:
    @staticmethod
    def benchmark(func, iterations: int = 100) -> dict:
        times = []
        for _ in range(iterations):
            t = time.perf_counter()
            func()
            times.append(time.perf_counter() - t)
        avg = sum(times) / len(times)
        return {"iterations": iterations, "avg_ms": round(avg * 1000, 3),
                "min_ms": round(min(times) * 1000, 3), "max_ms": round(max(times) * 1000, 3)}

    @staticmethod
    def test_ecpm_calculation():
        from ..REVENUE_MODELS.cpm_calculator import CPMCalculator
        return PerformanceTestSuite.benchmark(
            lambda: CPMCalculator.ecpm(Decimal("100.00"), 50000), 1000
        )

    @staticmethod
    def test_fraud_scoring():
        from ..AD_QUALITY.ad_fraud_detector import AdFraudDetector
        return PerformanceTestSuite.benchmark(
            lambda: AdFraudDetector.score(ip="1.2.3.4", user_agent="Mozilla/5.0"), 1000
        )

    @staticmethod
    def test_geo_optimizer():
        from ..OPTIMIZATION_ENGINES.geo_optimizer import GeoOptimizer
        countries = ["US", "BD", "IN", "GB", "DE", "BR"]
        return PerformanceTestSuite.benchmark(
            lambda: [GeoOptimizer.tier(c) for c in countries], 1000
        )

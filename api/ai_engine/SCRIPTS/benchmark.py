"""
api/ai_engine/SCRIPTS/benchmark.py
====================================
AI Engine Benchmark — latency ও throughput test।
"""

import time
import statistics
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def benchmark_predictions(n: int = 100):
    import django
    django.setup()

    from api.ai_engine.services import PredictionService

    latencies = []
    errors = 0

    print(f"\n⚡ Benchmarking {n} predictions...")
    for i in range(n):
        test_input = {
            'is_vpn': False, 'is_proxy': False, 'device_count': 1,
            'account_age_days': 30, 'clicks_per_hour': 5,
        }
        start = time.time()
        try:
            PredictionService.predict('fraud', test_input)
            latencies.append((time.time() - start) * 1000)
        except Exception:
            errors += 1

    if latencies:
        print(f"\n📊 Results ({n} requests):")
        print(f"   Avg latency:  {statistics.mean(latencies):.2f}ms")
        print(f"   P50 latency:  {statistics.median(latencies):.2f}ms")
        print(f"   P95 latency:  {statistics.quantiles(latencies, n=20)[18]:.2f}ms")
        print(f"   Min/Max:      {min(latencies):.2f}ms / {max(latencies):.2f}ms")
        print(f"   Errors:       {errors}/{n}")
        throughput = n / (sum(latencies) / 1000)
        print(f"   Throughput:   {throughput:.0f} req/s")


if __name__ == '__main__':
    benchmark_predictions(100)

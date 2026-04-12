"""
api/ai_engine/TESTING_EVALUATION/performance_test.py
=====================================================
Performance Test — latency, throughput, memory benchmarking।
Production SLA validation।
Load testing, stress testing, endurance testing।
"""

import time
import logging
import statistics
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class PerformanceTest:
    """
    Comprehensive performance testing engine।
    Latency percentiles, throughput, memory usage।
    """

    # SLA thresholds
    SLA_AVG_MS  = 200.0
    SLA_P99_MS  = 500.0
    SLA_P95_MS  = 300.0
    MIN_RPS     = 10.0    # Minimum requests per second

    def run(self, predictor, n_requests: int = 100,
            warmup_requests: int = 10) -> dict:
        """
        Standard latency performance test।
        Warmup → Actual test → Report।
        """
        # Warmup
        dummy = {'f1': 0.5, 'f2': 1.0, 'f3': 0.3, 'f4': 0.8}
        for _ in range(warmup_requests):
            try:
                predictor.predict(dummy)
            except Exception:
                pass

        # Actual test
        latencies: List[float] = []
        errors = 0
        start_time = time.time()

        for i in range(n_requests):
            features = {
                'f1': 0.1 + (i % 10) * 0.09,
                'f2': float(i % 5),
                'f3': 0.5,
                'f4': float(i % 3) * 0.3,
            }
            req_start = time.time()
            try:
                predictor.predict(features)
                latencies.append((time.time() - req_start) * 1000)
            except Exception as e:
                errors += 1

        total_time_s = time.time() - start_time
        throughput   = len(latencies) / max(total_time_s, 0.001)

        if not latencies:
            return {
                'passed': False,
                'errors': errors,
                'error_rate': 1.0,
                'reason': 'All requests failed',
            }

        return self._compute_report(latencies, errors, n_requests, throughput)

    def _compute_report(self, latencies: List[float], errors: int,
                        n_requests: int, throughput: float) -> dict:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        avg_ms  = statistics.mean(latencies)
        p50_ms  = latencies_sorted[int(n * 0.50)]
        p75_ms  = latencies_sorted[int(n * 0.75)]
        p90_ms  = latencies_sorted[int(n * 0.90)]
        p95_ms  = latencies_sorted[int(n * 0.95)]
        p99_ms  = latencies_sorted[min(int(n * 0.99), n - 1)]
        std_ms  = statistics.stdev(latencies) if n > 1 else 0

        sla_passed = (avg_ms <= self.SLA_AVG_MS and
                      p99_ms <= self.SLA_P99_MS and
                      p95_ms <= self.SLA_P95_MS and
                      throughput >= self.MIN_RPS)

        return {
            'passed':          sla_passed,
            'n_requests':      n_requests,
            'successful':      len(latencies),
            'errors':          errors,
            'error_rate':      round(errors / max(n_requests, 1), 4),
            'latency': {
                'avg_ms':   round(avg_ms,  2),
                'std_ms':   round(std_ms,  2),
                'min_ms':   round(min(latencies), 2),
                'max_ms':   round(max(latencies), 2),
                'p50_ms':   round(p50_ms,  2),
                'p75_ms':   round(p75_ms,  2),
                'p90_ms':   round(p90_ms,  2),
                'p95_ms':   round(p95_ms,  2),
                'p99_ms':   round(p99_ms,  2),
            },
            'throughput_rps': round(throughput, 2),
            'sla': {
                'avg_threshold':  self.SLA_AVG_MS,
                'p99_threshold':  self.SLA_P99_MS,
                'min_rps':        self.MIN_RPS,
                'avg_passed':     avg_ms  <= self.SLA_AVG_MS,
                'p99_passed':     p99_ms  <= self.SLA_P99_MS,
                'p95_passed':     p95_ms  <= self.SLA_P95_MS,
                'throughput_ok':  throughput >= self.MIN_RPS,
            },
            'verdict': 'PASS ✅' if sla_passed else 'FAIL ❌',
        }

    def load_test(self, predictor, rps_target: float = 100,
                   duration_seconds: int = 30) -> dict:
        """
        Load test — specified RPS এ sustained performance।
        Real production load simulate করো।
        """
        import threading
        results   = {'latencies': [], 'errors': 0, 'requests': 0}
        lock      = threading.Lock()
        stop_flag = threading.Event()

        def worker():
            dummy = {'f1': 0.5, 'f2': 0.3}
            while not stop_flag.is_set():
                start = time.time()
                try:
                    predictor.predict(dummy)
                    lat = (time.time() - start) * 1000
                    with lock:
                        results['latencies'].append(lat)
                        results['requests'] += 1
                except Exception:
                    with lock:
                        results['errors'] += 1
                        results['requests'] += 1

                # Rate limiting
                elapsed = time.time() - start
                sleep_t = max(0, 1.0 / rps_target - elapsed)
                time.sleep(sleep_t)

        # Start workers
        n_workers = max(1, int(rps_target / 10))
        threads   = [threading.Thread(target=worker) for _ in range(n_workers)]
        for t in threads:
            t.daemon = True
            t.start()

        time.sleep(duration_seconds)
        stop_flag.set()
        for t in threads:
            t.join(timeout=2)

        lats = results['latencies']
        achieved_rps = results['requests'] / duration_seconds

        return {
            'duration_seconds': duration_seconds,
            'target_rps':       rps_target,
            'achieved_rps':     round(achieved_rps, 2),
            'rps_achieved':     achieved_rps >= rps_target * 0.90,  # 90% target
            'total_requests':   results['requests'],
            'errors':           results['errors'],
            'latency': {
                'avg_ms': round(statistics.mean(lats), 2) if lats else 0,
                'p99_ms': round(sorted(lats)[int(len(lats) * 0.99)], 2) if lats else 0,
            } if lats else {},
        }

    def memory_test(self, predictor, n_requests: int = 1000) -> dict:
        """Memory usage ও leak detection।"""
        try:
            import tracemalloc
            tracemalloc.start()

            dummy = {'f1': 0.5, 'f2': 0.3}
            for _ in range(n_requests):
                predictor.predict(dummy)

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            return {
                'current_mb':    round(current / 1024 / 1024, 3),
                'peak_mb':       round(peak / 1024 / 1024, 3),
                'per_request_kb': round(current / max(n_requests, 1) / 1024, 4),
                'n_requests':    n_requests,
                'memory_ok':     peak / 1024 / 1024 < 500,  # < 500MB
            }
        except Exception as e:
            return {'error': str(e)}

    def concurrent_test(self, predictor, n_threads: int = 10,
                         requests_per_thread: int = 50) -> dict:
        """Concurrent request handling test।"""
        import threading

        all_latencies = []
        all_errors    = []
        lock          = threading.Lock()

        def worker_fn():
            local_lats  = []
            local_errs  = 0
            dummy       = {'f1': 0.5, 'f2': 0.3, 'f3': 1.0}
            for _ in range(requests_per_thread):
                start = time.time()
                try:
                    predictor.predict(dummy)
                    local_lats.append((time.time() - start) * 1000)
                except Exception:
                    local_errs += 1
            with lock:
                all_latencies.extend(local_lats)
                all_errors.append(local_errs)

        threads = [threading.Thread(target=worker_fn) for _ in range(n_threads)]
        start_all = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.time() - start_all

        total_req = n_threads * requests_per_thread
        total_err = sum(all_errors)
        throughput = total_req / max(total_time, 0.001)

        return {
            'n_threads':       n_threads,
            'total_requests':  total_req,
            'total_errors':    total_err,
            'error_rate':      round(total_err / max(total_req, 1), 4),
            'total_time_s':    round(total_time, 2),
            'throughput_rps':  round(throughput, 2),
            'latency': {
                'avg_ms': round(statistics.mean(all_latencies), 2) if all_latencies else 0,
                'p99_ms': round(sorted(all_latencies)[int(len(all_latencies) * 0.99)], 2) if all_latencies else 0,
            },
            'concurrency_ok':  total_err < total_req * 0.05,  # < 5% error rate
        }

    def regression_test(self, current_results: dict,
                          baseline_results: dict,
                          tolerance_pct: float = 10.0) -> dict:
        """
        Performance regression detection।
        Current vs Baseline compare করো।
        """
        regressions = []
        metrics_to_check = ['avg_ms', 'p95_ms', 'p99_ms']

        for metric in metrics_to_check:
            curr = current_results.get('latency', {}).get(metric, 0)
            base = baseline_results.get('latency', {}).get(metric, 0)
            if base == 0:
                continue
            degradation = ((curr - base) / base) * 100
            if degradation > tolerance_pct:
                regressions.append({
                    'metric':      metric,
                    'baseline_ms': round(base, 2),
                    'current_ms':  round(curr, 2),
                    'degradation_pct': round(degradation, 2),
                })

        return {
            'regression_detected': len(regressions) > 0,
            'regressions':         regressions,
            'tolerance_pct':       tolerance_pct,
            'verdict':             'REGRESSION DETECTED ⚠️' if regressions else 'No regression ✅',
        }

# api/offer_inventory/testing_qa/load_tester.py
"""
Load Tester — Simulate high-traffic scenarios for performance testing.
Tests: offer listing, postback handling, conversion recording throughput.
"""
import time
import uuid
import logging
import threading
from decimal import Decimal
from django.test import RequestFactory
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class LoadTester:
    """
    Simulate concurrent load on key platform endpoints.
    Use ONLY in development/staging — never production.
    """

    def __init__(self, concurrency: int = 10, requests_per_thread: int = 10):
        self.concurrency          = concurrency
        self.requests_per_thread  = requests_per_thread
        self.results              = []
        self._lock                = threading.Lock()

    def run_offer_list_test(self) -> dict:
        """Test offer listing endpoint throughput."""
        from api.offer_inventory.repository import OfferRepository

        def worker():
            for _ in range(self.requests_per_thread):
                start = time.monotonic()
                try:
                    OfferRepository.get_active_offers()
                    elapsed = (time.monotonic() - start) * 1000
                    with self._lock:
                        self.results.append({'ok': True, 'ms': elapsed})
                except Exception as e:
                    with self._lock:
                        self.results.append({'ok': False, 'error': str(e)})

        return self._run_threads(worker, 'offer_list')

    def run_fraud_check_test(self, ip: str = '1.2.3.4',
                              user_agent: str = 'Mozilla/5.0') -> dict:
        """Test fraud detection throughput."""
        from api.offer_inventory.fraud_detection import FraudDetectionEngine

        def worker():
            for _ in range(self.requests_per_thread):
                start = time.monotonic()
                try:
                    FraudDetectionEngine._score_bot(ip, user_agent, None)
                    elapsed = (time.monotonic() - start) * 1000
                    with self._lock:
                        self.results.append({'ok': True, 'ms': elapsed})
                except Exception as e:
                    with self._lock:
                        self.results.append({'ok': False, 'error': str(e)})

        return self._run_threads(worker, 'fraud_check')

    def run_cache_test(self) -> dict:
        """Test Redis cache throughput."""
        from django.core.cache import cache

        def worker():
            for i in range(self.requests_per_thread):
                key = f'load_test:{uuid.uuid4().hex}'
                start = time.monotonic()
                try:
                    cache.set(key, {'data': 'test_value'}, 60)
                    cache.get(key)
                    cache.delete(key)
                    elapsed = (time.monotonic() - start) * 1000
                    with self._lock:
                        self.results.append({'ok': True, 'ms': elapsed})
                except Exception as e:
                    with self._lock:
                        self.results.append({'ok': False, 'error': str(e)})

        return self._run_threads(worker, 'cache_ops')

    def _run_threads(self, worker_fn, test_name: str) -> dict:
        """Execute worker function in multiple threads."""
        self.results = []
        threads  = [threading.Thread(target=worker_fn) for _ in range(self.concurrency)]
        start    = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start

        ok_results  = [r for r in self.results if r.get('ok')]
        err_results = [r for r in self.results if not r.get('ok')]
        latencies   = [r['ms'] for r in ok_results]

        summary = {
            'test_name'       : test_name,
            'concurrency'     : self.concurrency,
            'total_requests'  : len(self.results),
            'successful'      : len(ok_results),
            'failed'          : len(err_results),
            'success_rate_pct': round(len(ok_results) / max(len(self.results), 1) * 100, 1),
            'total_seconds'   : round(elapsed, 2),
            'requests_per_sec': round(len(self.results) / elapsed, 1),
            'avg_latency_ms'  : round(sum(latencies) / len(latencies), 1) if latencies else 0,
            'max_latency_ms'  : round(max(latencies), 1) if latencies else 0,
            'min_latency_ms'  : round(min(latencies), 1) if latencies else 0,
            'errors'          : [r.get('error', '') for r in err_results[:5]],
        }
        logger.info(f'Load test [{test_name}]: {summary["requests_per_sec"]} req/s | '
                    f'avg={summary["avg_latency_ms"]}ms | '
                    f'success={summary["success_rate_pct"]}%')
        return summary

    def run_all_tests(self) -> dict:
        """Run all available load tests."""
        return {
            'offer_list' : self.run_offer_list_test(),
            'fraud_check': self.run_fraud_check_test(),
            'cache_ops'  : self.run_cache_test(),
        }


class DatabaseStressTest:
    """Database-specific stress tests."""

    @staticmethod
    def test_click_insert_throughput(count: int = 100) -> dict:
        """Test bulk Click insert performance."""
        from api.offer_inventory.models import Click, Offer
        from api.offer_inventory.testing_qa.mock_offer_generator import MockOfferGenerator
        import secrets

        offer = Offer.objects.filter(status='active').first()
        if not offer:
            offer = MockOfferGenerator.create_offer()

        start  = time.monotonic()
        clicks = []
        for _ in range(count):
            clicks.append(Click(
                offer       =offer,
                ip_address  ='1.2.3.4',
                user_agent  ='LoadTest/1.0',
                country_code='BD',
                device_type ='mobile',
                click_token =secrets.token_hex(32),
                is_unique   =True,
                is_fraud    =False,
            ))
        Click.objects.bulk_create(clicks)
        elapsed = time.monotonic() - start

        return {
            'records_inserted': count,
            'elapsed_seconds' : round(elapsed, 3),
            'inserts_per_sec' : round(count / elapsed, 1),
        }

    @staticmethod
    def test_query_performance() -> dict:
        """Test common query patterns."""
        from api.offer_inventory.models import Click, Conversion, Offer
        results = {}

        queries = {
            'active_offers'     : lambda: Offer.objects.filter(status='active').count(),
            'recent_clicks'     : lambda: Click.objects.filter(is_fraud=False).order_by('-created_at')[:20].count(),
            'approved_conversions': lambda: Conversion.objects.filter(status__name='approved').count(),
        }
        for name, q in queries.items():
            start = time.monotonic()
            q()
            results[name] = round((time.monotonic() - start) * 1000, 2)

        return results

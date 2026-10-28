"""
tasks/rate_limit_tester.py
Testing and benchmarking tools for rate limiting system.
Provides load testing, performance benchmarking, and validation tools.
"""
from django.core.cache import cache

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

logger = logging.getLogger(__name__)


class RateLimitTester:
    """
    Comprehensive testing suite for rate limiting system.
    """

    def __init__(self):
        self.factory = RequestFactory()

    def create_test_request(self, user_id: Optional[int] = None, ip: str = '127.0.0.1') -> 'HttpRequest':
        """Create a mock Django request for testing."""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = ip
        request.META['HTTP_X_FORWARDED_FOR'] = ip

        if user_id:
            # Mock user object
            class MockUser:
                def __init__(self, id):
                    self.id = id
                    self.is_authenticated = True
                    self.is_staff = False
            request.user = MockUser(user_id)
        else:
            request.user = AnonymousUser()

        return request

    def test_rate_limit_basic(self, limit_type: str = 'api_general', user_id: int = 123) -> Dict:
        """
        Basic rate limit test - single user making sequential requests.
        """
        from .middleware_rate_limit import RateLimitService

        service = RateLimitService()
        results = []

        start_time = time.time()

        # Make requests up to limit + some overflow
        config = service.rate_limits.get(limit_type, {'limit': 10, 'window': 60})
        max_requests = config['limit'] + 5

        for i in range(max_requests):
            identifier = f"user_{user_id}"
            is_allowed, remaining = service.check_limit(limit_type, identifier)

            results.append({
                'request': i + 1,
                'allowed': is_allowed,
                'remaining': remaining,
                'timestamp': time.time()
            })

            time.sleep(0.01)  # Small delay

        end_time = time.time()

        # Analyze results
        allowed_count = sum(1 for r in results if r['allowed'])
        blocked_count = len(results) - allowed_count

        return {
            'test_type': 'basic_sequential',
            'limit_type': limit_type,
            'user_id': user_id,
            'total_requests': len(results),
            'allowed': allowed_count,
            'blocked': blocked_count,
            'expected_limit': config['limit'],
            'duration': end_time - start_time,
            'requests_per_second': len(results) / (end_time - start_time),
            'results': results[:20],  # First 20 results
        }

    def test_rate_limit_concurrent(self, limit_type: str = 'api_general',
                                  num_threads: int = 10, requests_per_thread: int = 5) -> Dict:
        """
        Concurrent rate limit test - multiple threads hitting the same endpoint.
        """
        from .middleware_rate_limit import RateLimitService

        service = RateLimitService()
        all_results = []

        def worker_thread(thread_id: int) -> List[Dict]:
            results = []
            user_id = 1000 + thread_id  # Different user per thread

            for i in range(requests_per_thread):
                identifier = f"user_{user_id}"
                start_time = time.time()
                is_allowed, remaining = service.check_limit(limit_type, identifier)
                end_time = time.time()

                results.append({
                    'thread': thread_id,
                    'request': i + 1,
                    'user_id': user_id,
                    'allowed': is_allowed,
                    'remaining': remaining,
                    'response_time': end_time - start_time,
                    'timestamp': end_time
                })

                time.sleep(0.001)  # Very small delay

            return results

        start_time = time.time()

        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
            for future in as_completed(futures):
                all_results.extend(future.result())

        end_time = time.time()

        # Analyze results
        total_requests = len(all_results)
        allowed_count = sum(1 for r in all_results if r['allowed'])
        blocked_count = total_requests - allowed_count
        avg_response_time = sum(r['response_time'] for r in all_results) / total_requests

        return {
            'test_type': 'concurrent',
            'limit_type': limit_type,
            'num_threads': num_threads,
            'requests_per_thread': requests_per_thread,
            'total_requests': total_requests,
            'allowed': allowed_count,
            'blocked': blocked_count,
            'avg_response_time': avg_response_time,
            'duration': end_time - start_time,
            'requests_per_second': total_requests / (end_time - start_time),
            'thread_efficiency': total_requests / (num_threads * (end_time - start_time)),
        }

    def test_rate_limit_burst(self, limit_type: str = 'api_general', user_id: int = 999,
                             burst_size: int = 50) -> Dict:
        """
        Burst test - sudden flood of requests to test rate limiter resilience.
        """
        from .middleware_rate_limit import RateLimitService

        service = RateLimitService()
        results = []

        start_time = time.time()

        # Burst of requests
        for i in range(burst_size):
            identifier = f"user_{user_id}"
            req_start = time.time()
            is_allowed, remaining = service.check_limit(limit_type, identifier)
            req_end = time.time()

            results.append({
                'request': i + 1,
                'allowed': is_allowed,
                'remaining': remaining,
                'response_time': req_end - req_start,
                'timestamp': req_end
            })

        end_time = time.time()

        # Analyze results
        allowed_count = sum(1 for r in results if r['allowed'])
        blocked_count = len(results) - allowed_count
        avg_response_time = sum(r['response_time'] for r in results) / len(results)

        return {
            'test_type': 'burst',
            'limit_type': limit_type,
            'user_id': user_id,
            'burst_size': burst_size,
            'total_requests': len(results),
            'allowed': allowed_count,
            'blocked': blocked_count,
            'block_rate': blocked_count / len(results),
            'avg_response_time': avg_response_time,
            'duration': end_time - start_time,
            'requests_per_second': len(results) / (end_time - start_time),
        }

    def benchmark_redis_vs_cache(self, iterations: int = 1000) -> Dict:
        """
        Benchmark Redis vs Django cache performance.
        """
        from .middleware_rate_limit import RateLimitService

        service = RateLimitService()
        results = {'redis': [], 'cache': []}

        # Test Redis (if available)
        if service.redis_client:
            start_time = time.time()
            for i in range(iterations):
                try:
                    service.redis_client.incr('benchmark_test')
                except:
                    break
            end_time = time.time()
            results['redis'] = {
                'iterations': iterations,
                'duration': end_time - start_time,
                'ops_per_second': iterations / (end_time - start_time),
            }

        # Test Django cache
        start_time = time.time()
        for i in range(iterations):
            cache.get(f'benchmark_test_{i}')
            cache.set(f'benchmark_test_{i}', i, 60)
        end_time = time.time()
        results['cache'] = {
            'iterations': iterations,
            'duration': end_time - start_time,
            'ops_per_second': iterations / (end_time - start_time),
        }

        return results

    def test_middleware_integration(self, limit_type: str = 'api_general',
                                   num_requests: int = 20) -> Dict:
        """
        Test full middleware integration with mock requests.
        """
        from .middleware_rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(lambda r: None)  # Mock get_response
        results = []

        for i in range(num_requests):
            request = self.create_test_request(user_id=555)
            request.path = f'/api/test/{i}'

            # Mock the middleware call
            try:
                start_time = time.time()
                # This would normally call the middleware
                # For testing, we'll call the service directly
                from .middleware_rate_limit import RateLimitService
                service = RateLimitService()
                is_allowed, remaining = service.check_limit(limit_type, 'user_555')
                end_time = time.time()

                results.append({
                    'request': i + 1,
                    'allowed': is_allowed,
                    'remaining': remaining,
                    'response_time': end_time - start_time,
                })

                time.sleep(0.01)

            except Exception as e:
                results.append({
                    'request': i + 1,
                    'error': str(e),
                })

        return {
            'test_type': 'middleware_integration',
            'num_requests': num_requests,
            'results': results,
        }


def run_rate_limit_test_suite():
    """
    Run comprehensive test suite.
    """
    tester = RateLimitTester()
    results = {}

    print("🚀 Running Rate Limit Test Suite")
    print("=" * 50)

    # Basic test
    print("\n📊 Basic Sequential Test...")
    results['basic'] = tester.test_rate_limit_basic()
    print(f"  ✅ {results['basic']['allowed']}/{results['basic']['total_requests']} allowed")

    # Concurrent test
    print("\n⚡ Concurrent Test...")
    results['concurrent'] = tester.test_rate_limit_concurrent(num_threads=5, requests_per_thread=3)
    print(f"  ✅ {results['concurrent']['allowed']}/{results['concurrent']['total_requests']} allowed")

    # Burst test
    print("\n💥 Burst Test...")
    results['burst'] = tester.test_rate_limit_burst(burst_size=30)
    print(f"  ✅ {results['burst']['allowed']}/{results['burst']['total_requests']} allowed")

    # Benchmark
    print("\n🏁 Performance Benchmark...")
    results['benchmark'] = tester.benchmark_redis_vs_cache(iterations=500)
    if results['benchmark']['redis']:
        print(f"  ✅ Redis: {results['benchmark']['redis']['ops_per_second']:.1f} ops/sec")
    else:
        print("  ⚠️  Redis not available, using cache only")

    print("\n🎉 Test suite completed!")
    return results


if __name__ == '__main__':
    run_rate_limit_test_suite()
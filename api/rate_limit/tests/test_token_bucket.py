"""
Token Bucket Algorithm Tests

This module contains comprehensive tests for the token bucket rate limiting algorithm.
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from api.rate_limit.tests.factories import (
    UserRateLimitProfileFactory,
    RateLimitConfigFactory, UserFactory, RateLimitLogFactory,
    BulkDataFactory, TestDataGenerator
)


class TokenBucket:
    """Token bucket implementation for testing."""
    
    def __init__(self, capacity, refill_rate, refill_interval=1):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Number of tokens to add per refill interval
            refill_interval: Time between refills in seconds
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.refill_interval = refill_interval
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens=1):
        """
        Consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            bool: True if tokens were consumed, False otherwise
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed >= self.refill_interval:
            intervals = int(elapsed / self.refill_interval)
            tokens_to_add = intervals * self.refill_rate
            
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now + (elapsed % self.refill_interval)
    
    def get_tokens(self):
        """Get current number of tokens."""
        self._refill()
        return self.tokens
    
    def get_time_until_next_token(self):
        """Get time until next token is available."""
        if self.tokens > 0:
            return 0
        
        time_since_last_refill = time.time() - self.last_refill
        time_until_next_refill = self.refill_interval - (time_since_last_refill % self.refill_interval)
        
        return max(0, time_until_next_refill)


class TokenBucketTest(TestCase):
    """Test cases for TokenBucket implementation."""
    
    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.refill_rate, 5)
        self.assertEqual(bucket.refill_interval, 1)
        self.assertEqual(bucket.tokens, 10)
    
    def test_token_bucket_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        # Should be able to consume tokens
        self.assertTrue(bucket.consume(1))
        self.assertEqual(bucket.tokens, 9)
        
        self.assertTrue(bucket.consume(5))
        self.assertEqual(bucket.tokens, 4)
        
        self.assertTrue(bucket.consume(4))
        self.assertEqual(bucket.tokens, 0)
    
    def test_token_bucket_consume_failure(self):
        """Test token consumption failure."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        # Consume all tokens
        self.assertTrue(bucket.consume(10))
        self.assertEqual(bucket.tokens, 0)
        
        # Should not be able to consume more
        self.assertFalse(bucket.consume(1))
        self.assertEqual(bucket.tokens, 0)
        
        self.assertFalse(bucket.consume(5))
        self.assertEqual(bucket.tokens, 0)
    
    def test_token_bucket_refill(self):
        """Test token refill mechanism."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        # Consume all tokens
        self.assertTrue(bucket.consume(10))
        self.assertEqual(bucket.tokens, 0)
        
        # Wait for refill (simulate with manual refill)
        time.sleep(0)  # Wait slightly more than refill interval
        bucket._refill()
        
        # Should have new tokens
        self.assertEqual(bucket.tokens, 5)
        
        # Consume and wait again
        self.assertTrue(bucket.consume(5))
        self.assertEqual(bucket.tokens, 0)
        
        time.sleep(0)
        bucket._refill()
        
        self.assertEqual(bucket.tokens, 5)
    
    def test_token_bucket_multiple_refills(self):
        """Test multiple token refills."""
        bucket = TokenBucket(capacity=10, refill_rate=2, refill_interval=1)
        
        # Consume all tokens
        self.assertTrue(bucket.consume(10))
        self.assertEqual(bucket.tokens, 0)
        
        # Wait for multiple refills
        time.sleep(0)  # Wait for 3 refills
        bucket._refill()
        
        # Should have 6 tokens (2 * 3 refills)
        self.assertEqual(bucket.tokens, 6)
        
        # Should not exceed capacity
        time.sleep(0)  # Wait for 3 more refills
        bucket._refill()
        
        self.assertEqual(bucket.tokens, 10)  # Should be at capacity
    
    def test_token_bucket_get_tokens(self):
        """Test getting current token count."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        self.assertEqual(bucket.get_tokens(), 10)
        
        bucket.consume(3)
        self.assertEqual(bucket.get_tokens(), 7)
        
        bucket.consume(7)
        self.assertEqual(bucket.get_tokens(), 0)
    
    def test_token_bucket_time_until_next_token(self):
        """Test getting time until next token."""
        bucket = TokenBucket(capacity=10, refill_rate=5, refill_interval=1)
        
        # With tokens available, should return 0
        self.assertEqual(bucket.get_time_until_next_token(), 0)
        
        # Consume all tokens
        bucket.consume(10)
        
        # Should return time until next refill
        time_until = bucket.get_time_until_next_token()
        self.assertGreater(time_until, 0)
        self.assertLessEqual(time_until, 1)
    
    def test_token_bucket_edge_cases(self):
        """Test edge cases for token bucket."""
        # Zero capacity
        with self.assertRaises(Exception):
            TokenBucket(capacity=0, refill_rate=1)
        
        # Zero refill rate
        bucket = TokenBucket(capacity=10, refill_rate=0, refill_interval=1)
        self.assertEqual(bucket.refill_rate, 0)
        
        # Very small refill interval
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=0.1)
        self.assertEqual(bucket.refill_interval, 0.1)
    
    def test_token_bucket_large_values(self):
        """Test token bucket with large values."""
        bucket = TokenBucket(capacity=1000000, refill_rate=10000, refill_interval=1)
        
        self.assertEqual(bucket.capacity, 1000000)
        self.assertEqual(bucket.refill_rate, 10000)
        self.assertEqual(bucket.tokens, 1000000)
        
        # Should handle large consumption
        self.assertTrue(bucket.consume(500000))
        self.assertEqual(bucket.tokens, 500000)
        
        self.assertTrue(bucket.consume(500000))
        self.assertEqual(bucket.tokens, 0)
        
        self.assertFalse(bucket.consume(1))
        self.assertEqual(bucket.tokens, 0)


class TokenBucketConcurrencyTest(TestCase):
    """Test cases for concurrent token bucket operations."""
    
    def test_concurrent_consumption(self):
        """Test concurrent token consumption."""
        bucket = TokenBucket(capacity=100, refill_rate=10, refill_interval=1)
        
        results = []
        
        def worker():
            """Worker function for concurrent consumption."""
            for i in range(50):
                if bucket.consume(1):
                    results.append(True)
                else:
                    results.append(False)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have consumed exactly 100 tokens (capacity)
        true_count = sum(1 for result in results if result)
        false_count = sum(1 for result in results if not result)
        
        self.assertEqual(true_count, 100)
        self.assertEqual(false_count, 150)  # 250 total attempts - 100 successful
        self.assertEqual(bucket.tokens, 0)
    
    def test_concurrent_refill(self):
        """Test concurrent token refill."""
        bucket = TokenBucket(capacity=50, refill_rate=10, refill_interval=0.1)
        
        # Consume all tokens
        bucket.consume(50)
        self.assertEqual(bucket.tokens, 0)
        
        refill_results = []
        
        def refill_worker():
            """Worker function for concurrent refill."""
            time.sleep(0)  # Wait for 2 refill intervals
            bucket._refill()
            refill_results.append(bucket.tokens)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=refill_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All threads should see the same token count
        unique_results = set(refill_results)
        self.assertEqual(len(unique_results), 1)
        self.assertIn(20, unique_results)  # 10 * 2 refills
    
    def test_race_condition_consumption(self):
        """Test race condition in token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=1)
        
        consumption_results = []
        
        def race_worker():
            """Worker function for race condition test."""
            result = bucket.consume(1)
            consumption_results.append(result)
        
        # Create many threads trying to consume the last token
        threads = []
        for i in range(20):
            thread = threading.Thread(target=race_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Only one should succeed in consuming the last token
        successful_consumptions = sum(1 for result in consumption_results if result)
        self.assertEqual(successful_consumptions, 10)  # Initial capacity
        self.assertEqual(bucket.tokens, 0)


class TokenBucketIntegrationTest(TestCase):
    """Integration tests for token bucket with rate limit models."""
    
    def setUp(self):
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=10,
            time_unit='minute',
            time_value=1
        )
    
    def test_token_bucket_with_rate_limit_config(self):
        """Test token bucket integration with rate limit config."""
        # Create token bucket based on config
        bucket = TokenBucket(
            capacity=self.config.requests_per_unit,
            refill_rate=self.config.requests_per_unit,
            refill_interval=60  # 1 minute
        )
        
        # Test basic functionality
        self.assertEqual(bucket.capacity, 10)
        self.assertEqual(bucket.refill_rate, 10)
        self.assertEqual(bucket.refill_interval, 60)
        
        # Should be able to consume up to capacity
        for i in range(10):
            self.assertTrue(bucket.consume(1))
        
        # Should not be able to consume more
        self.assertFalse(bucket.consume(1))
    
    def test_token_bucket_time_unit_conversion(self):
        """Test conversion of time units to seconds."""
        time_unit_conversions = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        
        for time_unit, seconds in time_unit_conversions.items():
            with self.subTest(time_unit=time_unit):
                config = RateLimitConfigFactory(
                    user=self.user,
                    rate_limit_type='user',
                    requests_per_unit=5,
                    time_unit=time_unit,
                    time_value=1
                )
                
                bucket = TokenBucket(
                    capacity=config.requests_per_unit,
                    refill_rate=config.requests_per_unit,
                    refill_interval=seconds
                )
                
                self.assertEqual(bucket.refill_interval, seconds)
    
    def test_token_bucket_with_different_configurations(self):
        """Test token bucket with different rate limit configurations."""
        configs = [
            {'requests_per_unit': 5, 'time_unit': 'second', 'time_value': 1},
            {'requests_per_unit': 10, 'time_unit': 'minute', 'time_value': 1},
            {'requests_per_unit': 100, 'time_unit': 'hour', 'time_value': 1},
            {'requests_per_unit': 1000, 'time_unit': 'day', 'time_value': 1},
        ]
        
        for config_data in configs:
            with self.subTest(config=config_data):
                config = RateLimitConfigFactory(
                    user=self.user,
                    rate_limit_type='user',
                    **config_data
                )
                
                # Convert time unit to seconds
                time_unit_seconds = {
                    'second': 1,
                    'minute': 60,
                    'hour': 3600,
                    'day': 86400
                }[config.time_unit]
                
                bucket = TokenBucket(
                    capacity=config.requests_per_unit,
                    refill_rate=config.requests_per_unit,
                    refill_interval=time_unit_seconds * config.time_value
                )
                
                # Test basic functionality
                self.assertTrue(bucket.consume(1))
                self.assertGreater(bucket.get_tokens(), 0)
    
    def test_token_bucket_with_user_profiles(self):
        """Test token bucket with user rate limit profiles."""
        # Create user profile with custom limits
        profile = UserRateLimitProfileFactory(
            user=self.user,
            custom_daily_limit=50,
            custom_hourly_limit=5
        )
        
        # Use custom hourly limit for token bucket
        bucket = TokenBucket(
            capacity=profile.custom_hourly_limit,
            refill_rate=profile.custom_hourly_limit,
            refill_interval=3600  # 1 hour
        )
        
        self.assertEqual(bucket.capacity, 5)
        self.assertEqual(bucket.refill_rate, 5)
        
        # Test consumption
        for i in range(5):
            self.assertTrue(bucket.consume(1))
        
        self.assertFalse(bucket.consume(1))
    
    def test_token_bucket_with_premium_users(self):
        """Test token bucket with premium user limits."""
        # Create premium user profile
        profile = UserRateLimitProfileFactory(
            user=self.user,
            is_premium=True,
            custom_daily_limit=200,
            custom_hourly_limit=20
        )
        
        # Premium users get higher limits
        bucket = TokenBucket(
            capacity=profile.custom_hourly_limit,
            refill_rate=profile.custom_hourly_limit,
            refill_interval=3600
        )
        
        self.assertEqual(bucket.capacity, 20)
        self.assertEqual(bucket.refill_rate, 20)
        
        # Should be able to consume more tokens
        for i in range(20):
            self.assertTrue(bucket.consume(1))
        
        self.assertFalse(bucket.consume(1))


class TokenBucketPerformanceTest(TestCase):
    """Performance tests for token bucket algorithm."""
    
    def test_token_bucket_consumption_performance(self):
        """Test performance of token consumption."""
        bucket = TokenBucket(capacity=10000, refill_rate=1000, refill_interval=1)
        
        import time
        
        start_time = time.time()
        
        # Consume tokens rapidly
        for i in range(10000):
            bucket.consume(1)
        
        end_time = time.time()
        consumption_time = end_time - start_time
        
        # Should complete in under 1 second
        self.assertLess(consumption_time, 1.0)
        self.assertEqual(bucket.tokens, 0)
    
    def test_token_bucket_refill_performance(self):
        """Test performance of token refill."""
        bucket = TokenBucket(capacity=1000, refill_rate=100, refill_interval=0.01)
        
        import time
        
        # Consume all tokens
        for i in range(1000):
            bucket.consume(1)
        
        start_time = time.time()
        
        # Perform many refills
        for i in range(100):
            time.sleep(0)  # Wait for refill interval
            bucket._refill()
        
        end_time = time.time()
        refill_time = end_time - start_time
        
        # Should complete in reasonable time
        self.assertLess(refill_time, 2.0)
        self.assertGreater(bucket.tokens, 0)
    
    def test_token_bucket_memory_usage(self):
        """Test memory usage of token bucket."""
        import sys
        
        # Create many token buckets
        buckets = []
        for i in range(1000):
            bucket = TokenBucket(capacity=100, refill_rate=10, refill_interval=1)
            buckets.append(bucket)
        
        # Check memory usage (rough estimate)
        bucket_size = sys.getsizeof(buckets[0])
        total_size = bucket_size * len(buckets)
        
        # Should be reasonable (less than 10MB)
        self.assertLess(total_size, 10 * 1024 * 1024)
        
        # Test consumption on all buckets
        for bucket in buckets:
            bucket.consume(1)
        
        # All should have 99 tokens remaining
        for bucket in buckets:
            self.assertEqual(bucket.tokens, 99)
    
    def test_token_bucket_concurrent_performance(self):
        """Test performance under concurrent load."""
        bucket = TokenBucket(capacity=1000, refill_rate=100, refill_interval=1)
        
        results = []
        
        def performance_worker():
            """Worker function for performance test."""
            for i in range(100):
                if bucket.consume(1):
                    results.append(True)
                else:
                    results.append(False)
        
        import time
        
        start_time = time.time()
        
        # Create many threads
        threads = []
        for i in range(20):
            thread = threading.Thread(target=performance_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        performance_time = end_time - start_time
        
        # Should complete in reasonable time
        self.assertLess(performance_time, 2.0)
        self.assertEqual(len(results), 2000)  # 20 threads * 100 operations


class TokenBucketAlgorithmTest(TestCase):
    """Algorithm-specific tests for token bucket."""
    
    def test_token_bucket_mathematical_properties(self):
        """Test mathematical properties of token bucket."""
        bucket = TokenBucket(capacity=10, refill_rate=2, refill_interval=1)
        
        # Property 1: Tokens never exceed capacity
        for i in range(100):
            bucket._refill()
            self.assertLessEqual(bucket.tokens, bucket.capacity)
        
        # Property 2: Tokens never go negative
        bucket.consume(10)
        for i in range(100):
            bucket.consume(1)  # Should fail without negative tokens
            self.assertGreaterEqual(bucket.tokens, 0)
        
        # Property 3: Refill rate is consistent
        bucket.tokens = 0
        bucket.last_refill = time.time() - 5  # 5 seconds ago
        
        bucket._refill()
        expected_tokens = min(10, 2 * 5)  # 2 tokens/second * 5 seconds
        self.assertEqual(bucket.tokens, expected_tokens)
    
    def test_token_bucket_refill_precision(self):
        """Test precision of token refill timing."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=0.1)
        
        # Consume all tokens
        bucket.consume(10)
        
        # Test precise refill timing
        start_time = time.time()
        bucket.last_refill = start_time - 0.25  # 0.25 seconds ago (2.5 intervals)
        
        bucket._refill()
        
        # Should have 2 tokens (floor(2.5 intervals) * 1 token/interval)
        self.assertEqual(bucket.tokens, 2)
        
        # Remaining time should be 0.05 seconds (0.25 - 2 * 0.1)
        expected_remaining = 0.05
        actual_remaining = (start_time - 0.25) % 0.1
        self.assertAlmostEqual(actual_remaining, expected_remaining, places=2)
    
    def test_token_bucket_burst_capacity(self):
        """Test burst capacity handling."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=1)
        
        # Fill bucket to capacity
        bucket.tokens = 10
        
        # Should allow burst of up to capacity
        self.assertTrue(bucket.consume(10))
        self.assertEqual(bucket.tokens, 0)
        
        # Should not allow burst beyond capacity
        self.assertFalse(bucket.consume(1))
        
        # After refill, should allow smaller burst
        bucket.last_refill = time.time() - 2  # 2 seconds ago
        bucket._refill()
        
        self.assertEqual(bucket.tokens, 2)
        self.assertTrue(bucket.consume(2))
        self.assertFalse(bucket.consume(1))
    
    def test_token_bucket_average_rate(self):
        """Test average rate limiting."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=1)
        
        # Consume all tokens
        bucket.consume(10)
        
        # Track consumption over time
        consumption_times = []
        
        # Try to consume every 0.5 seconds
        for i in range(20):
            start_time = time.time()
            success = bucket.consume(1)
            end_time = time.time()
            
            consumption_times.append({
                'success': success,
                'time': end_time,
                'tokens': bucket.tokens
            })
            
            time.sleep(0)
        
        # Should be rate limited to 1 token per second
        successful_consumptions = [c for c in consumption_times if c['success']]
        self.assertEqual(len(successful_consumptions), 10)  # Initial capacity + 10 refills


class TokenBucketErrorHandlingTest(TestCase):
    """Error handling tests for token bucket."""
    
    def test_token_bucket_invalid_parameters(self):
        """Test handling of invalid parameters."""
        # Negative capacity
        with self.assertRaises(ValueError):
            TokenBucket(capacity=-1, refill_rate=1)
        
        # Negative refill rate
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=-1)
        
        # Zero refill interval
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=1, refill_interval=0)
        
        # Negative refill interval
        with self.assertRaises(ValueError):
            TokenBucket(capacity=10, refill_rate=1, refill_interval=-1)
    
    def test_token_bucket_edge_case_consumption(self):
        """Test edge cases in token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=1)
        
        # Consume more than available
        self.assertFalse(bucket.consume(11))
        self.assertEqual(bucket.tokens, 10)  # Should remain unchanged
        
        # Consume zero tokens
        self.assertTrue(bucket.consume(0))
        self.assertEqual(bucket.tokens, 10)  # Should remain unchanged
        
        # Consume negative tokens (should be invalid)
        with self.assertRaises(ValueError):
            bucket.consume(-1)
    
    def test_token_bucket_time_edge_cases(self):
        """Test edge cases related to timing."""
        bucket = TokenBucket(capacity=10, refill_rate=1, refill_interval=1)
        
        # Set last_refill to future time
        bucket.last_refill = time.time() + 10
        
        # Refill should not add tokens
        bucket._refill()
        self.assertEqual(bucket.tokens, 10)  # Should remain at capacity
        
        # Set last_refill to very old time
        bucket.last_refill = time.time() - 1000000  # Very old time
        
        # Refill should not exceed capacity
        bucket._refill()
        self.assertEqual(bucket.tokens, 10)  # Should be at capacity
    
    def test_token_bucket_concurrent_edge_cases(self):
        """Test edge cases in concurrent operations."""
        bucket = TokenBucket(capacity=1, refill_rate=1, refill_interval=1)
        
        results = []
        
        def edge_case_worker():
            """Worker for edge case testing."""
            try:
                result = bucket.consume(1)
                results.append(result)
            except Exception as e:
                results.append(e)
        
        # Create many threads trying to consume the single token
        threads = []
        for i in range(100):
            thread = threading.Thread(target=edge_case_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have exactly one success and 99 failures
        successes = [r for r in results if r is True]
        failures = [r for r in results if r is False]
        
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 99)
        self.assertEqual(bucket.tokens, 0)


if __name__ == '__main__':
    pytest.main([__file__])

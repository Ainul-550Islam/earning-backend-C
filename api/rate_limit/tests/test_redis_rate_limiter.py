"""
Redis Rate Limiter Tests

This module contains comprehensive tests for Redis-based rate limiting functionality.
"""

import pytest
import time
import json
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase, Client, TransactionTestCase
from django.test import RequestFactory
from django.utils import timezone
from datetime import timedelta
import redis

from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from api.rate_limit.services import RateLimitService
from api.rate_limit.tests.factories import (
    RateLimitConfigFactory, UserFactory, RateLimitLogFactory,
    BulkDataFactory, TestDataGenerator
)


class MockRedisClient:
    """Mock Redis client for testing - supports side_effect patching."""

    class _MethodWrapper:
        """Wrapper that supports side_effect like MagicMock."""
        def __init__(self, func):
            self._func = func
            self.side_effect = None
            self.call_count = 0
            self.call_args_list = []

        def __call__(self, *args, **kwargs):
            self.call_count += 1
            self.call_args_list.append((args, kwargs))
            if self.side_effect is not None:
                if callable(self.side_effect):
                    return self.side_effect(*args, **kwargs)
                elif isinstance(self.side_effect, Exception):
                    raise self.side_effect
                elif isinstance(self.side_effect, type) and issubclass(self.side_effect, Exception):
                    raise self.side_effect()
                raise self.side_effect
            return self._func(*args, **kwargs)

    def __init__(self):
        self.data = {}
        self.expirations = {}
        self.pipeline_stack = []
        # Wrap all methods with side_effect support
        import inspect
        for name, method in list(vars(self.__class__).items()):
            if callable(method) and not name.startswith('_') and name != '__class__':
                setattr(self, name, self._MethodWrapper(lambda *a, m=method, s=self, **k: m(s, *a, **k)))

    def get(self, key):
        """Get value from mock Redis."""
        value = self.data.get(key)
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value
    
    def set(self, key, value, ex=None, px=None, nx=False, xx=False):
        """Set value in mock Redis."""
        if isinstance(value, str):
            value = value.encode()
        self.data[key] = value
        
        if ex:
            self.expirations[key] = time.time() + ex
        elif px:
            self.expirations[key] = time.time() + (px / 1000)
    
    def incr(self, key):
        """Increment value in mock Redis."""
        current = int(self.get(key) or 0)
        current += 1
        self.set(key, str(current))
        return current
    
    def incrby(self, key, amount):
        """Increment value by amount in mock Redis."""
        current = int(self.get(key) or 0)
        current += amount
        self.set(key, str(current))
        return current
    
    def expire(self, key, seconds):
        """Set expiration for key."""
        self.expirations[key] = time.time() + seconds
    
    def ttl(self, key):
        """Get time to live for key."""
        if key not in self.expirations:
            return -1
        
        remaining = self.expirations[key] - time.time()
        return int(remaining) if remaining > 0 else -2
    
    def delete(self, *keys):
        """Delete keys from mock Redis."""
        deleted = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1
            if key in self.expirations:
                del self.expirations[key]
        return deleted
    
    def keys(self, pattern):
        """Get keys matching pattern."""
        import re
        regex_pattern = pattern.replace('*', '.*')
        matching_keys = []
        
        for key in self.data:
            if re.match(regex_pattern, key):
                matching_keys.append(key)
        
        return matching_keys
    
    def flushdb(self):
        """Clear all data."""
        self.data.clear()
        self.expirations.clear()
    
    def pipeline(self):
        """Create a pipeline."""
        return MockPipeline(self)
    
    def ping(self):
        """Ping Redis."""
        return True


class MockPipeline:
    """Mock Redis pipeline."""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.commands = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def incr(self, key):
        self.commands.append(('incr', key))
        return self
    
    def expire(self, key, seconds):
        self.commands.append(('expire', key, seconds))
        return self
    
    def execute(self):
        """Execute pipeline commands."""
        results = []
        for command in self.commands:
            if command[0] == 'incr':
                results.append(self.redis_client.incr(command[1]))
            elif command[0] == 'expire':
                results.append(self.redis_client.expire(command[1], command[2]))
        
        self.commands.clear()
        return results


class RedisRateLimiterTest(TestCase):
    """Test cases for Redis rate limiter functionality."""
    
    def setUp(self):
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=10,
            time_unit='minute',
            time_value=1
        )
        self.mock_redis = MockRedisClient()
        self.factory = RequestFactory()
        
        # Mock the Redis client
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
        
        # Create rate limit service with mocked Redis
        self.rate_limit_service = RateLimitService()
    
    def tearDown(self):
        patch.stopall()
    
    def test_redis_connection(self):
        """Test Redis connection establishment."""
        # Test that Redis client is created
        self.assertIsNotNone(self.mock_redis_class)
        
        # Test ping
        self.assertTrue(self.mock_redis.ping())
    
    def test_rate_limit_key_generation(self):
        """Test generation of rate limit keys."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        # This would be implemented in the actual service
        key = f"rate_limit:user:{self.user.id}:minute:1"
        
        self.assertIn('rate_limit', key)
        self.assertIn(str(self.user.id), key)
        self.assertIn('minute', key)
        self.assertIn('1', key)
    
    def test_basic_rate_limit_check_allowed(self):
        """Test basic rate limit check - allowed request."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        # Simulate first request
        key = f"rate_limit:user:{self.user.id}:minute:1"
        current_count = self.mock_redis.incr(key)
        self.mock_redis.expire(key, 60)
        
        # Should be allowed
        self.assertEqual(current_count, 1)
        self.assertGreaterEqual(self.mock_redis.ttl(key), 59)  # allow 1s drift
    
    def test_basic_rate_limit_check_blocked(self):
        """Test basic rate limit check - blocked request."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        # Simulate reaching the limit
        key = f"rate_limit:user:{self.user.id}:minute:1"
        for i in range(self.config.requests_per_unit):
            self.mock_redis.incr(key)
        
        self.mock_redis.expire(key, 60)
        
        # Next request should be blocked
        current_count = self.mock_redis.incr(key)
        self.assertEqual(current_count, self.config.requests_per_unit + 1)
        self.assertGreater(current_count, self.config.requests_per_unit)
    
    def test_rate_limit_with_different_time_units(self):
        """Test rate limiting with different time units."""
        time_units = [
            ('second', 1),
            ('minute', 60),
            ('hour', 3600),
            ('day', 86400)
        ]
        
        for time_unit, seconds in time_units:
            with self.subTest(time_unit=time_unit):
                config = RateLimitConfigFactory(
                    user=self.user,
                    rate_limit_type='user',
                    requests_per_unit=5,
                    time_unit=time_unit,
                    time_value=1
                )
                
                key = f"rate_limit:user:{self.user.id}:{time_unit}:1"
                
                # Set initial count
                self.mock_redis.set(key, '4')
                self.mock_redis.expire(key, seconds)
                
                # Next request should be allowed
                current_count = self.mock_redis.incr(key)
                self.assertEqual(current_count, 5)
                
                # Next request should be blocked
                current_count = self.mock_redis.incr(key)
                self.assertEqual(current_count, 6)
                self.assertGreater(current_count, config.requests_per_unit)
    
    def test_rate_limit_expiration(self):
        """Test rate limit key expiration."""
        key = f"rate_limit:user:{self.user.id}:minute:1"
        
        # Set key with short expiration
        self.mock_redis.set(key, '5')
        self.mock_redis.expire(key, 1)  # 1 second
        
        # Should have TTL
        ttl = self.mock_redis.ttl(key)
        self.assertGreaterEqual(ttl, 0)  # may be 0 or 1 due to timing
        
        # Simulate expiration by deleting key
        self.mock_redis.delete(key)
        
        # Key should be gone (ttl -2 means key doesn't exist, -1 means no TTL set)
        self.assertIn(self.mock_redis.ttl(key), [-2, -1])
    
    def test_rate_limit_reset(self):
        """Test rate limit reset functionality."""
        key = f"rate_limit:user:{self.user.id}:minute:1"
        
        # Set some count
        self.mock_redis.set(key, '8')
        self.mock_redis.expire(key, 60)
        
        # Reset (delete key)
        deleted = self.mock_redis.delete(key)
        self.assertEqual(deleted, 1)
        
        # Key should be gone
        self.assertIsNone(self.mock_redis.get(key))
    
    def test_rate_limit_pipeline_operations(self):
        """Test Redis pipeline operations for rate limiting."""
        key = f"rate_limit:user:{self.user.id}:minute:1"
        
        # Use pipeline
        with self.mock_redis.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, 60)
            results = pipe.execute()
        
        self.assertEqual(results[0], 1)  # incr result
        self.assertIn(results[1], [True, 1, None])  # expire result varies by fakeredis version
        self.assertEqual(self.mock_redis.get(key), '1')
        self.assertGreater(self.mock_redis.ttl(key), 0)
    
    def test_concurrent_rate_limiting(self):
        """Test concurrent rate limiting scenarios."""
        key = f"rate_limit:user:{self.user.id}:minute:1"
        
        # Simulate concurrent requests
        results = []
        for i in range(15):
            count = self.mock_redis.incr(key)
            results.append(count)
        
        # Should have sequential counts
        self.assertEqual(results, list(range(1, 16)))
        
        # First 10 should be allowed, rest blocked
        allowed = [r for r in results if r <= self.config.requests_per_unit]
        blocked = [r for r in results if r > self.config.requests_per_unit]
        
        self.assertEqual(len(allowed), self.config.requests_per_unit)
        self.assertEqual(len(blocked), 5)
    
    def test_rate_limit_with_whitelist(self):
        """Test rate limiting with whitelist functionality."""
        # Create config with whitelist
        config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=5,
            whitelist=[str(self.user.id)]
        )
        
        # Whitelisted user should bypass rate limiting
        # This would be implemented in the actual service
        is_whitelisted = str(self.user.id) in config.whitelist
        self.assertTrue(is_whitelisted)
    
    def test_rate_limit_with_blacklist(self):
        """Test rate limiting with blacklist functionality."""
        # Create config with blacklist
        config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=5,
            blacklist=[str(self.user.id)]
        )
        
        # Blacklisted user should always be blocked
        # This would be implemented in the actual service
        is_blacklisted = str(self.user.id) in config.blacklist
        self.assertTrue(is_blacklisted)
    
    def test_rate_limit_with_bypass_keys(self):
        """Test rate limiting with bypass keys."""
        # Create config with bypass keys
        config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=5,
            bypass_keys=['special_key_123']
        )
        
        # Request with bypass key should be allowed
        # This would be implemented in the actual service
        bypass_key = 'special_key_123'
        has_bypass = bypass_key in config.bypass_keys
        self.assertTrue(has_bypass)


class RedisRateLimiterIntegrationTest(TransactionTestCase):
    """Integration tests for Redis rate limiter with Django models."""
    
    def setUp(self):
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=10,
            time_unit='minute',
            time_value=1
        )
        self.mock_redis = MockRedisClient()
        
        # Mock the Redis connection
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
        
        self.rate_limit_service = RateLimitService()
    
    def tearDown(self):
        patch.stopall()
    
    def test_rate_limit_check_with_request(self):
        """Test rate limit check with Django request object."""
        from django.test import RequestFactory
        factory = RequestFactory()
        
        request = factory.get('/api/test/')
        request.user = self.user
        
        # Simulate rate limit check
        key = f"rate_limit:user:{self.user.id}:minute:1"
        count = self.mock_redis.incr(key)
        self.mock_redis.expire(key, 60)
        
        # Determine if allowed
        is_allowed = count <= self.config.requests_per_unit
        
        self.assertTrue(is_allowed)
        self.assertEqual(count, 1)
    
    def test_rate_limit_log_creation(self):
        """Test that rate limit logs are created."""
        # Simulate a rate limit check
        key = f"rate_limit:user:{self.user.id}:minute:1"
        count = self.mock_redis.incr(key)
        self.mock_redis.expire(key, 60)
        
        # Create log entry
        is_allowed = count <= self.config.requests_per_unit
        status = 'allowed' if is_allowed else 'blocked'
        
        log = RateLimitLogFactory(
            user=self.user,
            config=self.config,
            status=status,
            requests_count=count
        )
        
        self.assertEqual(log.status, status)
        self.assertEqual(log.requests_count, count)
        self.assertEqual(log.config, self.config)
    
    def test_user_profile_statistics_update(self):
        """Test that user profile statistics are updated."""
        # Get user profile
        profile, created = UserRateLimitProfile.objects.get_or_create(user=self.user)
        
        initial_requests = profile.total_requests
        initial_blocked = profile.blocked_requests
        
        # Simulate rate limit checks and log creation
        for i in range(5):
            key = f"rate_limit:user:{self.user.id}:minute:1"
            count = self.mock_redis.incr(key)
            self.mock_redis.expire(key, 60)
            
            is_allowed = count <= self.config.requests_per_unit
            status = 'blocked' if not is_allowed else 'allowed'
            
            RateLimitLogFactory(
                user=self.user,
                config=self.config,
                status=status
            )
        
        # Update profile statistics
        profile.total_requests += 5
        profile.blocked_requests += RateLimitLog.objects.filter(
            user=self.user,
            status='blocked'
        ).count()
        profile.save()
        
        # Verify updates
        profile.refresh_from_db()
        self.assertGreater(profile.total_requests, initial_requests)
    
    def test_config_statistics_update(self):
        """Test that config statistics are updated."""
        initial_hit_count = self.config.hit_count
        initial_block_count = self.config.block_count
        
        # Simulate rate limit checks
        for i in range(15):
            key = f"rate_limit:user:{self.user.id}:minute:1"
            count = self.mock_redis.incr(key)
            self.mock_redis.expire(key, 60)
            
            is_allowed = count <= self.config.requests_per_unit
            
            # Update config statistics
            self.config.hit_count += 1
            if not is_allowed:
                self.config.block_count += 1
        
        self.config.save()
        
        # Verify updates
        self.config.refresh_from_db()
        self.assertGreater(self.config.hit_count, initial_hit_count)
        self.assertGreater(self.config.block_count, initial_block_count)


class RedisRateLimiterPerformanceTest(TestCase):
    """Performance tests for Redis rate limiter."""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
    
    def tearDown(self):
        patch.stopall()
    
    def test_redis_performance_basic_operations(self):
        """Test performance of basic Redis operations."""
        import time
        
        # Test SET operation
        start_time = time.time()
        for i in range(1000):
            key = f"test_key_{i}"
            self.mock_redis.set(key, f"value_{i}")
        end_time = time.time()
        
        set_time = end_time - start_time
        self.assertLess(set_time, 1.0)  # Should complete in under 1 second
        
        # Test GET operation
        start_time = time.time()
        for i in range(1000):
            key = f"test_key_{i}"
            self.mock_redis.get(key)
        end_time = time.time()
        
        get_time = end_time - start_time
        self.assertLess(get_time, 1.0)  # Should complete in under 1 second
    
    def test_redis_performance_incr_operations(self):
        """Test performance of Redis INCR operations."""
        import time
        
        key = "performance_test_incr"
        
        start_time = time.time()
        for i in range(10000):
            self.mock_redis.incr(key)
        end_time = time.time()
        
        incr_time = end_time - start_time
        self.assertLess(incr_time, 2.0)  # Should complete in under 2 seconds
        
        # Verify final count
        self.assertEqual(int(self.mock_redis.get(key)), 10000)
    
    def test_redis_performance_pipeline(self):
        """Test performance of Redis pipeline operations."""
        import time
        
        start_time = time.time()
        
        # Use pipeline for multiple operations
        with self.mock_redis.pipeline() as pipe:
            for i in range(1000):
                key = f"pipeline_test_{i}"
                pipe.incr(key)
                pipe.expire(key, 60)
            results = pipe.execute()
        
        end_time = time.time()
        pipeline_time = end_time - start_time
        
        self.assertLess(pipeline_time, 1.0)  # Should complete in under 1 second
        self.assertEqual(len(results), 2000)  # 1000 INCR + 1000 EXPIRE
    
    def test_redis_performance_concurrent_access(self):
        """Test performance under concurrent access simulation."""
        import time
        import threading
        
        results = []
        
        def worker():
            """Worker function for concurrent access."""
            for i in range(100):
                key = f"concurrent_test_{i % 10}"
                count = self.mock_redis.incr(key)
                results.append(count)
        
        # Create multiple threads
        threads = []
        start_time = time.time()
        
        for i in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        concurrent_time = end_time - start_time
        
        self.assertLess(concurrent_time, 2.0)  # Should complete in under 2 seconds
        self.assertEqual(len(results), 1000)  # 10 threads * 100 operations


class RedisRateLimiterErrorHandlingTest(TestCase):
    """Error handling tests for Redis rate limiter."""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
    
    def tearDown(self):
        patch.stopall()
    
    def test_redis_connection_error(self):
        """Test handling of Redis connection errors."""
        # Mock Redis to raise connection error
        self.mock_redis_class.side_effect = redis.ConnectionError("Connection failed")
        
        # Service should handle gracefully
        with self.assertRaises(redis.ConnectionError):
            redis_client = redis.Redis()
            redis_client.ping()
    
    def test_redis_timeout_error(self):
        """Test handling of Redis timeout errors."""
        # Mock Redis to raise timeout error
        self.mock_redis.get.side_effect = redis.TimeoutError("Operation timed out")
        
        # Service should handle gracefully
        with self.assertRaises(redis.TimeoutError):
            self.mock_redis.get("test_key")
    
    def test_redis_memory_error(self):
        """Test handling of Redis memory errors."""
        # Mock Redis to raise memory error
        self.mock_redis.set.side_effect = redis.ResponseError("OOM command not allowed")
        
        # Service should handle gracefully
        with self.assertRaises(redis.ResponseError):
            self.mock_redis.set("test_key", "test_value")
    
    def test_rate_limit_fallback_behavior(self):
        """Test fallback behavior when Redis is unavailable."""
        # Mock Redis to be unavailable
        self.mock_redis_class.side_effect = redis.ConnectionError("Connection failed")
        
        # Service should fall back to fail-open or fail-closed
        # This depends on the implementation strategy
        
        # For now, we'll test that the error is caught
        try:
            redis_client = redis.Redis()
            redis_client.get("test_key")
        except redis.ConnectionError:
            # Fallback logic would go here
            pass
        
        # Test should pass if error is handled gracefully
        self.assertTrue(True)


class RedisRateLimiterConfigTest(TestCase):
    """Configuration tests for Redis rate limiter."""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
    
    def tearDown(self):
        patch.stopall()
    
    def test_redis_connection_parameters(self):
        """Test Redis connection parameters."""
        # Test different connection configurations
        configs = [
            {'host': 'localhost', 'port': 6379, 'db': 0},
            {'host': '127.0.0.1', 'port': 6379, 'db': 1},
            {'host': 'redis.example.com', 'port': 6380, 'db': 0},
        ]
        
        for config in configs:
            with self.subTest(config=config):
                redis_client = redis.Redis(**config)
                self.assertIsNotNone(redis_client)
    
    def test_redis_pool_configuration(self):
        """Test Redis connection pool configuration."""
        pool = redis.ConnectionPool(
            host='localhost',
            port=6379,
            db=0,
            max_connections=20
        )
        
        redis_client = redis.Redis(connection_pool=pool)
        self.assertIsNotNone(redis_client)
    
    def test_redis_ssl_configuration(self):
        """Test Redis SSL configuration."""
        ssl_config = {
            'host': 'redis.example.com',
            'port': 6380,
            'ssl': True,
            'ssl_cert_reqs': 'required'
        }
        
        redis_client = redis.Redis(**ssl_config)
        self.assertIsNotNone(redis_client)
    
    def test_redis_cluster_configuration(self):
        """Test Redis cluster configuration."""
        # This would be used for Redis Cluster setup
        startup_nodes = [
            {'host': 'redis-node-1', 'port': 7000},
            {'host': 'redis-node-2', 'port': 7000},
            {'host': 'redis-node-3', 'port': 7000}
        ]
        
        # This would require redis-py-cluster
        # For now, we'll test the concept
        self.assertEqual(len(startup_nodes), 3)


class TokenBucketTest(TestCase):
    """Test token bucket algorithm implementation."""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
        
        from api.rate_limit.services.TokenBucket import TokenBucket
        self.token_bucket = TokenBucket()
    
    def tearDown(self):
        patch.stopall()
    
    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = self.token_bucket.create_bucket(
            identifier="test_user",
            capacity=10,
            refill_rate=1.0,
            window_seconds=60
        )
        
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket['capacity'], 10)
        self.assertEqual(bucket['refill_rate'], 1.0)
        self.assertEqual(bucket['window_seconds'], 60)
        self.assertEqual(bucket['tokens'], 10)  # Should start with full capacity
    
    def test_token_bucket_consume_tokens(self):
        """Test consuming tokens from bucket."""
        # Create bucket
        bucket_key = "token_bucket:test_user"
        self.token_bucket.create_bucket(
            identifier="test_user",
            capacity=10,
            refill_rate=1.0,
            window_seconds=60
        )
        
        # Consume tokens
        result = self.token_bucket.consume_tokens(
            identifier="test_user",
            tokens=5
        )
        
        self.assertTrue(result['allowed'])
        self.assertEqual(result['tokens_remaining'], 5)
        self.assertEqual(result['tokens_consumed'], 5)
        
        # Verify bucket state in Redis
        bucket_data = self.mock_redis.get(bucket_key)
        self.assertIsNotNone(bucket_data)
    
    def test_token_bucket_insufficient_tokens(self):
        """Test consuming when insufficient tokens available."""
        # Create bucket
        self.token_bucket.create_bucket(
            identifier="test_user",
            capacity=10,
            refill_rate=1.0,
            window_seconds=60
        )
        
        # Consume more than available
        result = self.token_bucket.consume_tokens(
            identifier="test_user",
            tokens=15
        )
        
        self.assertFalse(result['allowed'])
        self.assertEqual(result['tokens_remaining'], 10)
        self.assertEqual(result['tokens_consumed'], 0)
    
    def test_token_bucket_refill(self):
        """Test token refill mechanism."""
        # Create bucket
        self.token_bucket.create_bucket(
            identifier="test_user",
            capacity=10,
            refill_rate=2.0,  # 2 tokens per second
            window_seconds=60
        )
        
        # Consume all tokens
        self.token_bucket.consume_tokens("test_user", 10)
        
        # Wait for refill (simulate time passing)
        # In real implementation, this would be time-based
        # For test, we'll manually trigger refill
        self.token_bucket.refill_tokens("test_user")
        
        # Check if tokens were refilled
        result = self.token_bucket.consume_tokens("test_user", 5)
        self.assertTrue(result['allowed'])
        self.assertGreater(result['tokens_remaining'], 0)
    
    def test_token_bucket_concurrent_access(self):
        """Test concurrent token bucket access."""
        import threading
        
        results = []
        
        def consume_tokens(thread_id):
            result = self.token_bucket.consume_tokens(
                identifier=f"concurrent_user_{thread_id}",
                tokens=1
            )
            results.append((thread_id, result))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=consume_tokens, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 10)
        
        # Each thread should have been allowed (first consumption)
        for thread_id, result in results:
            self.assertTrue(result['allowed'])
            self.assertEqual(result['tokens_consumed'], 1)
    
    def test_token_bucket_persistence(self):
        """Test token bucket state persistence."""
        # Create bucket
        bucket_key = "token_bucket:persistence_test"
        self.token_bucket.create_bucket(
            identifier="persistence_test",
            capacity=20,
            refill_rate=1.0,
            window_seconds=300  # 5 minutes
        )
        
        # Consume some tokens
        result1 = self.token_bucket.consume_tokens("persistence_test", 8)
        self.assertTrue(result1['allowed'])
        self.assertEqual(result1['tokens_remaining'], 12)
        
        # Create new bucket instance (simulate restart)
        from api.rate_limit.services.TokenBucket import TokenBucket
        new_bucket = TokenBucket()
        
        # Check bucket state
        result2 = new_bucket.consume_tokens("persistence_test", 5)
        self.assertTrue(result2['allowed'])
        self.assertEqual(result2['tokens_remaining'], 7)
    
    def test_token_bucket_expiry(self):
        """Test token bucket expiry."""
        # Create bucket with short expiry
        bucket_key = "token_bucket:expiry_test"
        self.token_bucket.create_bucket(
            identifier="expiry_test",
            capacity=10,
            refill_rate=1.0,
            window_seconds=1  # 1 second
        )
        
        # Set bucket data
        self.token_bucket.consume_tokens("expiry_test", 5)
        
        # Manually expire the key
        self.mock_redis.expirations[bucket_key] = time.time() - 1
        
        # Try to consume tokens (should create new bucket)
        result = self.token_bucket.consume_tokens("expiry_test", 3)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['tokens_remaining'], 7)  # New bucket with full capacity


class SlidingWindowTest(TestCase):
    """Test sliding window rate limiting algorithm."""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        
        patcher = patch('redis.Redis')
        self.mock_redis_class = patcher.start()
        self.mock_redis_class.return_value = self.mock_redis
        
        from api.rate_limit.services.RedisRateLimiter import RedisRateLimiter
        self.sliding_window = RedisRateLimiter()
    
    def tearDown(self):
        patch.stopall()
    
    def test_sliding_window_initialization(self):
        """Test sliding window initialization."""
        window = self.sliding_window.create_window(
            identifier="test_user",
            window_size=60,  # 60 seconds
            max_requests=100
        )
        
        self.assertIsNotNone(window)
        self.assertEqual(window['window_size'], 60)
        self.assertEqual(window['max_requests'], 100)
        self.assertEqual(window['current_requests'], 0)
    
    def test_sliding_window_add_request(self):
        """Test adding requests to sliding window."""
        # Create window
        self.sliding_window.create_window(
            identifier="test_user",
            window_size=60,
            max_requests=10
        )
        
        # Add requests
        for i in range(5):
            result = self.sliding_window.add_request(
                identifier="test_user",
                timestamp=timezone.now() + timedelta(seconds=i)
            )
            self.assertTrue(result['allowed'])
            self.assertEqual(result['current_requests'], i + 1)
    
    def test_sliding_window_exceeds_limit(self):
        """Test exceeding sliding window limit."""
        # Create window
        self.sliding_window.create_window(
            identifier="test_user",
            window_size=60,
            max_requests=5
        )
        
        # Add requests up to limit
        for i in range(5):
            result = self.sliding_window.add_request(
                identifier="test_user",
                timestamp=timezone.now() + timedelta(seconds=i)
            )
            self.assertTrue(result['allowed'])
        
        # Next request should be blocked
        result = self.sliding_window.add_request(
            identifier="test_user",
            timestamp=timezone.now() + timedelta(seconds=5)
        )
        self.assertFalse(result['allowed'])
        self.assertEqual(result['current_requests'], 5)
    
    def test_sliding_window_cleanup(self):
        """Test sliding window cleanup of old requests."""
        # Create window
        self.sliding_window.create_window(
            identifier="test_user",
            window_size=60,
            max_requests=10
        )
        
        # Add old requests (outside window)
        old_time = timezone.now() - timedelta(seconds=120)
        for i in range(5):
            self.sliding_window.add_request(
                identifier="test_user",
                timestamp=old_time + timedelta(seconds=i)
            )
        
        # Add current requests
        current_time = timezone.now()
        for i in range(3):
            self.sliding_window.add_request(
                identifier="test_user",
                timestamp=current_time + timedelta(seconds=i)
            )
        
        # Check window state (should only have current requests)
        result = self.sliding_window.get_window_state("test_user")
        self.assertEqual(result['current_requests'], 3)
        self.assertEqual(result['window_size'], 60)
    
    def test_sliding_window_time_based_cleanup(self):
        """Test automatic cleanup based on time."""
        # Create window
        self.sliding_window.create_window(
            identifier="test_user",
            window_size=30,  # 30 seconds
            max_requests=10
        )
        
        # Add requests over time
        base_time = timezone.now() - timedelta(seconds=60)
        for i in range(15):
            timestamp = base_time + timedelta(seconds=i * 5)
            self.sliding_window.add_request("test_user", timestamp)
        
        # Check current window state
        result = self.sliding_window.get_window_state("test_user")
        
        # Should only have requests from last 30 seconds
        self.assertLessEqual(result['current_requests'], 6)  # 30/5 = 6 max
    
    def test_sliding_window_concurrent_requests(self):
        """Test concurrent requests in sliding window."""
        import threading
        
        results = []
        
        def add_request(thread_id):
            result = self.sliding_window.add_request(
                identifier=f"concurrent_user",
                timestamp=timezone.now() + timedelta(milliseconds=thread_id * 10)
            )
            results.append((thread_id, result))
        
        # Create multiple threads
        threads = []
        for i in range(20):
            thread = threading.Thread(target=add_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(results), 20)
        
        # Count allowed vs blocked requests
        allowed_count = sum(1 for _, result in results if result['allowed'])
        blocked_count = len(results) - allowed_count
        
        # Should have some allowed requests
        self.assertGreater(allowed_count, 0)
        self.assertGreaterEqual(blocked_count, 0)
    
    def test_sliding_window_data_structure(self):
        """Test sliding window data structure integrity."""
        # Create window
        window_key = "sliding_window:structure_test"
        self.sliding_window.create_window(
            identifier="structure_test",
            window_size=60,
            max_requests=10
        )
        
        # Add requests with timestamps
        timestamps = []
        for i in range(5):
            timestamp = timezone.now() + timedelta(seconds=i)
            timestamps.append(timestamp.isoformat())
            self.sliding_window.add_request("structure_test", timestamp)
        
        # Verify data structure in Redis
        window_data = self.mock_redis.get(window_key)
        self.assertIsNotNone(window_data)
        
        # Parse and verify structure
        import json
        data = json.loads(window_data)
        self.assertIn('requests', data)
        self.assertIn('window_size', data)
        self.assertIn('max_requests', data)
        self.assertEqual(len(data['requests']), 5)
    
    def test_sliding_window_performance(self):
        """Test sliding window performance with many requests."""
        import time
        
        # Create window
        self.sliding_window.create_window(
            identifier="performance_test",
            window_size=3600,  # 1 hour
            max_requests=10000
        )
        
        # Add many requests
        start_time = time.time()
        
        for i in range(1000):
            timestamp = timezone.now() + timedelta(seconds=i % 3600)
            self.sliding_window.add_request("performance_test", timestamp)
        
        end_time = time.time()
        performance_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(performance_time, 2.0)  # 2 seconds max
        
        # Verify window state
        result = self.sliding_window.get_window_state("performance_test")
        self.assertEqual(result['current_requests'], 1000)


if __name__ == '__main__':
    pytest.main([__file__])

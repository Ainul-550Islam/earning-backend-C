"""Test Rate Limiter for Webhooks System

This module contains tests for the webhook rate limiter
including Redis-based rate limiting, sliding windows, and throttling.
"""

import pytest
import time
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from ..services.analytics import RateLimiterService
from ..models import (
    WebhookEndpoint, WebhookRateLimit, WebhookDeliveryLog
)
from ..choices import WebhookStatus

User = get_user_model()


class RateLimiterServiceTest(TestCase):
    """Test cases for RateLimiterService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            rate_limit_per_min=100,
            created_by=self.user,
        )
        self.rate_limiter = RateLimiterService()
    
    def test_is_rate_limited_false(self):
        """Test rate limiting when not exceeded."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = 0  # Current count is 0
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertFalse(is_limited)
            mock_get.assert_called_once()
            mock_set.assert_called_once()
    
    def test_is_rate_limited_true(self):
        """Test rate limiting when exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 100  # Already at limit
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertTrue(is_limited)
            mock_get.assert_called_once()
    
    def test_is_rate_limited_with_cache_miss(self):
        """Test rate limiting with cache miss."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = None  # Cache miss
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertFalse(is_limited)
            mock_get.assert_called_once()
            mock_set.assert_called_once()
    
    def test_get_rate_limit_info(self):
        """Test getting rate limit information."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 50  # Current count is 50
            
            info = self.rate_limiter.get_rate_limit_info(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertEqual(info['current_count'], 50)
            self.assertEqual(info['max_requests'], 100)
            self.assertEqual(info['remaining_requests'], 50)
            self.assertEqual(info['reset_time'], mock_get.return_value)
            self.assertEqual(info['is_rate_limited'], False)
    
    def test_get_rate_limit_info_exceeded(self):
        """Test getting rate limit information when exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 100  # At limit
            
            info = self.rate_limiter.get_rate_limit_info(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertEqual(info['current_count'], 100)
            self.assertEqual(info['max_requests'], 100)
            self.assertEqual(info['remaining_requests'], 0)
            self.assertEqual(info['is_rate_limited'], True)
    
    def test_reset_rate_limit(self):
        """Test resetting rate limit."""
        with patch('django.core.cache.cache.delete') as mock_delete:
            self.rate_limiter.reset_rate_limit(
                endpoint=self.endpoint,
                window_seconds=60
            )
            
            mock_delete.assert_called_once()
    
    def test_increment_rate_limit(self):
        """Test incrementing rate limit."""
        with patch('django.core.cache.cache.incr') as mock_incr:
            mock_incr.return_value = 51  # New count is 51
            
            new_count = self.rate_limiter.increment_rate_limit(
                endpoint=self.endpoint,
                window_seconds=60
            )
            
            self.assertEqual(new_count, 51)
            mock_incr.assert_called_once()
    
    def test_increment_rate_limit_with_ttl(self):
        """Test incrementing rate limit with TTL."""
        with patch('django.core.cache.cache.incr') as mock_incr, \
             patch('django.core.cache.cache.expire') as mock_expire:
            
            mock_incr.return_value = 1  # First increment
            
            new_count = self.rate_limiter.increment_rate_limit(
                endpoint=self.endpoint,
                window_seconds=60
            )
            
            self.assertEqual(new_count, 1)
            mock_incr.assert_called_once()
            mock_expire.assert_called_once()
    
    def test_create_rate_limit_config(self):
        """Test creating rate limit configuration."""
        rate_limit = self.rate_limiter.create_rate_limit(
            endpoint=self.endpoint,
            window_seconds=300,
            max_requests=1000
        )
        
        self.assertIsInstance(rate_limit, WebhookRateLimit)
        self.assertEqual(rate_limit.endpoint, self.endpoint)
        self.assertEqual(rate_limit.window_seconds, 300)
        self.assertEqual(rate_limit.max_requests, 1000)
        self.assertEqual(rate_limit.current_count, 0)
    
    def test_update_rate_limit_config(self):
        """Test updating rate limit configuration."""
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            current_count=50,
            created_by=self.user
        )
        
        updated_rate_limit = self.rate_limiter.update_rate_limit(
            rate_limit=rate_limit,
            window_seconds=300,
            max_requests=1000
        )
        
        self.assertEqual(updated_rate_limit.window_seconds, 300)
        self.assertEqual(updated_rate_limit.max_requests, 1000)
        self.assertEqual(updated_rate_limit.current_count, 0)  # Reset on update
    
    def test_delete_rate_limit_config(self):
        """Test deleting rate limit configuration."""
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            created_by=self.user
        )
        
        result = self.rate_limiter.delete_rate_limit(rate_limit)
        
        self.assertTrue(result)
        with self.assertRaises(WebhookRateLimit.DoesNotExist):
            WebhookRateLimit.objects.get(id=rate_limit.id)
    
    def test_get_rate_limit_config(self):
        """Test getting rate limit configuration."""
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            created_by=self.user
        )
        
        found_rate_limit = self.rate_limiter.get_rate_limit(self.endpoint)
        
        self.assertEqual(found_rate_limit.id, rate_limit.id)
        self.assertEqual(found_rate_limit.window_seconds, 60)
        self.assertEqual(found_rate_limit.max_requests, 100)
    
    def test_get_rate_limit_config_not_found(self):
        """Test getting rate limit configuration when not found."""
        found_rate_limit = self.rate_limiter.get_rate_limit(self.endpoint)
        
        self.assertIsNone(found_rate_limit)
    
    def test_check_webhook_rate_limit_not_exceeded(self):
        """Test webhook rate limit check when not exceeded."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = 50  # Current count is 50
            
            result = self.rate_limiter.check_webhook_rate_limit(self.endpoint)
            
            self.assertFalse(result['is_rate_limited'])
            self.assertEqual(result['current_count'], 50)
            self.assertEqual(result['remaining_requests'], 50)
    
    def test_check_webhook_rate_limit_exceeded(self):
        """Test webhook rate limit check when exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 100  # At limit
            
            result = self.rate_limiter.check_webhook_rate_limit(self.endpoint)
            
            self.assertTrue(result['is_rate_limited'])
            self.assertEqual(result['current_count'], 100)
            self.assertEqual(result['remaining_requests'], 0)
    
    def test_check_webhook_rate_limit_with_custom_config(self):
        """Test webhook rate limit check with custom config."""
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=300,
            max_requests=1000,
            current_count=500,
            created_by=self.user
        )
        
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 500  # Current count is 500
            
            result = self.rate_limiter.check_webhook_rate_limit(self.endpoint)
            
            self.assertFalse(result['is_rate_limited'])
            self.assertEqual(result['current_count'], 500)
            self.assertEqual(result['remaining_requests'], 500)
            self.assertEqual(result['window_seconds'], 300)
            self.assertEqual(result['max_requests'], 1000)
    
    def test_record_webhook_request(self):
        """Test recording a webhook request."""
        with patch('django.core.cache.cache.incr') as mock_incr:
            mock_incr.return_value = 51  # New count is 51
            
            result = self.rate_limiter.record_webhook_request(self.endpoint)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['current_count'], 51)
            mock_incr.assert_called_once()
    
    def test_record_webhook_request_with_rate_limit(self):
        """Test recording a webhook request with rate limit check."""
        with patch('django.core.cache.cache.incr') as mock_incr:
            mock_incr.return_value = 101  # Exceeds limit
            
            result = self.rate_limiter.record_webhook_request(
                self.endpoint,
                check_limit=True,
                max_requests=100
            )
            
            self.assertFalse(result['success'])
            self.assertEqual(result['current_count'], 101)
            self.assertTrue(result['is_rate_limited'])
    
    def test_get_rate_limit_statistics(self):
        """Test getting rate limit statistics."""
        # Create rate limit config
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            current_count=50,
            created_by=self.user
        )
        
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 75  # Current count is 75
            
            stats = self.rate_limiter.get_rate_limit_statistics(self.endpoint)
            
            self.assertEqual(stats['current_count'], 75)
            self.assertEqual(stats['max_requests'], 100)
            self.assertEqual(stats['remaining_requests'], 25)
            self.assertEqual(stats['utilization_percentage'], 75.0)
            self.assertEqual(stats['window_seconds'], 60)
    
    def test_get_rate_limit_statistics_no_config(self):
        """Test getting rate limit statistics without config."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 10  # Current count is 10
            
            stats = self.rate_limiter.get_rate_limit_statistics(self.endpoint)
            
            self.assertEqual(stats['current_count'], 10)
            self.assertEqual(stats['max_requests'], 100)  # Default
            self.assertEqual(stats['remaining_requests'], 90)
            self.assertEqual(stats['utilization_percentage'], 10.0)
            self.assertEqual(stats['window_seconds'], 60)  # Default
    
    def test_cleanup_expired_rate_limits(self):
        """Test cleanup of expired rate limits."""
        # Create expired rate limit
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            reset_at=timezone.now() - timezone.timedelta(hours=1),
            created_by=self.user
        )
        
        result = self.rate_limiter.cleanup_expired_rate_limits()
        
        self.assertEqual(result['cleaned_count'], 1)
        
        with self.assertRaises(WebhookRateLimit.DoesNotExist):
            WebhookRateLimit.objects.get(id=rate_limit.id)
    
    def test_cleanup_expired_rate_limits_active(self):
        """Test cleanup of expired rate limits with active limits."""
        # Create active rate limit
        rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            reset_at=timezone.now() + timezone.timedelta(hours=1),
            created_by=self.user
        )
        
        result = self.rate_limiter.cleanup_expired_rate_limits()
        
        self.assertEqual(result['cleaned_count'], 0)
        
        # Check that rate limit still exists
        WebhookRateLimit.objects.get(id=rate_limit.id)
    
    def test_get_rate_limit_for_multiple_endpoints(self):
        """Test rate limiting for multiple endpoints."""
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            rate_limit_per_min=50,
            created_by=self.user,
        )
        
        with patch('django.core.cache.cache.get') as mock_get:
            # Different counts for different endpoints
            def mock_get_side_effect(key, default=None):
                if 'endpoint-1' in key:
                    return 25
                elif 'endpoint-2' in key:
                    return 45
                return 0
            
            mock_get.side_effect = mock_get_side_effect
            
            # Check first endpoint
            result1 = self.rate_limiter.check_webhook_rate_limit(self.endpoint)
            self.assertFalse(result1['is_rate_limited'])
            self.assertEqual(result1['current_count'], 25)
            
            # Check second endpoint
            result2 = self.rate_limiter.check_webhook_rate_limit(endpoint2)
            self.assertFalse(result2['is_rate_limited'])
            self.assertEqual(result2['current_count'], 45)
    
    def test_rate_limit_with_sliding_window(self):
        """Test rate limiting with sliding window."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set, \
             patch('time.time') as mock_time:
            
            # Mock time to simulate sliding window
            mock_time.return_value = 1640995200  # Fixed timestamp
            
            mock_get.return_value = 50  # Current count is 50
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100,
                sliding_window=True
            )
            
            self.assertFalse(is_limited)
            
            # Check that cache key includes timestamp for sliding window
            cache_key = mock_set.call_args[0][0]
            self.assertIn('sliding', cache_key)
    
    def test_rate_limit_with_burst_capacity(self):
        """Test rate limiting with burst capacity."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = 80  # Current count is 80
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100,
                burst_capacity=20
            )
            
            self.assertFalse(is_limited)  # 80 + 20 burst = 100 (not exceeded)
    
    def test_rate_limit_with_burst_capacity_exceeded(self):
        """Test rate limiting with burst capacity exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 85  # Current count is 85
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100,
                burst_capacity=10
            )
            
            self.assertTrue(is_limited)  # 85 + 10 burst = 95 (still not exceeded, but close)
    
    def test_rate_limit_with_ip_based_limiting(self):
        """Test rate limiting with IP-based limiting."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 50  # Current count is 50
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100,
                ip_address='192.168.1.1',
                limit_by='ip'
            )
            
            self.assertFalse(is_limited)
            
            # Check that cache key includes IP
            cache_key = mock_get.call_args[0][0]
            self.assertIn('192.168.1.1', cache_key)
    
    def test_rate_limit_with_user_based_limiting(self):
        """Test rate limiting with user-based limiting."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 50  # Current count is 50
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100,
                user_id=self.user.id,
                limit_by='user'
            )
            
            self.assertFalse(is_limited)
            
            # Check that cache key includes user ID
            cache_key = mock_get.call_args[0][0]
            self.assertIn(str(self.user.id), cache_key)
    
    def test_rate_limit_performance(self):
        """Test rate limiting performance."""
        import time
        
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = 50  # Current count is 50
            
            start_time = time.time()
            
            # Check rate limit 1000 times
            for _ in range(1000):
                is_limited = self.rate_limiter.is_rate_limited(
                    endpoint=self.endpoint,
                    window_seconds=60,
                    max_requests=100
                )
                self.assertFalse(is_limited)
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 1 second)
            self.assertLess(end_time - start_time, 1.0)
            self.assertEqual(mock_get.call_count, 1000)
    
    def test_rate_limit_concurrent_safety(self):
        """Test rate limiting concurrent safety."""
        import threading
        
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = 50  # Current count is 50
            
            results = []
            
            def check_rate_limit():
                is_limited = self.rate_limiter.is_rate_limited(
                    endpoint=self.endpoint,
                    window_seconds=60,
                    max_requests=100
                )
                results.append(is_limited)
            
            # Create multiple threads
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=check_rate_limit)
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # All checks should succeed
            self.assertEqual(len(results), 10)
            self.assertTrue(all(not result for result in results))
    
    def test_rate_limit_with_redis_backend(self):
        """Test rate limiting with Redis backend."""
        with patch('django.core.cache.cache') as mock_cache:
            mock_redis = Mock()
            mock_cache.get.return_value = 50
            mock_cache.set.return_value = True
            mock_cache.incr.return_value = 51
            
            # Simulate Redis backend
            mock_redis.get.return_value = 50
            mock_redis.set.return_value = True
            mock_redis.incr.return_value = 51
            
            rate_limiter = RateLimiterService(backend='redis')
            
            with patch('django.core.cache.cache', mock_redis):
                is_limited = rate_limiter.is_rate_limited(
                    endpoint=self.endpoint,
                    window_seconds=60,
                    max_requests=100
                )
                
                self.assertFalse(is_limited)
                mock_redis.get.assert_called_once()
    
    def test_rate_limit_with_custom_key_prefix(self):
        """Test rate limiting with custom key prefix."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 50  # Current count is 50
            
            rate_limiter = RateLimiterService(key_prefix='custom:')
            
            is_limited = rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertFalse(is_limited)
            
            # Check that cache key includes custom prefix
            cache_key = mock_get.call_args[0][0]
            self.assertTrue(cache_key.startswith('custom:'))
    
    def test_rate_limit_with_custom_ttl(self):
        """Test rate limiting with custom TTL."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            
            mock_get.return_value = None  # Cache miss
            
            rate_limiter = RateLimiterService(default_ttl=120)
            
            is_limited = rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertFalse(is_limited)
            
            # Check that cache set uses custom TTL
            cache_args = mock_set.call_args
            self.assertEqual(cache_args[1]['timeout'], 120)
    
    def test_rate_limit_error_handling(self):
        """Test rate limiting error handling."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.side_effect = Exception('Cache error')
            
            # Should handle gracefully and return False (not rate limited)
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            
            self.assertFalse(is_limited)
    
    def test_rate_limit_with_different_time_windows(self):
        """Test rate limiting with different time windows."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 50  # Current count is 50
            
            # Test 1-minute window
            is_limited_1min = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100
            )
            self.assertFalse(is_limited_1min)
            
            # Test 5-minute window
            is_limited_5min = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=300,
                max_requests=500
            )
            self.assertFalse(is_limited_5min)
            
            # Test 1-hour window
            is_limited_1hour = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=3600,
                max_requests=6000
            )
            self.assertFalse(is_limited_1hour)
            
            # Check that different windows use different cache keys
            cache_keys = [call[0][0] for call in mock_get.call_args_list]
            self.assertEqual(len(set(cache_keys)), 3)  # All keys should be different
    
    def test_rate_limit_with_fractional_limits(self):
        """Test rate limiting with fractional limits."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 0  # Current count is 0
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=100.5  # Fractional limit
            )
            
            self.assertFalse(is_limited)
    
    def test_rate_limit_with_zero_limit(self):
        """Test rate limiting with zero limit."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 0  # Current count is 0
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=0  # Zero limit
            )
            
            self.assertTrue(is_limited)  # Should be immediately rate limited
    
    def test_rate_limit_with_negative_limit(self):
        """Test rate limiting with negative limit."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 0  # Current count is 0
            
            is_limited = self.rate_limiter.is_rate_limited(
                endpoint=self.endpoint,
                window_seconds=60,
                max_requests=-10  # Negative limit
            )
            
            self.assertTrue(is_limited)  # Should be immediately rate limited

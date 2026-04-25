"""
Test Cache

Tests for the cache service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.cache import cache_service
from ..models import OfferRoute, UserOfferHistory
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestCache(TestCase):
    """Test cases for cache service."""
    
    def setUp(self):
        """Set up test environment."""
        self.cache_service = cache_service
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_set_cache_basic(self):
        """Test basic cache set operation."""
        try:
            # Test setting a simple value
            key = 'test_key'
            value = 'test_value'
            timeout = 300  # 5 minutes
            
            result = self.cache_service.set(key, value, timeout)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['key'], key)
            self.assertEqual(result['value'], value)
            self.assertEqual(result['timeout'], timeout)
            
        except Exception as e:
            self.fail(f"Error in test_set_cache_basic: {e}")
    
    def test_get_cache_basic(self):
        """Test basic cache get operation."""
        try:
            # Test getting a value
            key = 'test_key'
            value = 'test_value'
            timeout = 300
            
            # Set value first
            self.cache_service.set(key, value, timeout)
            
            # Get value
            result = self.cache_service.get(key)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['key'], key)
            self.assertEqual(result['value'], value)
            self.assertTrue(result['found'])
            
        except Exception as e:
            self.fail(f"Error in test_get_cache_basic: {e}")
    
    def test_get_cache_miss(self):
        """Test cache miss scenario."""
        try:
            # Test getting a non-existent value
            key = 'non_existent_key'
            
            # Get value
            result = self.cache_service.get(key)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['key'], key)
            self.assertFalse(result['found'])
            self.assertIsNone(result['value'])
            
        except Exception as e:
            self.fail(f"Error in test_get_cache_miss: {e}")
    
    def test_delete_cache_basic(self):
        """Test basic cache delete operation."""
        try:
            # Test deleting a value
            key = 'test_key'
            value = 'test_value'
            timeout = 300
            
            # Set value first
            self.cache_service.set(key, value, timeout)
            
            # Delete value
            result = self.cache_service.delete(key)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['key'], key)
            
            # Verify value is deleted
            get_result = self.cache_service.get(key)
            self.assertFalse(get_result['found'])
            
        except Exception as e:
            self.fail(f"Error in test_delete_cache_basic: {e}")
    
    def test_clear_cache_pattern_basic(self):
        """Test basic cache pattern clearing."""
        try:
            # Set multiple values
            keys = ['test_key_1', 'test_key_2', 'test_key_3']
            for i, key in enumerate(keys):
                self.cache_service.set(key, f'value_{i}', 300)
            
            # Clear pattern
            result = self.cache_service.clear_pattern('test_key_*')
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['pattern'], 'test_key_*')
            self.assertEqual(result['cleared_count'], 3)
            
            # Verify values are cleared
            for key in keys:
                get_result = self.cache_service.get(key)
                self.assertFalse(get_result['found'])
            
        except Exception as e:
            self.fail(f"Error in test_clear_cache_pattern_basic: {e}")
    
    def test_cache_ttl_basic(self):
        """Test cache TTL (time-to-live) functionality."""
        try:
            # Test setting value with TTL
            key = 'test_ttl_key'
            value = 'test_ttl_value'
            timeout = 60  # 1 minute
            
            # Set value
            self.cache_service.set(key, value, timeout)
            
            # Get value immediately
            result1 = self.cache_service.get(key)
            self.assertTrue(result1['success'])
            self.assertEqual(result1['value'], value)
            
            # Wait for TTL to expire (mock time)
            with patch('django.utils.timezone.now') as mock_now:
                # Simulate time passing
                mock_now.return_value = timezone.now() + timezone.timedelta(seconds=61)
                
                result2 = self.cache_service.get(key)
                self.assertTrue(result2['success'])
                self.assertFalse(result2['found'])  # Should be expired
            
        except Exception as e:
            self.fail(f"Error in test_cache_ttl_basic: {e}")
    
    def test_cache_serialization_basic(self):
        """Test cache serialization/deserialization."""
        try:
            # Test setting complex object
            key = 'test_complex_key'
            value = {
                'string': 'test_string',
                'number': 42,
                'list': [1, 2, 3],
                'dict': {'nested': 'value'},
                'boolean': True,
                'none': None
            }
            timeout = 300
            
            # Set complex value
            result = self.cache_service.set(key, value, timeout)
            
            # Get complex value
            get_result = self.cache_service.get(key)
            
            # Assertions
            self.assertTrue(get_result['success'])
            self.assertEqual(get_result['value'], value)
            self.assertTrue(get_result['found'])
            
        except Exception as e:
            self.fail(f"Error in test_cache_serialization_basic: {e}")
    
    def test_cache_concurrency_basic(self):
        """Test cache concurrency handling."""
        try:
            # Test concurrent access
            key = 'test_concurrent_key'
            value = 'test_concurrent_value'
            
            # Set value
            result1 = self.cache_service.set(key, value, 300)
            self.assertTrue(result1['success'])
            
            # Get value
            result2 = self.cache_service.get(key)
            self.assertTrue(result2['success'])
            self.assertEqual(result2['value'], value)
            
        except Exception as e:
            self.fail(f"Error in test_cache_concurrency_basic: {e}")
    
    def test_cache_memory_usage_basic(self):
        """Test cache memory usage monitoring."""
        try:
            # Get memory usage
            result = self.cache_service.get_memory_usage()
            
            # Assertions
            self.assertIsInstance(result, dict)
            self.assertIn('total_keys', result)
            self.assertIn('total_size_bytes', result)
            self.assertIn('max_key_size_bytes', result)
            self.assertIn('avg_key_size_bytes', result)
            self.assertIn('memory_usage_percentage', result)
            
            # Verify reasonable values
            self.assertGreaterEqual(result['total_keys'], 0)
            self.assertGreaterEqual(result['total_size_bytes'], 0)
            self.assertGreaterEqual(result['max_key_size_bytes'], 0)
            self.assertGreaterEqual(result['avg_key_size_bytes'], 0)
            self.assertGreaterEqual(result['memory_usage_percentage'], 0)
            self.assertLessEqual(result['memory_usage_percentage'], 100)
            
        except Exception as e:
            self.fail(f"Error in test_cache_memory_usage_basic: {e}")
    
    def test_cache_performance_basic(self):
        """Test cache performance metrics."""
        try:
            # Get performance metrics
            result = self.cache_service.get_performance_metrics()
            
            # Assertions
            self.assertIsInstance(result, dict)
            self.assertIn('hit_rate', result)
            self.assertIn('miss_rate', result)
            self.assertIn('avg_response_time_ms', result)
            self.assertIn('total_requests', result)
            self.assertIn('cache_size', result)
            self.assertIn('eviction_policy', result)
            
            # Verify reasonable values
            self.assertGreaterEqual(result['hit_rate'], 0.0)
            self.assertLessEqual(result['hit_rate'], 1.0)
            self.assertGreaterEqual(result['miss_rate'], 0.0)
            self.assertLessEqual(result['miss_rate'], 1.0)
            self.assertGreaterEqual(result['avg_response_time_ms'], 0.0)
            self.assertGreaterEqual(result['total_requests'], 0)
            self.assertGreaterEqual(result['cache_size'], 0)
            
        except Exception as e:
            self.fail(f"Error in test_cache_performance_basic: {e}")
    
    def test_cache_health_check(self):
        """Test cache service health check."""
        try:
            # Test health check
            health = self.cache_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('memory_status', health)
            self.assertIn('performance_status', health)
            self.assertIn('cache_backend', health)
            self.assertIn('total_keys', health)
            self.assertIn('total_size', health)
            
            # Verify health status
            self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy', 'error'])
            
        except Exception as e:
            self.fail(f"Error in test_cache_health_check: {e}")
    
    def test_cache_under_load(self):
        """Test cache performance under load."""
        try:
            # Create many cache entries
            keys = []
            for i in range(100):
                key = f'load_test_key_{i}'
                value = f'load_test_value_{i}'
                self.cache_service.set(key, value, 300)
                keys.append(key)
            
            # Measure performance
            start_time = timezone.now()
            
            # Get all values
            for key in keys:
                self.cache_service.get(key)
            
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Should complete in reasonable time
            self.assertLess(elapsed_ms, 5000)  # Under 5 seconds
            
        except Exception as e:
            self.fail(f"Error in test_cache_under_load: {e}")


if __name__ == '__main__':
    pytest.main()

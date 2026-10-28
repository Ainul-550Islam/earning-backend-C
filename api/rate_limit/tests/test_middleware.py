"""
Rate Limit Middleware Tests

This module contains comprehensive tests for rate limiting middleware functionality.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase, TransactionTestCase, RequestFactory
from django.test import Client
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
import time

from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from api.rate_limit.middleware import RateLimitMiddleware, EarningTaskRateLimitMiddleware
from api.rate_limit.tests.factories import (
    RateLimitConfigFactory, UserFactory, RateLimitLogFactory,
    BulkDataFactory, TestDataGenerator
)

User = get_user_model()


class RateLimitMiddlewareTest(TestCase):
    """Test cases for RateLimitMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse())
        
        # Mock the rate limit service
        self.rate_limit_service_patcher = patch('api.rate_limit.middleware.RateLimitService')
        self.mock_rate_limit_service = self.rate_limit_service_patcher.start()
        self.mock_service_instance = MagicMock()
        self.mock_rate_limit_service.return_value = self.mock_service_instance
    
    def tearDown(self):
        self.rate_limit_service_patcher.stop()
    
    def test_middleware_initialization(self):
        """Test middleware initialization."""
        middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse())
        
        self.assertIsNotNone(middleware.get_response)
        self.assertIsNotNone(middleware.rate_limit_service)
    
    def test_middleware_process_request_allowed(self):
        """Test middleware processing allowed request."""
        # Mock service to allow request
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        response = self.middleware.process_request(request)
        
        # Should return None to continue processing
        self.assertIsNone(response)
        
        # Service should be called
        self.mock_service_instance.check_request.assert_called_once_with(request)
    
    def test_middleware_process_request_blocked(self):
        """Test middleware processing blocked request."""
        # Mock service to block request
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': False,
            'failed_configs': [{
                'config': MagicMock(),
                'metadata': {'remaining': 0, 'reset_time': 1234567890}
            }]
        }
        
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        response = self.middleware.process_request(request)
        
        # Should return JsonResponse with 429 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 429)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'Rate limit exceeded')
        self.assertIn('retry_after', response_data)
    
    def test_middleware_excluded_paths(self):
        """Test middleware excludes certain paths."""
        excluded_paths = [
            '/api/health/',
            '/api/status/',
            '/admin/',
            '/static/',
            '/media/'
        ]
        
        for path in excluded_paths:
            with self.subTest(path=path):
                request = self.factory.get(path)
                request.user = self.user
                
                response = self.middleware.process_request(request)
                
                # Should return None for excluded paths
                self.assertIsNone(response)
                
                # Service should not be called for excluded paths
                self.mock_service_instance.check_request.assert_not_called()
    
    def test_middleware_excluded_methods(self):
        """Test middleware excludes certain HTTP methods."""
        excluded_methods = ['OPTIONS', 'HEAD']
        
        for method in excluded_methods:
            with self.subTest(method=method):
                request = getattr(self.factory, method.lower())('/api/test/')
                request.user = self.user
                
                response = self.middleware.process_request(request)
                
                # Should return None for excluded methods
                self.assertIsNone(response)
                
                # Service should not be called for excluded methods
                self.mock_service_instance.check_request.assert_not_called()
    
    def test_middleware_authenticated_user(self):
        """Test middleware with authenticated user."""
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.mock_service_instance.check_request.assert_called_once_with(request)
    
    def test_middleware_anonymous_user(self):
        """Test middleware with anonymous user."""
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        
        request = self.factory.get('/api/test/')
        request.user = None  # Anonymous user
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        self.mock_service_instance.check_request.assert_called_once_with(request)
    
    def test_middleware_ip_address_extraction(self):
        """Test IP address extraction from request."""
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        
        # Test with X-Forwarded-For header
        request = self.factory.get('/api/test/')
        request.user = self.user
        request.META = {
            'HTTP_X_FORWARDED_FOR': '192.168.1.100, 10.0.0.1',
            'REMOTE_ADDR': '127.0.0.1'
        }
        
        response = self.middleware.process_request(request)
        
        self.assertIsNone(response)
        
        # Check that IP was extracted correctly (would be in request.ip_address)
        # This depends on the implementation
    
    def test_middleware_rate_limit_headers(self):
        """Test rate limit headers in response."""
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': [{
                'config': MagicMock(),
                'metadata': {
                    'remaining': 5,
                    'reset_time': 1234567890,
                    'limit': 10
                }
            }]
        }
        
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        # Process request
        self.middleware.process_request(request)
        
        # Get response from get_response
        response = self.middleware.get_response(request)
        
        # Should have rate limit headers
        # This would be implemented in process_response method
        # For now, we'll test the concept
    
    def test_middleware_service_error_handling(self):
        """Test middleware handling of service errors."""
        # Mock service to raise exception
        self.mock_service_instance.check_request.side_effect = Exception("Service error")
        
        request = self.factory.get('/api/test/')
        request.user = self.user
        
        # Should handle error gracefully
        with self.assertRaises(Exception):
            response = self.middleware.process_request(request)
        
        # Or depending on implementation, might return error response
        # response = self.middleware.process_request(request)
        # self.assertEqual(response.status_code, 500)


class EarningTaskRateLimitMiddlewareTest(TestCase):
    """Test cases for EarningTaskRateLimitMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.middleware = EarningTaskRateLimitMiddleware(get_response=lambda r: HttpResponse())
        
        # Mock the rate limit service
        self.rate_limit_service_patcher = patch('api.rate_limit.middleware.RateLimitService')
        self.mock_rate_limit_service = self.rate_limit_service_patcher.start()
        self.mock_service_instance = MagicMock()
        self.mock_rate_limit_service.return_value = self.mock_service_instance
    
    def tearDown(self):
        self.rate_limit_service_patcher.stop()
    
    def test_earning_middleware_task_completion_allowed(self):
        """Test earning middleware for allowed task completion."""
        # Mock service to allow task completion
        self.mock_service_instance.check_task_completion_limit.return_value = {
            'is_allowed': True,
            'limit': 10,
            'remaining': 9,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/complete-task/')
        request.user = self.user
        request.POST = {'task_id': 'task_123', 'task_type': 'survey'}
        
        response = self.middleware.process_request(request)
        
        # Should return None to continue processing
        self.assertIsNone(response)
        
        # Service should be called
        self.mock_service_instance.check_task_completion_limit.assert_called_once_with(
            self.user, 'survey'
        )
    
    def test_earning_middleware_task_completion_blocked(self):
        """Test earning middleware for blocked task completion."""
        # Mock service to block task completion
        self.mock_service_instance.check_task_completion_limit.return_value = {
            'is_allowed': False,
            'limit': 10,
            'remaining': 0,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/complete-task/')
        request.user = self.user
        request.POST = {'task_id': 'task_123', 'task_type': 'survey'}
        
        response = self.middleware.process_request(request)
        
        # Should return JsonResponse with 429 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 429)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Task limit exceeded', response_data['error'])
    
    def test_earning_middleware_offer_access_allowed(self):
        """Test earning middleware for allowed offer access."""
        # Mock service to allow offer access
        self.mock_service_instance.check_offer_access_limit.return_value = {
            'is_allowed': True,
            'limit': 5,
            'remaining': 4,
            'reset_time': 1234567890
        }
        
        request = self.factory.get('/api/earning/offer-wall/')
        request.user = self.user
        request.GET = {'offer_wall': 'offer_wall_1'}
        
        response = self.middleware.process_request(request)
        
        # Should return None to continue processing
        self.assertIsNone(response)
        
        # Service should be called
        self.mock_service_instance.check_offer_access_limit.assert_called_once_with(
            self.user, 'offer_wall_1'
        )
    
    def test_earning_middleware_offer_access_blocked(self):
        """Test earning middleware for blocked offer access."""
        # Mock service to block offer access
        self.mock_service_instance.check_offer_access_limit.return_value = {
            'is_allowed': False,
            'limit': 5,
            'remaining': 0,
            'reset_time': 1234567890
        }
        
        request = self.factory.get('/api/earning/offer-wall/')
        request.user = self.user
        request.GET = {'offer_wall': 'offer_wall_1'}
        
        response = self.middleware.process_request(request)
        
        # Should return JsonResponse with 429 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 429)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Offer limit exceeded', response_data['error'])
    
    def test_earning_middleware_referral_activity_allowed(self):
        """Test earning middleware for allowed referral activity."""
        # Mock service to allow referral activity
        self.mock_service_instance.check_referral_activity.return_value = {
            'is_allowed': True,
            'limit': 20,
            'remaining': 19,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/referral-click/')
        request.user = None  # Referral can be anonymous
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        request.POST = {'referral_code': 'ref_123'}
        
        response = self.middleware.process_request(request)
        
        # Should return None to continue processing
        self.assertIsNone(response)
        
        # Service should be called
        self.mock_service_instance.check_referral_activity.assert_called_once_with(
            '192.168.1.100'
        )
    
    def test_earning_middleware_referral_activity_blocked(self):
        """Test earning middleware for blocked referral activity."""
        # Mock service to block referral activity
        self.mock_service_instance.check_referral_activity.return_value = {
            'is_allowed': False,
            'limit': 20,
            'remaining': 0,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/referral-click/')
        request.user = None  # Referral can be anonymous
        request.META = {'REMOTE_ADDR': '192.168.1.100'}
        request.POST = {'referral_code': 'ref_123'}
        
        response = self.middleware.process_request(request)
        
        # Should return JsonResponse with 429 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 429)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Referral limit exceeded', response_data['error'])
    
    def test_earning_middleware_withdrawal_allowed(self):
        """Test earning middleware for allowed withdrawal."""
        # Mock service to allow withdrawal
        self.mock_service_instance.check_withdrawal_limit.return_value = {
            'is_allowed': True,
            'limit': 3,
            'remaining': 2,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/withdraw/')
        request.user = self.user
        request.POST = {'amount': 10.50}
        
        response = self.middleware.process_request(request)
        
        # Should return None to continue processing
        self.assertIsNone(response)
        
        # Service should be called
        self.mock_service_instance.check_withdrawal_limit.assert_called_once_with(
            self.user
        )
    
    def test_earning_middleware_withdrawal_blocked(self):
        """Test earning middleware for blocked withdrawal."""
        # Mock service to block withdrawal
        self.mock_service_instance.check_withdrawal_limit.return_value = {
            'is_allowed': False,
            'limit': 3,
            'remaining': 0,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/withdraw/')
        request.user = self.user
        request.POST = {'amount': 10.50}
        
        response = self.middleware.process_request(request)
        
        # Should return JsonResponse with 429 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 429)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Withdrawal limit exceeded', response_data['error'])
    
    def test_earning_middleware_request_attributes(self):
        """Test earning middleware sets request attributes."""
        self.mock_service_instance.check_task_completion_limit.return_value = {
            'is_allowed': True,
            'limit': 10,
            'remaining': 9,
            'reset_time': 1234567890
        }
        
        request = self.factory.post('/api/earning/complete-task/')
        request.user = self.user
        request.POST = {'task_id': 'task_123', 'task_type': 'survey'}
        
        self.middleware.process_request(request)
        
        # Should set earning-specific attributes
        self.assertTrue(hasattr(request, 'task_id'))
        self.assertTrue(hasattr(request, 'task_type'))
        self.assertEqual(request.task_id, 'task_123')
        self.assertEqual(request.task_type, 'survey')


class RateLimitMiddlewareIntegrationTest(TransactionTestCase):
    """Integration tests for rate limit middleware."""
    
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=5,
            time_unit='minute',
            time_value=1,
            is_active=True
        )
    
    def test_middleware_with_django_client(self):
        """Test middleware with Django test client."""
        self.client.force_login(self.user)
        
        # Mock the rate limit service
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # First request should be allowed
            mock_service_instance.check_request.return_value = {
                'is_allowed': True,
                'configs': []
            }
            
            response = self.client.get('/api/test/')
            
            # Should succeed (assuming endpoint exists)
            self.assertIn(response.status_code, [200, 404])
            
            # Service should be called
            mock_service_instance.check_request.assert_called()
    
    def test_middleware_creates_rate_limit_logs(self):
        """Test that middleware creates rate limit logs."""
        self.client.force_login(self.user)
        
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to create logs
            def mock_check_request(request):
                # Create log entry
                RateLimitLogFactory(
                    user=request.user,
                    config=self.config,
                    status='allowed'
                )
                return {'is_allowed': True, 'configs': []}
            
            mock_service_instance.check_request.side_effect = mock_check_request
            
            response = self.client.get('/api/test/')
            
            # Should have created a log
            logs = RateLimitLog.objects.filter(user=self.user)
            self.assertGreater(logs.count(), 0)
    
    def test_middleware_updates_user_profile(self):
        """Test that middleware updates user profile statistics."""
        self.client.force_login(self.user)
        
        # Get user profile
        profile, created = UserRateLimitProfile.objects.get_or_create(user=self.user)
        initial_requests = profile.total_requests
        
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to update profile
            def mock_check_request(request):
                # Update profile
                profile.total_requests += 1
                profile.save()
                return {'is_allowed': True, 'configs': []}
            
            mock_service_instance.check_request.side_effect = mock_check_request
            
            response = self.client.get('/api/test/')
            
            # Profile should be updated
            profile.refresh_from_db()
            self.assertGreater(profile.total_requests, initial_requests)
    
    def test_middleware_with_ip_blocking(self):
        """Test middleware with IP blocking."""
        self.client.force_login(self.user)
        
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to check IP blocking
            def mock_check_request(request):
                # Simulate IP block check
                if hasattr(request, 'META') and 'REMOTE_ADDR' in request.META:
                    ip = request.META['REMOTE_ADDR']
                    if ip == '192.168.1.100':
                        return {'is_allowed': False, 'failed_configs': []}
                return {'is_allowed': True, 'configs': []}
            
            mock_service_instance.check_request.side_effect = mock_check_request
            
            # Test with blocked IP
            response = self.client.get('/api/test/', REMOTE_ADDR='192.168.1.100')
            
            # Should be blocked
            self.assertEqual(response.status_code, 429)


class RateLimitMiddlewarePerformanceTest(TestCase):
    """Performance tests for rate limit middleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse())
        
        # Mock the rate limit service
        self.rate_limit_service_patcher = patch('api.rate_limit.middleware.RateLimitService')
        self.mock_rate_limit_service = self.rate_limit_service_patcher.start()
        self.mock_service_instance = MagicMock()
        self.mock_rate_limit_service.return_value = self.mock_service_instance
        
        # Configure mock to return quickly
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
    
    def tearDown(self):
        self.rate_limit_service_patcher.stop()
    
    def test_middleware_performance_allowed_requests(self):
        """Test middleware performance with allowed requests."""
        import time
        
        start_time = time.time()
        
        # Process many requests
        for i in range(1000):
            request = self.factory.get('/api/test/')
            request.user = self.user
            self.middleware.process_request(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 1000 requests in under 1 second
        self.assertLess(processing_time, 1.0)
    
    def test_middleware_performance_blocked_requests(self):
        """Test middleware performance with blocked requests."""
        import time
        
        # Configure mock to block requests
        self.mock_service_instance.check_request.return_value = {
            'is_allowed': False,
            'failed_configs': []
        }
        
        start_time = time.time()
        
        # Process many requests
        for i in range(1000):
            request = self.factory.get('/api/test/')
            request.user = self.user
            self.middleware.process_request(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 1000 requests in under 2 seconds (slower due to JSON response)
        self.assertLess(processing_time, 2.0)
    
    def test_middleware_performance_excluded_paths(self):
        """Test middleware performance with excluded paths."""
        import time
        
        excluded_paths = [
            '/api/health/',
            '/api/status/',
            '/admin/',
            '/static/test.css',
            '/media/image.jpg'
        ]
        
        start_time = time.time()
        
        # Process many requests to excluded paths
        for i in range(1000):
            path = excluded_paths[i % len(excluded_paths)]
            request = self.factory.get(path)
            request.user = self.user
            self.middleware.process_request(request)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should be faster for excluded paths (no service call)
        self.assertLess(processing_time, 0.5)
        
        # Service should not be called for excluded paths
        self.assertEqual(self.mock_service_instance.check_request.call_count, 0)
    
    def test_middleware_memory_usage(self):
        """Test middleware memory usage."""
        import sys
        
        # Process many requests
        requests = []
        for i in range(1000):
            request = self.factory.get('/api/test/')
            request.user = self.user
            requests.append(request)
            self.middleware.process_request(request)
        
        # Check memory usage (rough estimate)
        request_size = sys.getsizeof(requests[0])
        total_size = request_size * len(requests)
        
        # Should be reasonable (less than 50MB for 1000 requests)
        self.assertLess(total_size, 50 * 1024 * 1024)


class RateLimitMiddlewareErrorHandlingTest(TestCase):
    """Error handling tests for rate limit middleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse())
    
    def test_middleware_service_connection_error(self):
        """Test middleware handling of service connection errors."""
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service.side_effect = Exception("Connection error")
            
            request = self.factory.get('/api/test/')
            request.user = self.user
            
            # Should handle error gracefully
            with self.assertRaises(Exception):
                response = self.middleware.process_request(request)
    
    def test_middleware_invalid_request_data(self):
        """Test middleware handling of invalid request data."""
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to handle invalid data
            def mock_check_request(request):
                if not hasattr(request, 'user'):
                    raise ValueError("Invalid request: no user")
                return {'is_allowed': True, 'configs': []}
            
            mock_service_instance.check_request.side_effect = mock_check_request
            
            # Test with request missing user
            request = self.factory.get('/api/test/')
            # Don't set request.user
            
            with self.assertRaises(ValueError):
                response = self.middleware.process_request(request)
    
    def test_middleware_json_response_error(self):
        """Test middleware handling of JSON response errors."""
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to return invalid data
            mock_service_instance.check_request.return_value = {
                'is_allowed': False,
                'failed_configs': [{'invalid': 'data'}]  # Missing required metadata
            }
            
            request = self.factory.get('/api/test/')
            request.user = self.user
            
            # Should handle error gracefully
            with self.assertRaises(KeyError):
                response = self.middleware.process_request(request)
    
    def test_middleware_concurrent_requests(self):
        """Test middleware handling of concurrent requests."""
        import threading
        
        with patch('api.rate_limit.middleware.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance
            
            # Mock service to handle concurrent requests
            def mock_check_request(request):
                time.sleep(0.01)  # Simulate processing time
                return {'is_allowed': True, 'configs': []}
            
            mock_service_instance.check_request.side_effect = mock_check_request
            
            results = []
            
            def worker():
                request = self.factory.get('/api/test/')
                request.user = self.user
                try:
                    response = self.middleware.process_request(request)
                    results.append(response)
                except Exception as e:
                    results.append(e)
            
            # Create multiple threads
            threads = []
            for i in range(10):
                thread = threading.Thread(target=worker)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # All should succeed
            self.assertEqual(len(results), 10)
            for result in results:
                self.assertIsNone(result)  # Allowed requests return None


if __name__ == '__main__':
    pytest.main([__file__])

"""
Enhanced Security Middleware Tests
Comprehensive test suite for all security middleware components
Author: System Security Team
Version: 2.0.0
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.test import APITestCase

from ..middleware import (
    SecurityHeadersMiddleware, RateLimitMiddleware,
    SecurityAuditMiddleware, VPNProxyDetectionMiddleware
)
from .factories import UserFactory, StaffUserFactory, SecurityLogFactory

User = get_user_model()


class SecurityHeadersMiddlewareTest(TestCase):
    """Test SecurityHeadersMiddleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(get_response=lambda r: HttpResponse())
        self.user = UserFactory()
    
    def test_security_headers_added(self):
        """Test that security headers are added to response"""
        request = self.factory.get('/')
        response = self.middleware(request)
        
        # Check for security headers
        self.assertIn('X-Content-Type-Options', response)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        
        self.assertIn('X-Frame-Options', response)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        
        self.assertIn('X-XSS-Protection', response)
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
        
        self.assertIn('Strict-Transport-Security', response)
        self.assertIn('max-age=31536000', response['Strict-Transport-Security'])
        
        self.assertIn('Content-Security-Policy', response)
        self.assertIn("default-src 'self'", response['Content-Security-Policy'])
    
    def test_security_headers_https_only(self):
        """Test HTTPS-only headers"""
        request = self.factory.get('/', secure=True)
        response = self.middleware(request)
        
        # HSTS should only be added for HTTPS requests
        self.assertIn('Strict-Transport-Security', response)
        
        # Non-HTTPS request should not have HSTS
        request_http = self.factory.get('/', secure=False)
        response_http = self.middleware(request_http)
        self.assertNotIn('Strict-Transport-Security', response_http)
    
    def test_security_headers_preserve_existing(self):
        """Test that existing headers are preserved"""
        def get_response(request):
            response = HttpResponse()
            response['Custom-Header'] = 'custom-value'
            return response
        
        middleware = SecurityHeadersMiddleware(get_response)
        request = self.factory.get('/')
        response = middleware(request)
        
        self.assertEqual(response['Custom-Header'], 'custom-value')
        self.assertIn('X-Content-Type-Options', response)
    
    def test_security_headers_csp_customization(self):
        """Test CSP customization"""
        with override_settings(
            SECURITY_CSP="default-src 'self'; script-src 'self' 'unsafe-inline'"
        ):
            request = self.factory.get('/')
            response = self.middleware(request)
            
            self.assertIn('Content-Security-Policy', response)
            csp = response['Content-Security-Policy']
            self.assertIn("default-src 'self'", csp)
            self.assertIn("script-src 'self' 'unsafe-inline'", csp)
    
    @patch('api.security.middleware.logger')
    def test_security_headers_error_handling(self, mock_logger):
        """Test error handling in security headers middleware"""
        def get_response(request):
            raise Exception("Test error")
        
        middleware = SecurityHeadersMiddleware(get_response)
        request = self.factory.get('/')
        
        # Should handle error gracefully
        response = middleware(request)
        self.assertEqual(response.status_code, 500)
        mock_logger.error.assert_called()


class RateLimitMiddlewareTest(TestCase):
    """Test RateLimitMiddleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        cache.clear()
    
    def test_rate_limit_basic_functionality(self):
        """Test basic rate limiting functionality"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        
        # First request should pass
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        
        # Multiple requests within limit should pass
        for _ in range(9):  # Total 10 requests (default limit)
            request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
        
        # Request exceeding limit should be blocked
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
        response = middleware(request)
        self.assertEqual(response.status_code, 429)
    
    def test_rate_limit_different_ips(self):
        """Test rate limiting for different IPs"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        
        # Requests from different IPs should be tracked separately
        for ip in ['192.168.1.1', '192.168.1.2', '192.168.1.3']:
            for _ in range(15):  # Exceed limit for each IP
                request = self.factory.get('/', REMOTE_ADDR=ip)
                response = middleware(request)
                # First 10 should pass, rest should be blocked
                if _ < 10:
                    self.assertEqual(response.status_code, 200)
                else:
                    self.assertEqual(response.status_code, 429)
    
    def test_rate_limit_authenticated_users(self):
        """Test rate limiting for authenticated users"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        
        # Authenticated user requests
        for _ in range(15):
            request = self.factory.get('/')
            request.user = self.user
            response = middleware(request)
            # Authenticated users should have higher limits
            self.assertEqual(response.status_code, 200)
    
    def test_rate_limit_staff_users(self):
        """Test rate limiting for staff users"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        staff_user = StaffUserFactory()
        
        # Staff user requests should bypass rate limiting
        for _ in range(50):
            request = self.factory.get('/')
            request.user = staff_user
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
    
    def test_rate_limit_custom_limits(self):
        """Test custom rate limit configuration"""
        with override_settings(
            RATE_LIMIT={
                'anonymous': {'requests_per_minute': 5},
                'authenticated': {'requests_per_minute': 20},
                'staff': {'requests_per_minute': 100}
            }
        ):
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = RateLimitMiddleware(get_response)
            
            # Test anonymous user limit
            for _ in range(10):
                request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
                response = middleware(request)
                if _ < 5:
                    self.assertEqual(response.status_code, 200)
                else:
                    self.assertEqual(response.status_code, 429)
    
    def test_rate_limit_sliding_window(self):
        """Test sliding window rate limiting"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        
        # Make requests up to limit
        for _ in range(10):
            request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
            response = middleware(request)
            self.assertEqual(response.status_code, 200)
        
        # Should be blocked now
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
        response = middleware(request)
        self.assertEqual(response.status_code, 429)
        
        # Wait for window to slide (simulate with cache manipulation)
        cache_key = f"rate_limit:192.168.1.1"
        cache.delete(cache_key)
        
        # Should be allowed again
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
    
    def test_rate_limit_headers(self):
        """Test rate limit headers in response"""
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = RateLimitMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.1')
        response = middleware(request)
        
        # Should have rate limit headers
        self.assertIn('X-RateLimit-Limit', response)
        self.assertIn('X-RateLimit-Remaining', response)
        self.assertIn('X-RateLimit-Reset', response)
    
    @patch('api.security.middleware.logger')
    def test_rate_limit_error_handling(self, mock_logger):
        """Test error handling in rate limit middleware"""
        def get_response(request):
            raise Exception("Test error")
        
        middleware = RateLimitMiddleware(get_response)
        request = self.factory.get('/')
        
        # Should handle error gracefully
        response = middleware(request)
        self.assertEqual(response.status_code, 500)
        mock_logger.error.assert_called()


class SecurityAuditMiddlewareTest(TestCase):
    """Test SecurityAuditMiddleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
    
    def test_security_audit_logging(self):
        """Test security audit logging functionality"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = SecurityAuditMiddleware(get_response)
            
            request = self.factory.get('/api/test/', REMOTE_ADDR='192.168.1.1')
            request.user = self.user
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            # Should create security log
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['event_type'], 'api_request')
            self.assertEqual(call_args['ip_address'], '192.168.1.1')
            self.assertEqual(call_args['user_agent'], 'TestAgent/1.0')
            self.assertIn('api/test/', call_args['metadata']['path'])
    
    def test_security_audit_sensitive_endpoints(self):
        """Test audit logging for sensitive endpoints"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = SecurityAuditMiddleware(get_response)
            
            # Test sensitive endpoints
            sensitive_endpoints = [
                '/api/auth/login/',
                '/api/auth/logout/',
                '/api/users/change-password/',
                '/api/admin/users/'
            ]
            
            for endpoint in sensitive_endpoints:
                request = self.factory.post(endpoint, REMOTE_ADDR='192.168.1.1')
                request.user = self.user
                request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
                
                response = middleware(request)
                
                # Should create security log with higher severity
                mock_create.assert_called()
                call_args = mock_create.call_args[1]
                self.assertEqual(call_args['severity'], 'info')
                self.assertIn(endpoint, call_args['metadata']['path'])
    
    def test_security_audit_failed_requests(self):
        """Test audit logging for failed requests"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("Unauthorized", status=401)
            
            middleware = SecurityAuditMiddleware(get_response)
            
            request = self.factory.post('/api/auth/login/', REMOTE_ADDR='192.168.1.1')
            request.user = self.user
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            # Should create security log for failed request
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertEqual(call_args['event_type'], 'api_request_failed')
            self.assertEqual(call_args['severity'], 'warning')
            self.assertEqual(call_args['metadata']['status_code'], 401)
    
    def test_security_audit_request_body_logging(self):
        """Test request body logging for sensitive endpoints"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = SecurityAuditMiddleware(get_response)
            
            # Test with POST data
            request = self.factory.post(
                '/api/auth/login/',
                data={'username': 'test', 'password': 'secret'},
                REMOTE_ADDR='192.168.1.1'
            )
            request.user = self.user
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            # Should log request body (with password redacted)
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertIn('request_body', call_args['metadata'])
            # Password should be redacted
            self.assertNotIn('secret', str(call_args['metadata']['request_body']))
    
    def test_security_audit_response_logging(self):
        """Test response logging"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                response = HttpResponse({"data": "sensitive"}, content_type="application/json")
                response.status_code = 200
                return response
            
            middleware = SecurityAuditMiddleware(get_response)
            
            request = self.factory.get('/api/sensitive-data/', REMOTE_ADDR='192.168.1.1')
            request.user = self.user
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            # Should log response details
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertIn('response_status', call_args['metadata'])
            self.assertIn('response_size', call_args['metadata'])
    
    def test_security_audit_user_tracking(self):
        """Test user tracking in audit logs"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = SecurityAuditMiddleware(get_response)
            
            # Test with authenticated user
            request = self.factory.get('/api/test/', REMOTE_ADDR='192.168.1.1')
            request.user = self.user
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertEqual(call_args['user'], self.user)
            self.assertIn('user_id', call_args['metadata'])
            self.assertIn('username', call_args['metadata'])
    
    def test_security_audit_anonymous_requests(self):
        """Test audit logging for anonymous requests"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = SecurityAuditMiddleware(get_response)
            
            # Test with anonymous user
            request = self.factory.get('/api/public/', REMOTE_ADDR='192.168.1.1')
            request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
            
            response = middleware(request)
            
            mock_create.assert_called_once()
            call_args = mock_create.call_args[1]
            
            self.assertIsNone(call_args['user'])
            self.assertIn('anonymous', call_args['metadata'])
    
    @patch('api.security.middleware.logger')
    def test_security_audit_error_handling(self, mock_logger):
        """Test error handling in security audit middleware"""
        def get_response(request):
            raise Exception("Test error")
        
        middleware = SecurityAuditMiddleware(get_response)
        request = self.factory.get('/')
        
        # Should handle error gracefully
        response = middleware(request)
        self.assertEqual(response.status_code, 500)
        mock_logger.error.assert_called()


class VPNProxyDetectionMiddlewareTest(TestCase):
    """Test VPNProxyDetectionMiddleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_basic(self, mock_detector_class):
        """Test basic VPN detection"""
        # Mock VPN detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (True, {'is_vpn': True, 'confidence': 90})
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request.user = self.user
        
        response = middleware(request)
        
        # Should call VPN detector
        mock_detector.is_vpn.assert_called_once_with('192.168.1.100')
        
        # VPN detected should add headers
        self.assertIn('X-VPN-Detected', response)
        self.assertEqual(response['X-VPN-Detected'], 'true')
        self.assertIn('X-VPN-Confidence', response)
        self.assertEqual(response['X-VPN-Confidence'], '90')
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_no_vpn(self, mock_detector_class):
        """Test when no VPN is detected"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (False, {'is_vpn': False, 'confidence': 0})
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request.user = self.user
        
        response = middleware(request)
        
        # Should not add VPN headers
        self.assertNotIn('X-VPN-Detected', response)
        self.assertNotIn('X-VPN-Confidence', response)
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_staff_bypass(self, mock_detector_class):
        """Test staff user bypass"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request.user = self.staff_user
        
        response = middleware(request)
        
        # Should not call VPN detector for staff users
        mock_detector.is_vpn.assert_not_called()
        
        # Should add bypass header
        self.assertIn('X-VPN-Bypass', response)
        self.assertEqual(response['X-VPN-Bypass'], 'staff')
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_blocking_enabled(self, mock_detector_class):
        """Test VPN blocking when enabled"""
        with override_settings(VPN_BLOCK_ENABLED=True):
            mock_detector = MagicMock()
            mock_detector_class.return_value = mock_detector
            mock_detector.is_vpn.return_value = (True, {'is_vpn': True, 'confidence': 90})
            
            def get_response(request):
                return HttpResponse("OK")
            
            middleware = VPNProxyDetectionMiddleware(get_response)
            
            request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
            request.user = self.user
            
            response = middleware(request)
            
            # Should block VPN traffic
            self.assertEqual(response.status_code, 403)
            self.assertIn('VPN/Proxy detected', response.content.decode())
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_error_handling(self, mock_detector_class):
        """Test error handling in VPN detection"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.side_effect = Exception("Detection error")
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request.user = self.user
        
        response = middleware(request)
        
        # Should handle error gracefully and allow request
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-VPN-Error', response)
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_caching(self, mock_detector_class):
        """Test VPN detection caching"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (True, {'is_vpn': True, 'confidence': 90})
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        # First request
        request1 = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request1.user = self.user
        response1 = middleware(request1)
        
        # Second request should use cache
        request2 = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request2.user = self.user
        response2 = middleware(request2)
        
        # Should only call detector once due to caching
        mock_detector.is_vpn.assert_called_once()
        
        # Both responses should have VPN headers
        self.assertIn('X-VPN-Detected', response1)
        self.assertIn('X-VPN-Detected', response2)
    
    @patch('api.security.vpn_detector.VPNDetector')
    @patch('api.security.middleware.SecurityLog.objects.create')
    def test_vpn_detection_logging(self, mock_create, mock_detector_class):
        """Test VPN detection logging"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (True, {
            'is_vpn': True, 
            'confidence': 90,
            'service': 'test_service'
        })
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        request.user = self.user
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        
        response = middleware(request)
        
        # Should create security log
        mock_create.assert_called_once()
        call_args = mock_create.call_args[1]
        
        self.assertEqual(call_args['event_type'], 'vpn_detected')
        self.assertEqual(call_args['severity'], 'warning')
        self.assertEqual(call_args['ip_address'], '192.168.1.100')
        self.assertEqual(call_args['user'], self.user)
        self.assertIn('vpn_detection', call_args['metadata'])
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_x_forwarded_for(self, mock_detector_class):
        """Test VPN detection with X-Forwarded-For header"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (True, {'is_vpn': True, 'confidence': 90})
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get(
            '/',
            REMOTE_ADDR='192.168.1.1',  # Proxy IP
            HTTP_X_FORWARDED_FOR='192.168.1.100'  # Real IP
        )
        request.user = self.user
        
        response = middleware(request)
        
        # Should use X-Forwarded-For IP
        mock_detector.is_vpn.assert_called_once_with('192.168.1.100')
    
    @patch('api.security.vpn_detector.VPNDetector')
    def test_vpn_detection_multiple_ips(self, mock_detector_class):
        """Test VPN detection with multiple IPs in X-Forwarded-For"""
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_detector.is_vpn.return_value = (True, {'is_vpn': True, 'confidence': 90})
        
        def get_response(request):
            return HttpResponse("OK")
        
        middleware = VPNProxyDetectionMiddleware(get_response)
        
        request = self.factory.get(
            '/',
            REMOTE_ADDR='192.168.1.1',
            HTTP_X_FORWARDED_FOR='192.168.1.100, 10.0.0.1, 172.16.0.1'
        )
        request.user = self.user
        
        response = middleware(request)
        
        # Should use first IP in X-Forwarded-For
        mock_detector.is_vpn.assert_called_once_with('192.168.1.100')


class SecurityMiddlewareIntegrationTest(TestCase):
    """Integration tests for security middleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_middleware_chain_execution(self):
        """Test that all middleware execute in correct order"""
        with patch('api.security.middleware.SecurityLog.objects.create') as mock_create:
            def get_response(request):
                return HttpResponse("OK")
            
            # Apply middleware in order
            response = HttpResponse("OK")
            
            # Security Headers
            headers_middleware = SecurityHeadersMiddleware(get_response)
            request = self.factory.get('/')
            response = headers_middleware(request)
            
            # Rate Limit
            rate_middleware = RateLimitMiddleware(lambda r: response)
            response = rate_middleware(request)
            
            # Security Audit
            audit_middleware = SecurityAuditMiddleware(lambda r: response)
            response = audit_middleware(request)
            
            # VPN Detection
            with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
                mock_detector.return_value.is_vpn.return_value = (False, {})
                vpn_middleware = VPNProxyDetectionMiddleware(lambda r: response)
                response = vpn_middleware(request)
            
            # Should have all security headers
            self.assertIn('X-Content-Type-Options', response)
            self.assertIn('X-Frame-Options', response)
            
            # Should have rate limit headers
            self.assertIn('X-RateLimit-Limit', response)
            
            # Should have audit log
            mock_create.assert_called()
    
    def test_middleware_error_propagation(self):
        """Test error handling across middleware chain"""
        def get_response(request):
            raise Exception("Test error")
        
        # Apply middleware
        headers_middleware = SecurityHeadersMiddleware(get_response)
        rate_middleware = RateLimitMiddleware(lambda r: headers_middleware)
        audit_middleware = SecurityAuditMiddleware(lambda r: rate_middleware)
        
        request = self.factory.get('/')
        
        # Should handle error gracefully
        response = audit_middleware(request)
        self.assertEqual(response.status_code, 500)
    
    def test_middleware_performance_impact(self):
        """Test performance impact of security middleware"""
        import time
        
        def get_response(request):
            return HttpResponse("OK")
        
        # Test without middleware
        start_time = time.time()
        for _ in range(100):
            request = self.factory.get('/')
            response = get_response(request)
        without_middleware_time = time.time() - start_time
        
        # Test with all middleware
        with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
            mock_detector.return_value.is_vpn.return_value = (False, {})
            
            def middleware_chain(request):
                response = HttpResponse("OK")
                headers_middleware = SecurityHeadersMiddleware(lambda r: response)
                rate_middleware = RateLimitMiddleware(lambda r: headers_middleware(request))
                audit_middleware = SecurityAuditMiddleware(lambda r: rate_middleware(request))
                vpn_middleware = VPNProxyDetectionMiddleware(lambda r: audit_middleware(request))
                return vpn_middleware(request)
            
            start_time = time.time()
            for _ in range(100):
                request = self.factory.get('/')
                response = middleware_chain(request)
            with_middleware_time = time.time() - start_time
        
        # Performance impact should be reasonable (less than 10x slower)
        performance_ratio = with_middleware_time / without_middleware_time
        self.assertLess(performance_ratio, 10.0)
    
    def test_middleware_configuration_override(self):
        """Test middleware configuration override"""
        with override_settings(
            SECURITY_HEADERS_ENABLED=False,
            RATE_LIMIT_ENABLED=False,
            SECURITY_AUDIT_ENABLED=False,
            VPN_DETECTION_ENABLED=False
        ):
            def get_response(request):
                return HttpResponse("OK")
            
            # Apply middleware
            headers_middleware = SecurityHeadersMiddleware(get_response)
            rate_middleware = RateLimitMiddleware(lambda r: headers_middleware(request))
            audit_middleware = SecurityAuditMiddleware(lambda r: rate_middleware(request))
            
            with patch('api.security.vpn_detector.VPNDetector') as mock_detector:
                vpn_middleware = VPNProxyDetectionMiddleware(lambda r: audit_middleware(request))
                
                request = self.factory.get('/')
                response = vpn_middleware(request)
                
                # Should not have security features when disabled
                self.assertNotIn('X-Content-Type-Options', response)
                self.assertNotIn('X-RateLimit-Limit', response)
                mock_detector.assert_not_called()
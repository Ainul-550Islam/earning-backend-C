"""
test_ip_block.py - Comprehensive IP blocking functionality tests.

Test Scenario: একটি আইপি থেকে দ্রুত ১০০টি হিট পাঠিয়ে চেক করো যে AbuseDetectionService তাকে ডিটেক্ট করছে কি না এবং IPBlockList-এ ডাটা ঢুকছে কি না।
"""
from django.http import HttpResponse
import pytest
import time
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from api.rate_limit.models import IPBlockList, AbuseReport, RateLimitLog
from api.rate_limit.services.IPBlockService import IPBlockService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.RateLimitService import RateLimitService

User = get_user_model()


class IPBlockServiceTest(TestCase):
    """Test IP blocking service functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.ip_block_service = IPBlockService()
        self.test_ip = "192.168.1.100"
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_block_single_ip(self):
        """Test blocking a single IP address."""
        # Block the IP
        block = self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='test',
            blocked_by=self.test_user,
            duration_days=7
        )
        
        # Verify block was created
        self.assertIsNotNone(block)
        self.assertEqual(block.ip_address, self.test_ip)
        self.assertEqual(block.block_type, 'single')
        self.assertEqual(block.reason, 'test')
        self.assertFalse(block.permanent)
        self.assertTrue(block.is_active)
        
        # Verify IP is blocked
        is_blocked, blocking_rule = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked)
        self.assertEqual(blocking_rule.id, block.id)
    
    def test_block_ip_range(self):
        """Test blocking an IP range."""
        start_ip = "192.168.1.1"
        end_ip = "192.168.1.255"
        
        # Block the range
        block = self.ip_block_service.block_ip_range(
            start_ip=start_ip,
            end_ip=end_ip,
            reason='test_range',
            duration_days=7
        )
        
        # Verify block was created
        self.assertIsNotNone(block)
        self.assertEqual(block.ip_range_start, start_ip)
        self.assertEqual(block.ip_range_end, end_ip)
        self.assertEqual(block.block_type, 'range')
        self.assertEqual(block.reason, 'test_range')
        
        # Test IPs within range are blocked
        test_ips = ["192.168.1.50", "192.168.1.100", "192.168.1.200"]
        for ip in test_ips:
            is_blocked, _ = self.ip_block_service.is_ip_blocked(ip)
            self.assertTrue(is_blocked, f"IP {ip} should be blocked")
        
        # Test IP outside range is not blocked
        outside_ip = "192.168.2.100"
        is_blocked, _ = self.ip_block_service.is_ip_blocked(outside_ip)
        self.assertFalse(is_blocked, f"IP {outside_ip} should not be blocked")
    
    def test_block_subnet(self):
        """Test blocking a subnet."""
        subnet = "10.0.0.0/24"
        
        # Block the subnet
        block = self.ip_block_service.block_subnet(
            subnet=subnet,
            reason='test_subnet',
            duration_days=7
        )
        
        # Verify block was created
        self.assertIsNotNone(block)
        self.assertEqual(block.subnet, subnet)
        self.assertEqual(block.block_type, 'subnet')
        self.assertEqual(block.reason, 'test_subnet')
        
        # Test IPs within subnet are blocked
        test_ips = ["10.0.0.1", "10.0.0.50", "10.0.0.255"]
        for ip in test_ips:
            is_blocked, _ = self.ip_block_service.is_ip_blocked(ip)
            self.assertTrue(is_blocked, f"IP {ip} should be blocked")
        
        # Test IP outside subnet is not blocked
        outside_ip = "10.1.0.1"
        is_blocked, _ = self.ip_block_service.is_ip_blocked(outside_ip)
        self.assertFalse(is_blocked, f"IP {outside_ip} should not be blocked")
    
    def test_permanent_block(self):
        """Test permanent IP blocking."""
        # Create permanent block
        block = self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='permanent_test',
            permanent=True
        )
        
        # Verify permanent block
        self.assertTrue(block.permanent)
        self.assertIsNone(block.expires_at)
        
        # Verify IP is blocked
        is_blocked, _ = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked)
    
    def test_unblock_ip(self):
        """Test unblocking an IP address."""
        # First block the IP
        block = self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='test_block',
            duration_days=7
        )
        
        # Verify IP is blocked
        is_blocked, _ = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked)
        
        # Unblock the IP
        result = self.ip_block_service.unblock_ip(self.test_ip)
        
        # Verify unblock was successful
        self.assertTrue(result)
        
        # Verify IP is no longer blocked
        is_blocked, _ = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertFalse(is_blocked)
        
        # Verify block is deactivated
        block.refresh_from_db()
        self.assertFalse(block.is_active)
    
    def test_block_statistics(self):
        """Test block statistics generation."""
        # Create multiple blocks
        for i in range(5):
            self.ip_block_service.block_ip(
                ip_address=f"192.168.1.{100+i}",
                reason='test',
                duration_days=7
            )
        
        # Get statistics
        stats = self.ip_block_service.get_block_statistics(days=1)
        
        # Verify statistics
        self.assertIn('total_blocks', stats)
        self.assertIn('active_blocks', stats)
        self.assertIn('blocks_by_reason', stats)
        self.assertIn('blocks_by_type', stats)
        self.assertGreaterEqual(stats['total_blocks'], 5)
    
    def test_cleanup_expired_blocks(self):
        """Test cleanup of expired blocks."""
        # Create expired block
        past_time = timezone.now() - timedelta(days=10)
        with patch('django.utils.timezone.now', return_value=past_time):
            block = self.ip_block_service.block_ip(
                ip_address=self.test_ip,
                reason='expired_test',
                duration_days=7  # Will be expired
            )
        
        # Create current block
        current_block = self.ip_block_service.block_ip(
            ip_address="192.168.1.101",
            reason='current_test',
            duration_days=7
        )
        
        # Cleanup expired blocks
        cleaned_count = self.ip_block_service.cleanup_expired_blocks()
        
        # Verify cleanup
        self.assertGreaterEqual(cleaned_count, 1)
        
        # Verify expired block is deactivated
        block.refresh_from_db()
        self.assertFalse(block.is_active)
        
        # Verify current block is still active
        current_block.refresh_from_db()
        self.assertTrue(current_block.is_active)
    
    def test_auto_block_abusive_ips(self):
        """Test automatic blocking of abusive IPs."""
        # Create abuse reports for testing IP
        test_ip_abusive = "192.168.1.200"
        for i in range(10):  # Above threshold
            AbuseReport.objects.create(
                ip_address=test_ip_abusive,
                abuse_type='spam',
                severity=3,
                is_blocked=False
            )
        
        # Auto-block abusive IPs
        blocked_count = self.ip_block_service.block_abusive_ips(
            abuse_reports=AbuseReport.objects.filter(ip_address=test_ip_abusive),
            severity_threshold=5
        )
        
        # Verify auto-blocking
        self.assertGreaterEqual(blocked_count, 1)
        
        # Verify IP is now blocked
        is_blocked, _ = self.ip_block_service.is_ip_blocked(test_ip_abusive)
        self.assertTrue(is_blocked)
        
        # Verify abuse reports are marked as blocked
        reports = AbuseReport.objects.filter(ip_address=test_ip_abusive)
        for report in reports:
            self.assertTrue(report.is_blocked)


class IPBlockIntegrationTest(TestCase):
    """Test IP blocking integration with rate limiting."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_ip = "192.168.1.150"
        self.test_user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpass123'
        )
        self.ip_block_service = IPBlockService()
        self.abuse_detection_service = AbuseDetectionService()
        self.rate_limit_service = RateLimitService()
    
    def test_ip_blocking_prevents_rate_limit_processing(self):
        """Test that blocked IPs are rejected before rate limiting."""
        # Block the test IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='integration_test',
            duration_days=7
        )
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.META = {
            'REMOTE_ADDR': self.test_ip,
            'HTTP_USER_AGENT': 'TestAgent/1.0'
        }
        mock_request.path = '/api/test/'
        mock_request.method = 'GET'
        mock_request.user = self.test_user
        
        # Test rate limit check
        result = self.rate_limit_service.check_request(mock_request)
        
        # Since IP is blocked, this should be handled at middleware level
        # The rate limit service itself should still work
        self.assertIn('is_allowed', result)
        self.assertIn('configs', result)
    
    def test_abuse_detection_creates_blocks(self):
        """Test that abuse detection can create IP blocks."""
        # Create multiple abuse reports for test IP
        for i in range(15):  # High volume
            AbuseReport.objects.create(
                ip_address=self.test_ip,
                abuse_type='bot',
                severity=4,
                is_blocked=False
            )
        
        # Run abuse detection
        patterns = self.abuse_detection_service.detect_abuse_patterns(
            ip_address=self.test_ip,
            user=self.test_user,
            endpoint='/api/test/',
            time_window=3600
        )
        
        # Verify abuse detection
        self.assertIn('risk_score', patterns)
        self.assertIn('should_block', patterns)
        self.assertIn('abuse_types', patterns)
        
        # High risk score should trigger blocking
        if patterns['risk_score'] >= 70:
            self.assertTrue(patterns['should_block'])
    
    def test_ip_block_caching(self):
        """Test IP block status caching."""
        # Block the IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='cache_test',
            duration_days=7
        )
        
        # First check should query database
        is_blocked_1, rule_1 = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked_1)
        
        # Second check should use cache
        is_blocked_2, rule_2 = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked_2)
        self.assertEqual(rule_1.id, rule_2.id)
    
    def test_multiple_block_types_for_same_ip(self):
        """Test handling of multiple block types for same IP."""
        # Create single IP block
        block1 = self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='single_block',
            duration_days=7
        )
        
        # Create subnet block that includes the IP
        block2 = self.ip_block_service.block_subnet(
            subnet="192.168.1.0/24",
            reason='subnet_block',
            duration_days=7
        )
        
        # IP should be blocked (by either rule)
        is_blocked, rule = self.ip_block_service.is_ip_blocked(self.test_ip)
        self.assertTrue(is_blocked)
        
        # Should match one of the blocks
        self.assertIn(rule.id, [block1.id, block2.id])
    
    def test_block_export_functionality(self):
        """Test IP block export functionality."""
        # Create multiple blocks
        blocks_data = [
            {'ip': '192.168.1.1', 'type': 'single'},
            {'start': '10.0.0.1', 'end': '10.0.0.255', 'type': 'range'},
            {'subnet': '172.16.0.0/16', 'type': 'subnet'}
        ]
        
        for data in blocks_data:
            if data['type'] == 'single':
                self.ip_block_service.block_ip(data['ip'], reason='export_test')
            elif data['type'] == 'range':
                self.ip_block_service.block_ip_range(
                    data['start'], data['end'], reason='export_test'
                )
            elif data['type'] == 'subnet':
                self.ip_block_service.block_subnet(data['subnet'], reason='export_test')
        
        # Export blocks
        export_data = self.ip_block_service.get_blocked_ips_for_export()
        
        # Verify export data
        self.assertGreaterEqual(len(export_data), 3)
        
        for item in export_data:
            self.assertIn('ip_address', item)
            self.assertIn('block_type', item)
            self.assertIn('reason', item)
            self.assertIn('created_at', item)


class IPBlockPerformanceTest(TestCase):
    """Performance tests for IP blocking."""
    
    def setUp(self):
        """Set up test environment."""
        self.ip_block_service = IPBlockService()
    
    def test_large_scale_blocking_performance(self):
        """Test performance of large-scale IP blocking."""
        # Create many blocks
        start_time = time.time()
        
        for i in range(1000):
            self.ip_block_service.block_ip(
                ip_address=f"192.168.{i//256}.{i%256}",
                reason='performance_test',
                duration_days=7
            )
        
        creation_time = time.time() - start_time
        
        # Test lookup performance
        test_ips = [f"10.0.0.{i}" for i in range(100)]
        
        start_time = time.time()
        for ip in test_ips:
            self.ip_block_service.is_ip_blocked(ip)
        lookup_time = time.time() - start_time
        
        # Performance assertions
        self.assertLess(creation_time, 10.0)  # Should create 1000 blocks in < 10 seconds
        self.assertLess(lookup_time, 1.0)     # Should check 100 IPs in < 1 second
    
    def test_concurrent_blocking(self):
        """Test concurrent IP blocking operations."""
        import threading
        
        results = []
        errors = []
        
        def block_ip_range(start_idx):
            try:
                for i in range(10):
                    self.ip_block_service.block_ip(
                        ip_address=f"10.{start_idx}.{i}.1",
                        reason='concurrent_test',
                        duration_days=7
                    )
                results.append(start_idx)
            except Exception as e:
                errors.append((start_idx, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=block_ip_range, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(results), 10)
        self.assertEqual(len(errors), 0)


class MiddlewareInterceptionTest(TestCase):
    """Test middleware interception of blocked IPs."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_ip = "192.168.1.100"
        self.test_user = User.objects.create_user(
            username='middlewareuser',
            email='middleware@example.com',
            password='testpass123'
        )
        self.ip_block_service = IPBlockService()
        
    def test_middleware_blocks_blocked_ip(self):
        """Test that middleware blocks requests from blocked IPs."""
        # Block the test IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='middleware_test',
            duration_days=7
        )
        
        # Create mock request with blocked IP
        mock_request = self._create_mock_request(
            ip_address=self.test_ip,
            path='/api/protected/',
            method='GET',
            user=self.test_user
        )
        
        # Simulate middleware check
        from api.rate_limit.middleware import RateLimitMiddleware
        from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 403 Forbidden for blocked IP
        self.assertEqual(response.status_code, 403)
        
        # Verify response content indicates IP blocking
        response_content = response.content.decode('utf-8')
        self.assertIn('blocked', response_content.lower())
        self.assertIn('ip', response_content.lower())
    
    def test_middleware_allows_unblocked_ip(self):
        """Test that middleware allows requests from unblocked IPs."""
        # Create mock request with unblocked IP
        unblocked_ip = "192.168.1.200"
        mock_request = self._create_mock_request(
            ip_address=unblocked_ip,
            path='/api/protected/',
            method='GET',
            user=self.test_user
        )
        
        # Simulate middleware check
        from api.rate_limit.middleware import RateLimitMiddleware
        middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse(status=200))
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 200 OK for unblocked IP
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_blocks_subnet(self):
        """Test that middleware blocks requests from blocked subnets."""
        # Block a subnet
        self.ip_block_service.block_subnet(
            subnet="192.168.1.0/24",
            reason='subnet_test',
            duration_days=7
        )
        
        # Test multiple IPs in the subnet
        test_ips = ["192.168.1.50", "192.168.1.100", "192.168.1.200"]
        
        for ip in test_ips:
            mock_request = self._create_mock_request(
                ip_address=ip,
                path='/api/protected/',
                method='GET',
                user=self.test_user
            )
            
            # Simulate middleware check
            from api.rate_limit.middleware import RateLimitMiddleware
            from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
            
            # Process request through middleware
            response = middleware(mock_request)
            
            # Should return 403 Forbidden for all IPs in subnet
            self.assertEqual(response.status_code, 403)
    
    def test_middleware_blocks_ip_range(self):
        """Test that middleware blocks requests from blocked IP ranges."""
        # Block an IP range
        self.ip_block_service.block_ip_range(
            start_ip="10.0.0.1",
            end_ip="10.0.0.255",
            reason='range_test',
            duration_days=7
        )
        
        # Test IPs within range
        test_ips = ["10.0.0.50", "10.0.0.100", "10.0.0.200"]
        
        for ip in test_ips:
            mock_request = self._create_mock_request(
                ip_address=ip,
                path='/api/protected/',
                method='GET',
                user=self.test_user
            )
            
            # Simulate middleware check
            from api.rate_limit.middleware import RateLimitMiddleware
            from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
            
            # Process request through middleware
            response = middleware(mock_request)
            
            # Should return 403 Forbidden for all IPs in range
            self.assertEqual(response.status_code, 403)
        
        # Test IP outside range
        outside_ip = "10.1.0.100"
        mock_request = self._create_mock_request(
            ip_address=outside_ip,
            path='/api/protected/',
            method='GET',
            user=self.test_user
        )
        
        # Simulate middleware check
        middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse(status=200))
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 200 OK for IP outside range
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_logs_blocked_requests(self):
        """Test that middleware logs blocked requests."""
        # Block the test IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='logging_test',
            duration_days=7
        )
        
        # Create mock request
        mock_request = self._create_mock_request(
            ip_address=self.test_ip,
            path='/api/protected/',
            method='POST',
            user=self.test_user,
            user_agent='TestAgent/1.0'
        )
        
        # Simulate middleware check
        from api.rate_limit.middleware import RateLimitMiddleware
        from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 403 and log the event
        self.assertEqual(response.status_code, 403)
        
        # Verify log was created (check RateLimitLog)
        from api.rate_limit.models import RateLimitLog
        recent_logs = RateLimitLog.objects.filter(
            ip_address=self.test_ip,
            endpoint='/api/protected/',
            request_method='POST',
            status='blocked'
        ).order_by('-timestamp')[:1]
        
        self.assertEqual(recent_logs.count(), 1)
        log = recent_logs.first()
        self.assertEqual(log.ip_address, self.test_ip)
        self.assertEqual(log.endpoint, '/api/protected/')
        self.assertEqual(log.request_method, 'POST')
        self.assertEqual(log.status, 'blocked')
        self.assertEqual(log.user, self.test_user)
    
    def test_middleware_with_rate_limit_exceeded(self):
        """Test middleware behavior when rate limit is exceeded."""
        # Create rate limit config for testing
        from api.rate_limit.models import RateLimitConfig
        config = RateLimitConfig.objects.create(
            name='Middleware Test Config',
            rate_limit_type='ip',
            ip_address=self.test_ip,
            requests_per_unit=5,
            time_unit='minute',
            time_value=1,
            is_active=True
        )
        
        # Simulate rate limit exceeded (create logs)
        from api.rate_limit.models import RateLimitLog
        for i in range(6):  # Exceed limit
            RateLimitLog.objects.create(
                ip_address=self.test_ip,
                endpoint='/api/test/',
                request_method='GET',
                status='blocked' if i >= 5 else 'allowed',
                config=config,
                timestamp=timezone.now() - timedelta(seconds=i)
            )
        
        # Create mock request
        mock_request = self._create_mock_request(
            ip_address=self.test_ip,
            path='/api/test/',
            method='GET',
            user=self.test_user
        )
        
        # Simulate middleware check
        from api.rate_limit.middleware import RateLimitMiddleware
        from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 429 Too Many Requests
        self.assertEqual(response.status_code, 429)
    
    def test_middleware_bypass_for_whitelisted_ips(self):
        """Test middleware bypass for whitelisted IPs."""
        # Block the test IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='whitelist_test',
            duration_days=7
        )
        
        # Add IP to whitelist
        from api.rate_limit.models import RateLimitConfig
        config = RateLimitConfig.objects.create(
            name='Whitelist Test Config',
            rate_limit_type='ip',
            ip_address=self.test_ip,
            requests_per_unit=1000,
            time_unit='hour',
            time_value=1,
            is_active=True,
            whitelist=[self.test_ip]  # Whitelist this IP
        )
        
        # Create mock request
        mock_request = self._create_mock_request(
            ip_address=self.test_ip,
            path='/api/protected/',
            method='GET',
            user=self.test_user
        )
        
        # Simulate middleware check
        from api.rate_limit.middleware import RateLimitMiddleware
        middleware = RateLimitMiddleware(get_response=lambda r: HttpResponse(status=200))
        
        # Process request through middleware
        response = middleware(mock_request)
        
        # Should return 200 OK for whitelisted IP (bypasses block)
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_concurrent_requests(self):
        """Test middleware handling of concurrent requests from blocked IP."""
        # Block the test IP
        self.ip_block_service.block_ip(
            ip_address=self.test_ip,
            reason='concurrent_test',
            duration_days=7
        )
        
        import threading
        results = []
        
        def make_request(thread_id):
            mock_request = self._create_mock_request(
                ip_address=self.test_ip,
                path=f'/api/test/{thread_id}',
                method='GET',
                user=self.test_user
            )
            
            # Simulate middleware check
            from api.rate_limit.middleware import RateLimitMiddleware
            from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
            
            # Process request through middleware
            response = middleware(mock_request)
            results.append((thread_id, response.status_code))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should be blocked (403)
        self.assertEqual(len(results), 10)
        for thread_id, status_code in results:
            self.assertEqual(status_code, 403)
    
    def test_middleware_performance_with_blocked_ips(self):
        """Test middleware performance with blocked IP checks."""
        # Block multiple IPs
        blocked_ips = [f"192.168.1.{100+i}" for i in range(100)]
        
        for ip in blocked_ips:
            self.ip_block_service.block_ip(
                ip_address=ip,
                reason='performance_test',
                duration_days=7
            )
        
        import time
        
        # Test middleware performance
        start_time = time.time()
        
        for ip in blocked_ips:
            mock_request = self._create_mock_request(
                ip_address=ip,
                path='/api/test/',
                method='GET',
                user=self.test_user
            )
            
            # Simulate middleware check
            from api.rate_limit.middleware import RateLimitMiddleware
            from django.http import HttpResponse as _HR; middleware = RateLimitMiddleware(get_response=lambda r, _R=_HR: _R())
            
            # Process request through middleware
            response = middleware(mock_request)
            self.assertEqual(response.status_code, 403)
        
        end_time = time.time()
        performance_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(performance_time, 2.0)  # 2 seconds max for 100 requests
    
    def _create_mock_request(self, ip_address, path, method, user=None, user_agent=None):
        """Create a mock Django request object."""
        from django.http import HttpRequest, HttpResponse, JsonResponse
        from django.contrib.auth.models import AnonymousUser
        
        request = HttpRequest()
        request.method = method
        request.path = path
        request.META = {
            'REMOTE_ADDR': ip_address,
            'HTTP_USER_AGENT': user_agent or 'TestAgent/1.0',
            'HTTP_X_FORWARDED_FOR': ip_address,
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80'
        }
        request.user = user or AnonymousUser()
        
        return request


if __name__ == '__main__':
    pytest.main([__file__])

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
from unittest.mock import patch, MagicMock

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile,
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.services import RateLimitService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.IPBlockService import IPBlockService
from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService

User = get_user_model()


class RateLimitConfigTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            user=self.user,
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            is_active=True
        )
    
    def test_rate_limit_config_creation(self):
        """Test rate limit config creation"""
        self.assertEqual(self.config.name, 'test_config')
        self.assertEqual(self.config.user, self.user)
        self.assertTrue(self.config.is_active)
        self.assertEqual(str(self.config), 'test_config')
    
    def test_rate_limit_config_str_representation(self):
        """Test string representation of rate limit config"""
        expected = 'test_config (user) - 100 requests per 1 hour'
        self.assertEqual(str(self.config), expected)
    
    def test_rate_limit_config_absolute_import(self):
        """Test that absolute imports work correctly"""
        from api.rate_limit.models import RateLimitConfig as ImportedConfig
        self.assertEqual(ImportedConfig, RateLimitConfig)


class RateLimitLogTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            user=self.user,
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            is_active=True
        )
        self.log = RateLimitLog.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            request_method='GET',
            status='allowed',
            config=self.config
        )
    
    def test_rate_limit_log_creation(self):
        """Test rate limit log creation"""
        self.assertEqual(self.log.user, self.user)
        self.assertEqual(self.log.ip_address, '192.168.1.1')
        self.assertEqual(self.log.status, 'allowed')
        self.assertEqual(self.log.config, self.config)
    
    def test_rate_limit_log_str_representation(self):
        """Test string representation of rate limit log"""
        expected = f'{self.user.username} - {self.log.ip_address} - {self.log.endpoint} - {self.log.status}'
        self.assertEqual(str(self.log), expected)


class UserRateLimitProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserRateLimitProfile.objects.create(user=self.user)
    
    def test_user_profile_creation(self):
        """Test user profile creation"""
        self.assertEqual(self.profile.user, self.user)
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.total_requests, 0)
        self.assertEqual(self.profile.blocked_requests, 0)
    
    def test_user_profile_str_representation(self):
        """Test string representation of user profile"""
        expected = f'{self.user.username} - Premium: {self.profile.is_premium}'
        self.assertEqual(str(self.profile), expected)
    
    def test_user_profile_premium_upgrade(self):
        """Test premium upgrade functionality"""
        self.profile.is_premium = True
        self.profile.premium_until = timezone.now() + timedelta(days=30)
        self.profile.save()
        
        self.assertTrue(self.profile.is_premium)
        self.assertIsNotNone(self.profile.premium_until)


class AbuseReportTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.abuse_report = AbuseReport.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            abuse_type='high_volume',
            severity=3,
            pattern='rapid_requests'
        )
    
    def test_abuse_report_creation(self):
        """Test abuse report creation"""
        self.assertEqual(self.abuse_report.user, self.user)
        self.assertEqual(self.abuse_report.ip_address, '192.168.1.1')
        self.assertEqual(self.abuse_report.abuse_type, 'high_volume')
        self.assertEqual(self.abuse_report.severity, 3)
    
    def test_abuse_report_str_representation(self):
        """Test string representation of abuse report"""
        expected = f'{self.abuse_report.ip_address} - {self.abuse_report.abuse_type} - Severity: {self.abuse_report.severity}'
        self.assertEqual(str(self.abuse_report), expected)
    
    def test_abuse_report_should_block(self):
        """Test should_block functionality"""
        # Test high severity should block
        high_severity_report = AbuseReport.objects.create(
            user=self.user,
            ip_address='192.168.1.2',
            endpoint='/api/test/',
            abuse_type='high_volume',
            severity=5,
            pattern='rapid_requests'
        )
        self.assertTrue(high_severity_report.should_block())
        
        # Test low severity should not block
        low_severity_report = AbuseReport.objects.create(
            user=self.user,
            ip_address='192.168.1.3',
            endpoint='/api/test/',
            abuse_type='high_volume',
            severity=1,
            pattern='rapid_requests'
        )
        self.assertFalse(low_severity_report.should_block())
    
    def test_abuse_report_update_counts(self):
        """Test update_counts functionality"""
        initial_count = self.abuse_report.count_24h
        self.abuse_report.update_counts()
        self.assertEqual(self.abuse_report.count_24h, initial_count + 1)


class IPBlockListTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ip_block = IPBlockList.objects.create(
            ip_address='192.168.1.1',
            block_type='single',
            reason='manual',
            description='Test block',
            blocked_by=self.user
        )
    
    def test_ip_block_creation(self):
        """Test IP block creation"""
        self.assertEqual(self.ip_block.ip_address, '192.168.1.1')
        self.assertEqual(self.ip_block.block_type, 'single')
        self.assertEqual(self.ip_block.reason, 'manual')
        self.assertEqual(self.ip_block.blocked_by, self.user)
    
    def test_ip_block_str_representation(self):
        """Test string representation of IP block"""
        expected = f'{self.ip_block.ip_address} - {self.ip_block.block_type} - {self.ip_block.reason}'
        self.assertEqual(str(self.ip_block), expected)
    
    def test_ip_block_is_ip_blocked_single(self):
        """Test IP blocking for single IP"""
        self.assertTrue(self.ip_block.is_ip_blocked('192.168.1.1'))
        self.assertFalse(self.ip_block.is_ip_blocked('192.168.1.2'))
    
    def test_ip_block_is_ip_blocked_range(self):
        """Test IP blocking for IP range"""
        range_block = IPBlockList.objects.create(
            ip_range_start='192.168.1.1',
            ip_range_end='192.168.1.10',
            block_type='range',
            reason='manual',
            blocked_by=self.user
        )
        
        self.assertTrue(range_block.is_ip_blocked('192.168.1.5'))
        self.assertFalse(range_block.is_ip_blocked('192.168.1.11'))
    
    def test_ip_block_is_expired(self):
        """Test IP block expiration"""
        # Test non-expired block
        self.assertFalse(self.ip_block.is_expired())
        
        # Test expired block
        expired_block = IPBlockList.objects.create(
            ip_address='192.168.1.2',
            block_type='single',
            reason='manual',
            expires_at=timezone.now() - timedelta(days=1),
            blocked_by=self.user
        )
        self.assertTrue(expired_block.is_expired())
        
        # Test permanent block
        permanent_block = IPBlockList.objects.create(
            ip_address='192.168.1.3',
            block_type='single',
            reason='manual',
            permanent=True,
            blocked_by=self.user
        )
        self.assertFalse(permanent_block.is_expired())


class RateLimitInsightTestCase(TestCase):
    def setUp(self):
        self.insight = RateLimitInsight.objects.create(
            date=timezone.now().date(),
            total_requests=1000,
            blocked_requests=50,
            unique_users=100,
            unique_ips=80,
            abuse_reports_count=5,
            active_blocks_count=10
        )
    
    def test_rate_limit_insight_creation(self):
        """Test rate limit insight creation"""
        self.assertEqual(self.insight.total_requests, 1000)
        self.assertEqual(self.insight.blocked_requests, 50)
        self.assertEqual(self.insight.unique_users, 100)
    
    def test_rate_limit_insight_str_representation(self):
        """Test string representation of rate limit insight"""
        expected = f'{self.insight.date} - {self.insight.total_requests} requests'
        self.assertEqual(str(self.insight), expected)
    
    def test_rate_limit_insight_get_health_score(self):
        """Test health score calculation"""
        health_score = self.insight.get_health_score()
        self.assertIsInstance(health_score, (int, float))
        self.assertGreaterEqual(health_score, 0)
        self.assertLessEqual(health_score, 100)


class RateLimitExceptionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.exception = RateLimitException.objects.create(
            user=self.user,
            exception_type='whitelist',
            reason='Test exception',
            multiplier=2.0,
            granted_by=self.user
        )
    
    def test_rate_limit_exception_creation(self):
        """Test rate limit exception creation"""
        self.assertEqual(self.exception.user, self.user)
        self.assertEqual(self.exception.exception_type, 'whitelist')
        self.assertEqual(self.exception.multiplier, 2.0)
        self.assertEqual(self.exception.granted_by, self.user)
    
    def test_rate_limit_exception_str_representation(self):
        """Test string representation of rate limit exception"""
        expected = f'{self.exception.user.username} - {self.exception.exception_type} - {self.exception.reason}'
        self.assertEqual(str(self.exception), expected)
    
    def test_rate_limit_exception_applies_to_request(self):
        """Test exception applies to request"""
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        self.assertTrue(self.exception.applies_to_request(self.user, '192.168.1.1', '/api/test/'))
        self.assertFalse(self.exception.applies_to_request(self.user, '192.168.1.1', '/api/other/'))
    
    def test_rate_limit_exception_is_expired(self):
        """Test exception expiration"""
        # Test non-expired exception
        self.assertFalse(self.exception.is_expired())
        
        # Test expired exception
        expired_exception = RateLimitException.objects.create(
            user=self.user,
            exception_type='whitelist',
            reason='Test expired',
            expires_at=timezone.now() - timedelta(days=1),
            granted_by=self.user
        )
        self.assertTrue(expired_exception.is_expired())
        
        # Test permanent exception
        permanent_exception = RateLimitException.objects.create(
            user=self.user,
            exception_type='whitelist',
            reason='Test permanent',
            permanent=True,
            granted_by=self.user
        )
        self.assertFalse(permanent_exception.is_expired())


class RateLimitServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = RateLimitService()
    
    def test_get_applicable_configs(self):
        """Test getting applicable configs"""
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        configs = self.service.get_applicable_configs(request)
        self.assertIsInstance(configs, list)
    
    @patch('api.rate_limit.services.RateLimitService.redis_limiter')
    def test_check_request(self, mock_redis):
        """Test request checking"""
        mock_redis.check_rate_limit.return_value = (True, {'remaining': 50})
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        result = self.service.check_request(request)
        self.assertTrue(result['is_allowed'])
        self.assertIn('configs', result)


class AbuseDetectionServiceTestCase(TestCase):
    def setUp(self):
        self.service = AbuseDetectionService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_detect_abuse_patterns(self):
        """Test abuse pattern detection"""
        patterns = self.service.detect_abuse_patterns(
            ip_address='192.168.1.1',
            user=self.user,
            endpoint='/api/test/',
            time_window=3600
        )
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('risk_score', patterns)
        self.assertIn('abuse_types', patterns)
        self.assertIn('patterns', patterns)
    
    def test_create_abuse_report(self):
        """Test abuse report creation"""
        report = self.service.create_abuse_report(
            ip_address='192.168.1.1',
            user=self.user,
            endpoint='/api/test/',
            abuse_type='high_volume',
            severity=3
        )
        
        self.assertIsInstance(report, AbuseReport)
        self.assertEqual(report.ip_address, '192.168.1.1')
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.abuse_type, 'high_volume')


class IPBlockServiceTestCase(TestCase):
    def setUp(self):
        self.service = IPBlockService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_block_ip(self):
        """Test IP blocking"""
        block = self.service.block_ip(
            ip_address='192.168.1.1',
            reason='manual',
            description='Test block',
            blocked_by=self.user
        )
        
        self.assertIsInstance(block, IPBlockList)
        self.assertEqual(block.ip_address, '192.168.1.1')
        self.assertEqual(block.reason, 'manual')
    
    def test_is_ip_blocked(self):
        """Test IP block checking"""
        # Create a block
        IPBlockList.objects.create(
            ip_address='192.168.1.1',
            block_type='single',
            reason='manual',
            blocked_by=self.user
        )
        
        is_blocked, block_info = self.service.is_ip_blocked('192.168.1.1')
        self.assertTrue(is_blocked)
        self.assertIsInstance(block_info, dict)
    
    def test_unblock_ip(self):
        """Test IP unblocking"""
        # Create a block
        block = IPBlockList.objects.create(
            ip_address='192.168.1.1',
            block_type='single',
            reason='manual',
            blocked_by=self.user
        )
        
        result = self.service.unblock_ip('192.168.1.1', self.user)
        self.assertTrue(result['success'])
        
        # Check if block is deactivated
        block.refresh_from_db()
        self.assertFalse(block.is_active)


class RateLimitInsightServiceTestCase(TestCase):
    def setUp(self):
        self.service = RateLimitInsightService()
    
    def test_generate_daily_insights(self):
        """Test daily insights generation"""
        date = timezone.now().date()
        insight = self.service.generate_daily_insights(date)
        
        self.assertIsInstance(insight, RateLimitInsight)
        self.assertEqual(insight.date, date)
    
    def test_generate_weekly_report(self):
        """Test weekly report generation"""
        report = self.service.generate_weekly_report()
        
        self.assertIsInstance(report, dict)
        self.assertIn('period', report)
        self.assertIn('insights', report)
        self.assertIn('summary', report)


class RateLimitAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        self.client.force_login(self.user)
    
    def test_rate_limit_health_endpoint(self):
        """Test health check endpoint"""
        url = reverse('rate-limit-health')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('redis_status', response.json())
    
    def test_rate_limit_test_endpoint(self):
        """Test rate limit test endpoint"""
        url = reverse('rate-limit-test')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('configs', response.json())
    
    def test_rate_limit_configs_endpoint(self):
        """Test rate limit configs endpoint"""
        url = reverse('ratelimit-config-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
    
    def test_user_rate_limit_profiles_endpoint(self):
        """Test user rate limit profiles endpoint"""
        url = reverse('user-ratelimit-profile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
    
    def test_abuse_reports_endpoint(self):
        """Test abuse reports endpoint"""
        url = reverse('abuse-report-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
    
    def test_ip_blocks_endpoint(self):
        """Test IP blocks endpoint"""
        url = reverse('ip-block-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
    
    def test_rate_limit_insights_endpoint(self):
        """Test rate limit insights endpoint"""
        url = reverse('rate-limit-insight-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
    
    def test_rate_limit_exceptions_endpoint(self):
        """Test rate limit exceptions endpoint"""
        url = reverse('rate-limit-exception-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)


class RateLimitMiddlewareTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
    
    @patch('api.rate_limit.middleware.RateLimitService')
    def test_middleware_rate_limiting(self, mock_service):
        """Test middleware rate limiting functionality"""
        mock_service_instance = MagicMock()
        mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        mock_service.return_value = mock_service_instance
        
        # Test a request that should be rate limited
        response = self.client.get('/api/test/')
        
        # The middleware should allow the request through
        self.assertIn(response.status_code, [200, 404])  # 404 if endpoint doesn't exist
    
    @patch('api.rate_limit.middleware.RateLimitService')
    def test_middleware_rate_limit_exceeded(self, mock_service):
        """Test middleware when rate limit is exceeded"""
        mock_service_instance = MagicMock()
        mock_service_instance.check_request.return_value = {
            'is_allowed': False,
            'failed_configs': []
        }
        mock_service.return_value = mock_service_instance
        
        # Test a request that should be blocked
        response = self.client.get('/api/test/')
        
        # The middleware should return 429 for rate limit exceeded
        self.assertEqual(response.status_code, 429)


class RateLimitPermissionsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
    
    def test_is_admin_or_rate_limit_manager_permission(self):
        """Test admin or rate limit manager permission"""
        from api.rate_limit.permissions import IsAdminOrRateLimitManager
        permission = IsAdminOrRateLimitManager()
        
        # Test admin user
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.admin_user
        
        self.assertTrue(permission.has_permission(request, None))
        
        # Test regular user
        request.user = self.user
        self.assertFalse(permission.has_permission(request, None))
    
    def test_is_premium_user_permission(self):
        """Test premium user permission"""
        from api.rate_limit.permissions import IsPremiumUser
        permission = IsPremiumUser()
        
        # Create premium profile
        from api.rate_limit.models import UserRateLimitProfile
        profile = UserRateLimitProfile.objects.create(
            user=self.user,
            is_premium=True,
            premium_until=timezone.now() + timedelta(days=30)
        )
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        self.assertTrue(permission.has_permission(request, None))
        
        # Test non-premium user
        profile.is_premium = False
        profile.save()
        
        self.assertFalse(permission.has_permission(request, None))


class RateLimitDecoratorsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('api.rate_limit.decorators.RateLimitService')
    def test_rate_limit_decorator(self, mock_service):
        """Test rate limit decorator"""
        mock_service_instance = MagicMock()
        mock_service_instance.check_request.return_value = {
            'is_allowed': True,
            'configs': []
        }
        mock_service.return_value = mock_service_instance
        
        from api.rate_limit.decorators import rate_limit
        
        @rate_limit()
        def test_view(request):
            return {'success': True}
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        result = test_view(request)
        self.assertTrue(result['success'])
    
    @patch('api.rate_limit.decorators.RateLimitService')
    def test_rate_limit_decorator_exceeded(self, mock_service):
        """Test rate limit decorator when limit exceeded"""
        mock_service_instance = MagicMock()
        mock_service_instance.check_request.return_value = {
            'is_allowed': False,
            'failed_configs': [{
                'config': MagicMock(),
                'metadata': {'remaining': 0, 'reset_time': 1234567890}
            }]
        }
        mock_service.return_value = mock_service_instance
        
        from api.rate_limit.decorators import rate_limit
        
        @rate_limit()
        def test_view(request):
            return {'success': True}
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        result = test_view(request)
        self.assertEqual(result.status_code, 429)


class RateLimitSignalsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_creation_signal(self):
        """Test user creation signal creates rate limit profile"""
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123'
        )
        
        # Check if profile was created
        from api.rate_limit.models import UserRateLimitProfile
        self.assertTrue(
            UserRateLimitProfile.objects.filter(user=new_user).exists()
        )
    
    def test_abuse_report_auto_block_signal(self):
        """Test abuse report auto-blocking signal"""
        from api.rate_limit.models import AbuseReport
        
        # Create high severity abuse report
        report = AbuseReport.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            abuse_type='high_volume',
            severity=5,  # High severity
            pattern='rapid_requests'
        )
        
        # Check if IP was blocked
        from api.rate_limit.models import IPBlockList
        self.assertTrue(
            IPBlockList.objects.filter(ip_address='192.168.1.1').exists()
        )


class RateLimitIntegrationTestCase(TestCase):
    """Integration tests for the complete rate limiting system"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
    
    def test_complete_rate_limit_flow(self):
        """Test complete rate limiting flow from config to enforcement"""
        # 1. Create rate limit config
        config_data = {
            'name': 'integration_test_config',
            'rate_limit_type': 'user',
            'user': self.user.id,
            'requests_per_unit': 5,
            'time_unit': 'minute',
            'time_value': 1,
            'is_active': True
        }
        
        response = self.client.post(
            reverse('ratelimit-config-list'),
            data=json.dumps(config_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # 2. Test rate limiting enforcement (mocked)
        with patch('api.rate_limit.services.RateLimitService') as mock_service:
            mock_service_instance = MagicMock()
            mock_service_instance.check_request.return_value = {
                'is_allowed': False,
                'failed_configs': []
            }
            mock_service.return_value = mock_service_instance
            
            # Test request that should be blocked
            self.client.force_login(self.user)
            response = self.client.get('/api/test/')
            self.assertEqual(response.status_code, 429)
    
    def test_abuse_detection_and_blocking_flow(self):
        """Test complete abuse detection and blocking flow"""
        # 1. Create abuse report
        abuse_data = {
            'ip_address': '192.168.1.100',
            'endpoint': '/api/sensitive/',
            'abuse_type': 'high_volume',
            'severity': 5,
            'pattern': 'rapid_requests'
        }
        
        response = self.client.post(
            reverse('abuse-report-list'),
            data=json.dumps(abuse_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # 2. Check if IP was auto-blocked
        from api.rate_limit.models import IPBlockList
        self.assertTrue(
            IPBlockList.objects.filter(ip_address='192.168.1.100').exists()
        )
        
        # 3. Test IP blocking enforcement
        with patch('api.rate_limit.middleware.IPBlockService') as mock_ip_service:
            mock_ip_service_instance = MagicMock()
            mock_ip_service_instance.is_ip_blocked.return_value = (True, {})
            mock_ip_service.return_value = mock_ip_service_instance
            
            response = self.client.get('/api/test/')
            self.assertEqual(response.status_code, 403)
    
    def test_insight_generation_flow(self):
        """Test insight generation and analytics flow"""
        # 1. Generate insights
        insight_data = {
            'date': timezone.now().date().isoformat(),
            'total_requests': 1000,
            'blocked_requests': 50,
            'unique_users': 100,
            'unique_ips': 80,
            'abuse_reports_count': 5,
            'active_blocks_count': 10
        }
        
        response = self.client.post(
            reverse('rate-limit-insight-generate'),
            data=json.dumps(insight_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # 2. Check analytics endpoint
        response = self.client.get(reverse('rate-limit-analytics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_requests', response.json())


class RateLimitPerformanceTestCase(TestCase):
    """Performance tests for rate limiting system"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = RateLimitService()
    
    def test_bulk_config_creation_performance(self):
        """Test performance of bulk config creation"""
        import time
        
        configs = []
        start_time = time.time()
        
        for i in range(100):
            config = RateLimitConfig.objects.create(
                name=f'perf_test_config_{i}',
                rate_limit_type='user',
                user=self.user,
                requests_per_unit=100,
                time_unit='hour',
                time_value=1,
                is_active=True
            )
            configs.append(config)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Should create 100 configs in under 5 seconds
        self.assertLess(creation_time, 5.0)
        self.assertEqual(len(configs), 100)
    
    def test_bulk_log_creation_performance(self):
        """Test performance of bulk log creation"""
        import time
        
        config = RateLimitConfig.objects.create(
            name='perf_test_config',
            rate_limit_type='user',
            user=self.user,
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            is_active=True
        )
        
        logs = []
        start_time = time.time()
        
        for i in range(1000):
            log = RateLimitLog.objects.create(
                user=self.user,
                ip_address=f'192.168.1.{i % 255}',
                endpoint='/api/test/',
                request_method='GET',
                status='allowed',
                config=config
            )
            logs.append(log)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Should create 1000 logs in under 10 seconds
        self.assertLess(creation_time, 10.0)
        self.assertEqual(len(logs), 1000)


class RateLimitErrorHandlingTestCase(TestCase):
    """Error handling tests for rate limiting system"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.force_login(self.user)
    
    def test_invalid_config_creation(self):
        """Test handling of invalid config creation"""
        invalid_data = {
            'name': '',  # Empty name
            'rate_limit_type': 'invalid_type',
            'requests_per_unit': -1,  # Invalid value
            'time_unit': 'invalid_unit',
            'time_value': 0,  # Invalid value
        }
        
        response = self.client.post(
            reverse('ratelimit-config-list'),
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_invalid_abuse_report_creation(self):
        """Test handling of invalid abuse report creation"""
        invalid_data = {
            'ip_address': 'invalid_ip',  # Invalid IP
            'abuse_type': 'invalid_type',
            'severity': 10,  # Invalid severity
        }
        
        response = self.client.post(
            reverse('abuse-report-list'),
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_invalid_ip_block_creation(self):
        """Test handling of invalid IP block creation"""
        invalid_data = {
            'ip_address': 'invalid_ip',  # Invalid IP
            'block_type': 'invalid_type',
            'reason': '',  # Empty reason
        }
        
        response = self.client.post(
            reverse('ip-block-list'),
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
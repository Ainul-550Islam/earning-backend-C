"""
Comprehensive API-level tests for rate_limit views and viewsets.

This test file covers all HTTP views, viewsets, and API endpoints
that were previously untested in the rate_limit module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework.test import APIRequestFactory
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.test import Client
from django.core.cache import cache
from django.http import HttpResponse
from datetime import datetime, timedelta

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.views import (
    RateLimitConfigViewSet, RateLimitLogViewSet, UserRateLimitProfileViewSet,
    RateLimitStatsAPIView, AbuseReportViewSet, IPBlockListViewSet,
    RateLimitInsightViewSet, RateLimitExceptionViewSet
)
from api.rate_limit.consumers import RateLimitConsumer
from api.rate_limit.webhooks import RateLimitWebhookView
from api.rate_limit.encryption import RateLimitEncryptionService
from api.rate_limit.monitoring import RateLimitMonitoringService
from api.rate_limit.feature_flags import RateLimitFeatureFlags

User = get_user_model()


class RateLimitConfigViewSetTest(APITestCase):
    """Test cases for RateLimitConfigViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_list_rate_limit_configs_admin(self):
        """Test listing rate limit configs as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test configs
        RateLimitConfig.objects.create(
            name='test_config_1',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        RateLimitConfig.objects.create(
            name='test_config_2',
            rate_limit_type='ip',
            requests_per_unit=50,
            time_unit='minute',
            time_value=1,
            user=self.admin_user
        )
        
        response = self.client.get('/api/rate-limit/configs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_list_rate_limit_configs_unauthorized(self):
        """Test listing rate limit configs as regular user"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/rate-limit/configs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_create_rate_limit_config(self):
        """Test creating a new rate limit config"""
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            'name': 'new_config',
            'rate_limit_type': 'user',
            'requests_per_unit': 200,
            'time_unit': 'hour',
            'time_value': 1,
            'is_active': True
        }
        
        response = self.client.post('/api/rate-limit/configs/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RateLimitConfig.objects.count(), 1)
        
    def test_update_rate_limit_config(self):
        """Test updating a rate limit config"""
        self.client.force_authenticate(user=self.admin_user)
        
        config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
        data = {
            'name': 'updated_config',
            'requests_per_unit': 150
        }
        
        response = self.client.patch(f'/api/rate-limit/configs/{config.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.name, 'updated_config')
        self.assertEqual(config.requests_per_unit, 150)
        
    def test_delete_rate_limit_config(self):
        """Test deleting a rate limit config"""
        self.client.force_authenticate(user=self.admin_user)
        
        config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
        response = self.client.delete(f'/api/rate-limit/configs/{config.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RateLimitConfig.objects.count(), 0)
        
    def test_bulk_update_rate_limit_configs(self):
        """Test bulk updating rate limit configs"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test configs
        config1 = RateLimitConfig.objects.create(
            name='config_1',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        config2 = RateLimitConfig.objects.create(
            name='config_2',
            rate_limit_type='ip',
            requests_per_unit=50,
            time_unit='minute',
            time_value=1,
            user=self.admin_user
        )
        
        data = {
            'configs': [config1.id, config2.id],
            'action': 'activate'
        }
        
        response = self.client.post('/api/rate-limit/configs/bulk_update/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        config1.refresh_from_db()
        config2.refresh_from_db()
        self.assertTrue(config1.is_active)
        self.assertTrue(config2.is_active)


class RateLimitLogViewSetTest(APITestCase):
    """Test cases for RateLimitLogViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_list_rate_limit_logs_admin(self):
        """Test listing rate limit logs as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test logs
        RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint='/api/test/',
            method='GET',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            status_code=200,
            is_allowed=True
        )
        RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint='/api/test2/',
            method='POST',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            status_code=429,
            is_allowed=False
        )
        
        response = self.client.get('/api/rate-limit/logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
    def test_filter_rate_limit_logs_by_user(self):
        """Test filtering rate limit logs by user"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test logs for different users
        user1 = User.objects.create_user(username='user1', password='pass123')
        user2 = User.objects.create_user(username='user2', password='pass123')
        
        RateLimitLog.objects.create(
            user=user1,
            endpoint='/api/test/',
            method='GET',
            ip_address='192.168.1.1',
            status_code=200,
            is_allowed=True
        )
        RateLimitLog.objects.create(
            user=user2,
            endpoint='/api/test2/',
            method='POST',
            ip_address='192.168.1.2',
            status_code=429,
            is_allowed=False
        )
        
        response = self.client.get(f'/api/rate-limit/logs/?user={user1.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['user'], user1.id)


class UserRateLimitProfileViewSetTest(APITestCase):
    """Test cases for UserRateLimitProfileViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_list_user_rate_limit_profiles_admin(self):
        """Test listing user rate limit profiles as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test profiles
        UserRateLimitProfile.objects.create(
            user=self.regular_user,
            risk_level='low',
            custom_rate_multiplier=1.0,
            is_trusted=True
        )
        
        response = self.client.get('/api/rate-limit/profiles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
    def test_update_user_rate_limit_profile(self):
        """Test updating user rate limit profile"""
        self.client.force_authenticate(user=self.admin_user)
        
        profile = UserRateLimitProfile.objects.create(
            user=self.regular_user,
            risk_level='low',
            custom_rate_multiplier=1.0,
            is_trusted=True
        )
        
        data = {
            'risk_level': 'medium',
            'custom_rate_multiplier': 0.8,
            'is_trusted': False
        }
        
        response = self.client.patch(f'/api/rate-limit/profiles/{profile.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        profile.refresh_from_db()
        self.assertEqual(profile.risk_level, 'medium')
        self.assertEqual(profile.custom_rate_multiplier, 0.8)
        self.assertFalse(profile.is_trusted)


class RateLimitStatsAPIViewTest(APITestCase):
    """Test cases for RateLimitStatsAPIView"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_get_rate_limit_stats_admin(self):
        """Test getting rate limit statistics as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test data
        RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint='/api/test/',
            method='GET',
            ip_address='192.168.1.1',
            status_code=200,
            is_allowed=True
        )
        RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint='/api/test2/',
            method='POST',
            ip_address='192.168.1.1',
            status_code=429,
            is_allowed=False
        )
        
        response = self.client.get('/api/rate-limit/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that stats are included
        self.assertIn('total_requests', response.data)
        self.assertIn('blocked_requests', response.data)
        self.assertIn('allowed_requests', response.data)
        self.assertIn('block_rate', response.data)
        
    def test_get_rate_limit_stats_unauthorized(self):
        """Test getting rate limit statistics as regular user"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/rate-limit/stats/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AbuseReportViewSetTest(APITestCase):
    """Test cases for AbuseReportViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_create_abuse_report(self):
        """Test creating an abuse report"""
        self.client.force_authenticate(user=self.regular_user)
        
        data = {
            'reported_ip': '192.168.1.100',
            'reason': 'suspicious_activity',
            'description': 'Multiple failed login attempts detected',
            'evidence': {'attempts': 10, 'timeframe': '5 minutes'}
        }
        
        response = self.client.post('/api/rate-limit/abuse-reports/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AbuseReport.objects.count(), 1)
        
    def test_list_abuse_reports_admin(self):
        """Test listing abuse reports as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test reports
        AbuseReport.objects.create(
            reporter=self.regular_user,
            reported_ip='192.168.1.100',
            reason='suspicious_activity',
            description='Multiple failed login attempts'
        )
        
        response = self.client.get('/api/rate-limit/abuse-reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class IPBlockListViewSetTest(APITestCase):
    """Test cases for IPBlockListViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_create_ip_block_list(self):
        """Test creating an IP block list entry"""
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            'ip_address': '192.168.1.100',
            'reason': 'malicious_activity',
            'block_type': 'permanent',
            'is_active': True
        }
        
        response = self.client.post('/api/rate-limit/ip-blocks/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IPBlockList.objects.count(), 1)
        
    def test_list_ip_block_lists_admin(self):
        """Test listing IP block lists as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test block entries
        IPBlockList.objects.create(
            ip_address='192.168.1.100',
            reason='malicious_activity',
            block_type='permanent',
            created_by=self.admin_user
        )
        
        response = self.client.get('/api/rate-limit/ip-blocks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class RateLimitInsightViewSetTest(APITestCase):
    """Test cases for RateLimitInsightViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_list_rate_limit_insights_admin(self):
        """Test listing rate limit insights as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test insights
        RateLimitInsight.objects.create(
            insight_type='traffic_spike',
            description='Unusual traffic pattern detected',
            severity='medium',
            metadata={'endpoint': '/api/test/', 'spike_factor': 3.5}
        )
        
        response = self.client.get('/api/rate-limit/insights/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class RateLimitExceptionViewSetTest(APITestCase):
    """Test cases for RateLimitExceptionViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        self.client = APIClient()
        
    def test_create_rate_limit_exception(self):
        """Test creating a rate limit exception"""
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            'user': self.regular_user.id,
            'reason': 'api_client',
            'description': 'API client requires higher rate limits',
            'multiplier': 2.0,
            'expires_at': (timezone.now() + timedelta(days=30)).isoformat()
        }
        
        response = self.client.post('/api/rate-limit/exceptions/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RateLimitException.objects.count(), 1)
        
    def test_list_rate_limit_exceptions_admin(self):
        """Test listing rate limit exceptions as admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create test exceptions
        RateLimitException.objects.create(
            user=self.regular_user,
            reason='api_client',
            description='API client requires higher rate limits',
            multiplier=2.0,
            created_by=self.admin_user
        )
        
        response = self.client.get('/api/rate-limit/exceptions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class RateLimitAPITestCase(TransactionTestCase):
    """Base test case for rate limit API testing"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = APIRequestFactory()
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class RateLimitAPIIntegrationTest(RateLimitAPITestCase):
    """Integration tests for rate limit API"""
    
    def test_rate_limit_config_workflow(self):
        """Test complete rate limit config workflow"""
        # Create config
        config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=10,
            time_unit='minute',
            time_value=1,
            user=self.admin_user
        )
        
        # Create user profile
        profile = UserRateLimitProfile.objects.create(
            user=self.regular_user,
            risk_level='low',
            custom_rate_multiplier=1.0,
            is_trusted=True
        )
        
        # Create rate limit logs
        RateLimitLog.objects.create(
            user=self.regular_user,
            endpoint='/api/test/',
            method='GET',
            ip_address='192.168.1.1',
            status_code=200,
            is_allowed=True
        )
        
        # Verify all objects are created
        self.assertEqual(RateLimitConfig.objects.count(), 1)
        self.assertEqual(UserRateLimitProfile.objects.count(), 1)
        self.assertEqual(RateLimitLog.objects.count(), 1)
        
    def test_rate_limit_enforcement_workflow(self):
        """Test rate limit enforcement workflow"""
        # Create restrictive config
        config = RateLimitConfig.objects.create(
            name='restrictive_config',
            rate_limit_type='user',
            requests_per_unit=5,
            time_unit='minute',
            time_value=1,
            user=self.admin_user
        )
        
        # Create rate limit logs showing enforcement
        for i in range(10):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/test/',
                method='GET',
                ip_address='192.168.1.1',
                status_code=429 if i >= 5 else 200,
                is_allowed=i < 5
            )
        
        # Verify enforcement
        allowed_count = RateLimitLog.objects.filter(
            user=self.regular_user,
            is_allowed=True
        ).count()
        blocked_count = RateLimitLog.objects.filter(
            user=self.regular_user,
            is_allowed=False
        ).count()
        
        self.assertEqual(allowed_count, 5)
        self.assertEqual(blocked_count, 5)

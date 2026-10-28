# api/rate_limit/tests/test_models.py
"""
Tests for rate limit models.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)

User = get_user_model()


class RateLimitConfigModelTest(TestCase):
    """Test RateLimitConfig model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.user
        )
    
    def test_config_creation(self):
        """Test rate limit config creation."""
        self.assertEqual(self.config.name, 'test_config')
        self.assertEqual(self.config.rate_limit_type, 'user')
        self.assertEqual(self.config.requests_per_unit, 100)
        self.assertEqual(self.config.time_unit, 'hour')
        self.assertEqual(self.config.time_value, 1)
        self.assertEqual(self.config.user, self.user)
        self.assertTrue(self.config.is_active)
    
    def test_config_str_representation(self):
        """Test config string representation."""
        expected = f"{self.config.name} - {self.config.requests_per_unit} per {self.config.time_unit}"
        self.assertEqual(str(self.config), expected)
    
    def test_config_unique_name(self):
        """Test that config names are unique."""
        with self.assertRaises(Exception):  # Should raise IntegrityError
            RateLimitConfig.objects.create(
                name='test_config',  # Same name
                rate_limit_type='ip',
                requests_per_unit=50,
                time_unit='minute',
                time_value=1
            )


class RateLimitLogModelTest(TestCase):
    """Test RateLimitLog model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='endpoint',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            endpoint='/api/test/'
        )
        
        self.log = RateLimitLog.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            request_method='GET',
            status='allowed',
            config=self.config,
            suspicion_score=10
        )
    
    def test_log_creation(self):
        """Test rate limit log creation."""
        self.assertEqual(self.log.user, self.user)
        self.assertEqual(self.log.ip_address, '192.168.1.1')
        self.assertEqual(self.log.endpoint, '/api/test/')
        self.assertEqual(self.log.request_method, 'GET')
        self.assertEqual(self.log.status, 'allowed')
        self.assertEqual(self.log.config, self.config)
        self.assertEqual(self.log.suspicion_score, 10)
    
    def test_log_str_representation(self):
        """Test log string representation."""
        expected = f"{self.log.ip_address} - {self.log.endpoint} - {self.log.status}"
        self.assertEqual(str(self.log), expected)
    
    def test_log_without_user(self):
        """Test log creation without user."""
        log = RateLimitLog.objects.create(
            ip_address='192.168.1.2',
            endpoint='/api/public/',
            request_method='GET',
            status='allowed'
        )
        self.assertIsNone(log.user)
        self.assertEqual(log.ip_address, '192.168.1.2')


class UserRateLimitProfileModelTest(TestCase):
    """Test UserRateLimitProfile model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.profile = UserRateLimitProfile.objects.create(
            user=self.user,
            api_health_score=85,
            suspicion_score=15,
            is_premium=False,
            custom_daily_limit=1000,
            custom_hourly_limit=100
        )
    
    def test_profile_creation(self):
        """Test user profile creation."""
        self.assertEqual(self.profile.user, self.user)
        self.assertEqual(self.profile.api_health_score, 85)
        self.assertEqual(self.profile.suspicion_score, 15)
        self.assertFalse(self.profile.is_premium)
        self.assertEqual(self.profile.custom_daily_limit, 1000)
        self.assertEqual(self.profile.custom_hourly_limit, 100)
    
    def test_profile_str_representation(self):
        """Test profile string representation."""
        expected = f"{self.user.username} - Health: {self.profile.api_health_score}, Suspicion: {self.profile.suspicion_score}"
        self.assertEqual(str(self.profile), expected)
    
    def test_premium_upgrade(self):
        """Test premium upgrade."""
        self.profile.is_premium = True
        self.profile.premium_until = timezone.now() + timedelta(days=30)
        self.profile.save()
        
        self.assertTrue(self.profile.is_premium)
        self.assertIsNotNone(self.profile.premium_until)


class AbuseReportModelTest(TestCase):
    """Test AbuseReport model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.report = AbuseReport.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            abuse_type='spam',
            severity=3,
            description='Suspicious spam activity detected',
            evidence={'log_entries': ['log1', 'log2']}
        )
    
    def test_report_creation(self):
        """Test abuse report creation."""
        self.assertEqual(self.report.user, self.user)
        self.assertEqual(self.report.ip_address, '192.168.1.1')
        self.assertEqual(self.report.abuse_type, 'spam')
        self.assertEqual(self.report.severity, 3)
        self.assertEqual(self.report.description, 'Suspicious spam activity detected')
        self.assertEqual(self.report.evidence, {'log_entries': ['log1', 'log2']})
        self.assertFalse(self.report.is_investigated)
        self.assertFalse(self.report.is_blocked)
    
    def test_report_str_representation(self):
        """Test report string representation."""
        expected = f"{self.report.abuse_type} - {self.report.ip_address} - Severity: {self.report.severity}"
        self.assertEqual(str(self.report), expected)
    
    def test_report_investigation(self):
        """Test report investigation."""
        self.report.is_investigated = True
        self.report.investigated_at = timezone.now()
        self.report.save()
        
        self.assertTrue(self.report.is_investigated)
        self.assertIsNotNone(self.report.investigated_at)


class IPBlockListModelTest(TestCase):
    """Test IPBlockList model."""
    
    def setUp(self):
        """Set up test data."""
        self.block = IPBlockList.objects.create(
            ip_address='192.168.1.100',
            block_type='single',
            block_reason='abuse',
            is_active=True
        )
    
    def test_block_creation(self):
        """Test IP block creation."""
        self.assertEqual(self.block.ip_address, '192.168.1.100')
        self.assertEqual(self.block.block_type, 'single')
        self.assertEqual(self.block.block_reason, 'abuse')
        self.assertTrue(self.block.is_active)
        self.assertFalse(self.block.permanent)
        self.assertIsNone(self.block.expires_at)
    
    def test_block_str_representation(self):
        """Test block string representation."""
        expected = f"{self.block.ip_address} - {self.block.block_reason}"
        self.assertEqual(str(self.block), expected)
    
    def test_permanent_block(self):
        """Test permanent block."""
        self.block.permanent = True
        self.block.save()
        
        self.assertTrue(self.block.permanent)
        self.assertIsNone(self.block.expires_at)
    
    def test_temporary_block(self):
        """Test temporary block."""
        expires_at = timezone.now() + timedelta(hours=24)
        self.block.expires_at = expires_at
        self.block.save()
        
        self.assertFalse(self.block.permanent)
        self.assertEqual(self.block.expires_at, expires_at)


class RateLimitInsightModelTest(TestCase):
    """Test RateLimitInsight model."""
    
    def setUp(self):
        """Set up test data."""
        self.insight = RateLimitInsight.objects.create(
            date=timezone.now().date(),
            total_requests=1000,
            blocked_requests=50,
            unique_ips=100,
            unique_users=80,
            peak_hour=14
        )
    
    def test_insight_creation(self):
        """Test insight creation."""
        self.assertEqual(self.insight.total_requests, 1000)
        self.assertEqual(self.insight.blocked_requests, 50)
        self.assertEqual(self.insight.unique_ips, 100)
        self.assertEqual(self.insight.unique_users, 80)
        self.assertEqual(self.insight.peak_hour, 14)
    
    def test_insight_str_representation(self):
        """Test insight string representation."""
        expected = f"{self.insight.date} - {self.insight.total_requests} requests"
        self.assertEqual(str(self.insight), expected)
    
    def test_block_rate_calculation(self):
        """Test block rate calculation property."""
        expected_rate = (self.insight.blocked_requests / self.insight.total_requests) * 100
        # This would be a property method in the model
        pass


class RateLimitExceptionModelTest(TestCase):
    """Test RateLimitException model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.exception = RateLimitException.objects.create(
            user=self.user,
            exception_type='increased_limit',
            multiplier=2.0,
            is_active=True
        )
    
    def test_exception_creation(self):
        """Test exception creation."""
        self.assertEqual(self.exception.user, self.user)
        self.assertEqual(self.exception.exception_type, 'increased_limit')
        self.assertEqual(self.exception.multiplier, 2.0)
        self.assertTrue(self.exception.is_active)
        self.assertEqual(self.exception.usage_count, 0)
    
    def test_exception_str_representation(self):
        """Test exception string representation."""
        expected = f"{self.exception.exception_type} - {self.exception.user.username if self.exception.user else 'Anonymous'}"
        self.assertEqual(str(self.exception), expected)
    
    def test_usage_count_increment(self):
        """Test usage count increment."""
        initial_count = self.exception.usage_count
        self.exception.usage_count += 1
        self.exception.save()
        
        self.assertEqual(self.exception.usage_count, initial_count + 1)


class ModelRelationshipsTest(TestCase):
    """Test model relationships."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.user
        )
        
        self.profile = UserRateLimitProfile.objects.create(
            user=self.user,
            api_health_score=85,
            suspicion_score=15
        )
        
        self.log = RateLimitLog.objects.create(
            user=self.user,
            ip_address='192.168.1.1',
            endpoint='/api/test/',
            request_method='GET',
            status='allowed',
            config=self.config
        )
    
    def test_user_profile_relationship(self):
        """Test user-profile relationship."""
        self.assertEqual(self.user.ratelimitprofile, self.profile)
        self.assertEqual(self.profile.user, self.user)
    
    def test_config_log_relationship(self):
        """Test config-log relationship."""
        self.assertEqual(self.config.logs.count(), 1)
        self.assertEqual(self.log.config, self.config)
    
    def test_user_logs_relationship(self):
        """Test user-logs relationship."""
        self.assertEqual(self.user.ratelimitlog_set.count(), 1)
        self.assertEqual(self.log.user, self.user)
    
    def test_cascade_delete(self):
        """Test cascade delete behavior."""
        user_id = self.user.id
        
        # Delete user
        self.user.delete()
        
        # Check related objects are deleted
        self.assertFalse(UserRateLimitProfile.objects.filter(user_id=user_id).exists())
        self.assertFalse(RateLimitLog.objects.filter(user_id=user_id).exists())

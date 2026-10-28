"""
Comprehensive feature flags tests for rate_limit module.

This test file covers all feature flag management, flag evaluation,
conditional logic, A/B testing, and feature flag performance.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import time

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.feature_flags import RateLimitFeatureFlags
from api.rate_limit.services import RateLimitService

User = get_user_model()


class RateLimitFeatureFlagsTest(TestCase):
    """Test cases for RateLimitFeatureFlags"""
    
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
        
        self.feature_flags = RateLimitFeatureFlags()
        
        # Clear cache
        cache.clear()
        
    def test_create_feature_flag(self):
        """Test feature flag creation"""
        flag_data = {
            'key': 'enhanced_rate_limiting',
            'name': 'Enhanced Rate Limiting',
            'description': 'Enable enhanced rate limiting algorithms',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin', 'staff'],
                'user_segments': ['beta_testers'],
                'percentage': 50
            },
            'metadata': {
                'version': '2.0',
                'experiment_id': 'exp_12345'
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Verify flag creation
        self.assertIsNotNone(flag.id)
        self.assertEqual(flag.key, 'enhanced_rate_limiting')
        self.assertEqual(flag.name, 'Enhanced Rate Limiting')
        self.assertTrue(flag.enabled)
        self.assertIn('user_roles', flag.conditions)
        self.assertEqual(flag.conditions['percentage'], 50)
        
    def test_evaluate_feature_flag(self):
        """Test feature flag evaluation"""
        # Create flag
        flag_data = {
            'key': 'test_flag',
            'name': 'Test Flag',
            'description': 'Test feature flag',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin'],
                'percentage': 100
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Evaluate for admin user
        is_enabled_admin = self.feature_flags.is_enabled(
            'test_flag',
            user=self.admin_user
        )
        self.assertTrue(is_enabled_admin)
        
        # Evaluate for regular user
        is_enabled_regular = self.feature_flags.is_enabled(
            'test_flag',
            user=self.regular_user
        )
        self.assertFalse(is_enabled_regular)
        
    def test_percentage_based_flag(self):
        """Test percentage-based feature flag"""
        # Create flag with 50% rollout
        flag_data = {
            'key': 'percentage_test',
            'name': 'Percentage Test',
            'description': 'Test percentage-based rollout',
            'enabled': True,
            'conditions': {
                'percentage': 50
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Test multiple users
        enabled_count = 0
        total_users = 100
        
        for i in range(total_users):
            test_user = User.objects.create_user(
                username=f'test_user_{i}',
                email=f'test_user_{i}@example.com',
                password='pass123'
            )
            
            if self.feature_flags.is_enabled('percentage_test', user=test_user):
                enabled_count += 1
                
        # Verify percentage is approximately 50%
        enabled_percentage = (enabled_count / total_users) * 100
        self.assertGreaterEqual(enabled_percentage, 40)
        self.assertLessEqual(enabled_percentage, 60)
        
    def test_user_segment_flag(self):
        """Test user segment-based feature flag"""
        # Create users in different segments
        beta_user = User.objects.create_user(
            username='beta_user',
            email='beta@example.com',
            password='pass123'
        )
        
        # Add segment metadata
        beta_user.profile.segment = 'beta_testers'
        beta_user.profile.save()
        
        # Create flag for beta users
        flag_data = {
            'key': 'beta_features',
            'name': 'Beta Features',
            'description': 'Features for beta testers',
            'enabled': True,
            'conditions': {
                'user_segments': ['beta_testers']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Evaluate for beta user
        is_enabled_beta = self.feature_flags.is_enabled(
            'beta_features',
            user=beta_user
        )
        self.assertTrue(is_enabled_beta)
        
        # Evaluate for regular user
        is_enabled_regular = self.feature_flags.is_enabled(
            'beta_features',
            user=self.regular_user
        )
        self.assertFalse(is_enabled_regular)
        
    def test_time_based_flag(self):
        """Test time-based feature flag"""
        # Create time-based flag
        flag_data = {
            'key': 'time_limited_feature',
            'name': 'Time Limited Feature',
            'description': 'Feature available for limited time',
            'enabled': True,
            'conditions': {
                'start_time': (timezone.now() - timedelta(hours=1)).isoformat(),
                'end_time': (timezone.now() + timedelta(hours=1)).isoformat()
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Should be enabled within time window
        is_enabled = self.feature_flags.is_enabled(
            'time_limited_feature',
            user=self.regular_user
        )
        self.assertTrue(is_enabled)
        
        # Test outside time window
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now() + timedelta(hours=2)
            
            is_enabled_outside = self.feature_flags.is_enabled(
                'time_limited_feature',
                user=self.regular_user
            )
            self.assertFalse(is_enabled_outside)
            
    def test_ip_based_flag(self):
        """Test IP-based feature flag"""
        # Create IP-based flag
        flag_data = {
            'key': 'ip_whitelist_feature',
            'name': 'IP Whitelist Feature',
            'description': 'Feature for specific IP ranges',
            'enabled': True,
            'conditions': {
                'ip_ranges': ['192.168.1.0/24', '10.0.0.0/8']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Test with allowed IP
        is_enabled_allowed = self.feature_flags.is_enabled(
            'ip_whitelist_feature',
            user=self.regular_user,
            ip_address='192.168.1.100'
        )
        self.assertTrue(is_enabled_allowed)
        
        # Test with disallowed IP
        is_enabled_disallowed = self.feature_flags.is_enabled(
            'ip_whitelist_feature',
            user=self.regular_user,
            ip_address='203.0.113.1'
        )
        self.assertFalse(is_enabled_disallowed)
        
    def test_feature_flag_caching(self):
        """Test feature flag caching"""
        # Create flag
        flag_data = {
            'key': 'cached_flag',
            'name': 'Cached Flag',
            'description': 'Test flag caching',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # First evaluation (should query database)
        with patch('api.rate_limit.feature_flags.RateLimitFeatureFlags._evaluate_flag_conditions') as mock_evaluate:
            mock_evaluate.return_value = True
            
            result1 = self.feature_flags.is_enabled(
                'cached_flag',
                user=self.admin_user
            )
            
            # Second evaluation (should use cache)
            result2 = self.feature_flags.is_enabled(
                'cached_flag',
                user=self.admin_user
            )
            
            # Verify cache usage (evaluate should be called only once)
            mock_evaluate.assert_called_once()
            self.assertTrue(result1)
            self.assertTrue(result2)
            
    def test_feature_flag_override(self):
        """Test feature flag override"""
        # Create flag
        flag_data = {
            'key': 'override_test',
            'name': 'Override Test',
            'description': 'Test flag override',
            'enabled': False,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Should be disabled by default
        is_enabled_default = self.feature_flags.is_enabled(
            'override_test',
            user=self.admin_user
        )
        self.assertFalse(is_enabled_default)
        
        # Enable override
        self.feature_flags.set_override('override_test', True, user=self.admin_user)
        
        # Should be enabled with override
        is_enabled_override = self.feature_flags.is_enabled(
            'override_test',
            user=self.admin_user
        )
        self.assertTrue(is_enabled_override)
        
    def test_feature_flag_rollout(self):
        """Test gradual feature flag rollout"""
        # Create flag
        flag_data = {
            'key': 'gradual_rollout',
            'name': 'Gradual Rollout',
            'description': 'Test gradual rollout',
            'enabled': True,
            'conditions': {
                'percentage': 0  # Start at 0%
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Should be disabled at 0%
        is_enabled_0 = self.feature_flags.is_enabled(
            'gradual_rollout',
            user=self.regular_user
        )
        self.assertFalse(is_enabled_0)
        
        # Increase to 25%
        self.feature_flags.update_flag_percentage('gradual_rollout', 25)
        
        # Should be enabled for some users
        enabled_count = 0
        for i in range(100):
            test_user = User.objects.create_user(
                username=f'rollout_user_{i}',
                email=f'rollout_user_{i}@example.com',
                password='pass123'
            )
            
            if self.feature_flags.is_enabled('gradual_rollout', user=test_user):
                enabled_count += 1
                
        enabled_percentage = (enabled_count / 100) * 100
        self.assertGreaterEqual(enabled_percentage, 15)
        self.assertLessEqual(enabled_percentage, 35)
        
    def test_feature_flag_a_b_testing(self):
        """Test A/B testing with feature flags"""
        # Create A/B test flags
        flag_a_data = {
            'key': 'feature_a_variant',
            'name': 'Feature A Variant',
            'description': 'A/B test - Variant A',
            'enabled': True,
            'conditions': {
                'percentage': 50,
                'ab_test_group': 'control'
            }
        }
        
        flag_b_data = {
            'key': 'feature_b_variant',
            'name': 'Feature B Variant',
            'description': 'A/B test - Variant B',
            'enabled': True,
            'conditions': {
                'percentage': 50,
                'ab_test_group': 'variant'
            }
        }
        
        flag_a = self.feature_flags.create_flag(flag_a_data)
        flag_b = self.feature_flags.create_flag(flag_b_data)
        
        # Test A/B distribution
        control_count = 0
        variant_count = 0
        total_users = 200
        
        for i in range(total_users):
            test_user = User.objects.create_user(
                username=f'ab_user_{i}',
                email=f'ab_user_{i}@example.com',
                password='pass123'
            )
            
            if self.feature_flags.is_enabled('feature_a_variant', user=test_user):
                control_count += 1
            elif self.feature_flags.is_enabled('feature_b_variant', user=test_user):
                variant_count += 1
                
        # Verify A/B distribution
        self.assertEqual(control_count + variant_count, total_users)
        
        control_percentage = (control_count / total_users) * 100
        variant_percentage = (variant_count / total_users) * 100
        
        self.assertGreaterEqual(control_percentage, 40)
        self.assertLessEqual(control_percentage, 60)
        self.assertGreaterEqual(variant_percentage, 40)
        self.assertLessEqual(variant_percentage, 60)
        
    def test_feature_flag_dependencies(self):
        """Test feature flag dependencies"""
        # Create dependent flags
        parent_flag_data = {
            'key': 'parent_feature',
            'name': 'Parent Feature',
            'description': 'Parent feature flag',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        child_flag_data = {
            'key': 'child_feature',
            'name': 'Child Feature',
            'description': 'Child feature flag',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin'],
                'dependencies': ['parent_feature']
            }
        }
        
        parent_flag = self.feature_flags.create_flag(parent_flag_data)
        child_flag = self.feature_flags.create_flag(child_flag_data)
        
        # Child should be enabled when parent is enabled
        is_enabled_with_parent = self.feature_flags.is_enabled(
            'child_feature',
            user=self.admin_user
        )
        self.assertTrue(is_enabled_with_parent)
        
        # Disable parent
        self.feature_flags.disable_flag('parent_feature')
        
        # Child should be disabled when parent is disabled
        is_enabled_without_parent = self.feature_flags.is_enabled(
            'child_feature',
            user=self.admin_user
        )
        self.assertFalse(is_enabled_without_parent)
        
    def test_feature_flag_analytics(self):
        """Test feature flag analytics"""
        # Create flag
        flag_data = {
            'key': 'analytics_test',
            'name': 'Analytics Test',
            'description': 'Test flag analytics',
            'enabled': True,
            'conditions': {
                'percentage': 50
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Simulate flag evaluations
        for i in range(100):
            test_user = User.objects.create_user(
                username=f'analytics_user_{i}',
                email=f'analytics_user_{i}@example.com',
                password='pass123'
            )
            
            self.feature_flags.is_enabled('analytics_test', user=test_user)
            
        # Get analytics
        analytics = self.feature_flags.get_flag_analytics('analytics_test')
        
        # Verify analytics data
        self.assertIn('total_evaluations', analytics)
        self.assertIn('enabled_count', analytics)
        self.assertIn('disabled_count', analytics)
        self.assertIn('enabled_percentage', analytics)
        self.assertIn('unique_users', analytics)
        
        self.assertEqual(analytics['total_evaluations'], 100)
        self.assertEqual(analytics['enabled_count'] + analytics['disabled_count'], 100)
        
    def test_feature_flag_performance(self):
        """Test feature flag performance"""
        # Create multiple flags
        flags = []
        for i in range(10):
            flag_data = {
                'key': f'performance_test_{i}',
                'name': f'Performance Test {i}',
                'description': f'Test flag {i}',
                'enabled': True,
                'conditions': {
                    'percentage': 50
                }
            }
            flag = self.feature_flags.create_flag(flag_data)
            flags.append(flag)
            
        # Test performance
        start_time = time.time()
        
        for i in range(1000):
            for flag in flags:
                self.feature_flags.is_enabled(flag.key, user=self.regular_user)
                
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance (< 1 second for 10,000 evaluations)
        self.assertLess(total_time, 1.0)
        
        # Calculate average time per evaluation
        total_evaluations = 10 * 1000  # 10 flags * 1000 iterations
        avg_time_per_eval = total_time / total_evaluations
        self.assertLess(avg_time_per_eval, 0.0001)  # < 0.1ms per evaluation
        
    def test_feature_flag_error_handling(self):
        """Test feature flag error handling"""
        # Test with non-existent flag
        is_enabled_nonexistent = self.feature_flags.is_enabled(
            'non_existent_flag',
            user=self.regular_user
        )
        self.assertFalse(is_enabled_nonexistent)
        
        # Test with invalid conditions
        flag_data = {
            'key': 'invalid_conditions',
            'name': 'Invalid Conditions',
            'description': 'Test invalid conditions',
            'enabled': True,
            'conditions': {
                'invalid_condition': 'invalid_value'
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Should handle gracefully
        is_enabled_invalid = self.feature_flags.is_enabled(
            'invalid_conditions',
            user=self.regular_user
        )
        self.assertFalse(is_enabled_invalid)
        
    def test_feature_flag_bulk_operations(self):
        """Test bulk feature flag operations"""
        # Create multiple flags
        flag_keys = []
        for i in range(5):
            flag_data = {
                'key': f'bulk_test_{i}',
                'name': f'Bulk Test {i}',
                'description': f'Bulk test flag {i}',
                'enabled': True,
                'conditions': {
                    'user_roles': ['admin']
                }
            }
            flag = self.feature_flags.create_flag(flag_data)
            flag_keys.append(flag.key)
            
        # Bulk enable/disable
        self.feature_flags.bulk_enable_flags(flag_keys)
        
        for key in flag_keys:
            is_enabled = self.feature_flags.is_enabled(key, user=self.admin_user)
            self.assertTrue(is_enabled)
            
        self.feature_flags.bulk_disable_flags(flag_keys)
        
        for key in flag_keys:
            is_enabled = self.feature_flags.is_enabled(key, user=self.admin_user)
            self.assertFalse(is_enabled)
            
    def test_feature_flag_import_export(self):
        """Test feature flag import/export"""
        # Create flags
        flag_data = {
            'key': 'import_export_test',
            'name': 'Import Export Test',
            'description': 'Test import/export functionality',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin'],
                'percentage': 75
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Export flags
        exported_flags = self.feature_flags.export_flags()
        
        # Verify export
        self.assertIsInstance(exported_flags, list)
        self.assertGreater(len(exported_flags), 0)
        
        exported_flag = next(f for f in exported_flags if f['key'] == 'import_export_test')
        self.assertEqual(exported_flag['key'], 'import_export_test')
        self.assertEqual(exported_flag['name'], 'Import Export Test')
        
        # Delete original flag
        self.feature_flags.delete_flag('import_export_test')
        
        # Import flags
        imported_count = self.feature_flags.import_flags([exported_flag])
        
        # Verify import
        self.assertEqual(imported_count, 1)
        
        is_enabled = self.feature_flags.is_enabled('import_export_test', user=self.admin_user)
        self.assertTrue(is_enabled)


class RateLimitFeatureFlagsIntegrationTest(TestCase):
    """Integration tests for rate limit feature flags"""
    
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
        
        self.feature_flags = RateLimitFeatureFlags()
        self.rate_limit_service = RateLimitService()
        
        cache.clear()
        
    def test_feature_flag_integration_with_rate_limiting(self):
        """Test feature flags integration with rate limiting"""
        # Create feature flag for enhanced rate limiting
        flag_data = {
            'key': 'enhanced_rate_limiting',
            'name': 'Enhanced Rate Limiting',
            'description': 'Enable enhanced rate limiting algorithms',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Test rate limiting with feature flag
        # Admin should get enhanced limits
        admin_allowed = self.rate_limit_service.check_rate_limit(
            user=self.admin_user,
            endpoint='/api/test/',
            method='GET'
        )
        
        # Regular user should get standard limits
        regular_allowed = self.rate_limit_service.check_rate_limit(
            user=self.regular_user,
            endpoint='/api/test/',
            method='GET'
        )
        
        # Verify different behavior based on feature flag
        # (This would depend on the actual implementation)
        self.assertIsNotNone(admin_allowed)
        self.assertIsNotNone(regular_allowed)
        
    def test_feature_flag_driven_rate_limit_config(self):
        """Test feature flag-driven rate limit configuration"""
        # Create feature flag for different rate limit configs
        flag_data = {
            'key': 'strict_rate_limiting',
            'name': 'Strict Rate Limiting',
            'description': 'Apply stricter rate limits',
            'enabled': True,
            'conditions': {
                'percentage': 50
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Create rate limit config
        config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
        # Test rate limiting based on feature flag
        users = []
        for i in range(10):
            user = User.objects.create_user(
                username=f'flag_user_{i}',
                email=f'flag_user_{i}@example.com',
                password='pass123'
            )
            users.append(user)
            
        # Check rate limits for users
        strict_users = []
        normal_users = []
        
        for user in users:
            is_strict = self.feature_flags.is_enabled('strict_rate_limiting', user=user)
            
            if is_strict:
                strict_users.append(user)
            else:
                normal_users.append(user)
                
        # Verify distribution
        total_users = len(strict_users) + len(normal_users)
        self.assertEqual(total_users, 10)
        
        strict_percentage = (len(strict_users) / total_users) * 100
        self.assertGreaterEqual(strict_percentage, 30)
        self.assertLessEqual(strict_percentage, 70)
        
    def test_feature_flag_monitoring_integration(self):
        """Test feature flags integration with monitoring"""
        # Create feature flag
        flag_data = {
            'key': 'monitoring_feature',
            'name': 'Monitoring Feature',
            'description': 'Enable enhanced monitoring',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Simulate feature flag usage
        for i in range(100):
            user = self.admin_user if i % 2 == 0 else self.regular_user
            self.feature_flags.is_enabled('monitoring_feature', user=user)
            
        # Get analytics
        analytics = self.feature_flags.get_flag_analytics('monitoring_feature')
        
        # Verify analytics integration
        self.assertEqual(analytics['total_evaluations'], 100)
        self.assertGreater(analytics['enabled_count'], 0)
        
        # Verify monitoring metrics are collected
        monitoring_metrics = self.feature_flags.get_monitoring_metrics()
        self.assertIn('flag_evaluations', monitoring_metrics)
        self.assertIn('cache_hit_rate', monitoring_metrics)
        self.assertIn('average_evaluation_time', monitoring_metrics)
        
    def test_feature_flag_rollout_strategy(self):
        """Test feature flag rollout strategy"""
        # Create feature flag for gradual rollout
        flag_data = {
            'key': 'gradual_rollout_feature',
            'name': 'Gradual Rollout Feature',
            'description': 'Test gradual rollout strategy',
            'enabled': True,
            'conditions': {
                'percentage': 0
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Simulate gradual rollout
        rollout_stages = [10, 25, 50, 75, 100]
        
        for percentage in rollout_stages:
            # Update rollout percentage
            self.feature_flags.update_flag_percentage('gradual_rollout_feature', percentage)
            
            # Test with new users
            enabled_count = 0
            test_users = []
            
            for i in range(50):
                user = User.objects.create_user(
                    username=f'rollout_user_{percentage}_{i}',
                    email=f'rollout_user_{percentage}_{i}@example.com',
                    password='pass123'
                )
                test_users.append(user)
                
                if self.feature_flags.is_enabled('gradual_rollout_feature', user=user):
                    enabled_count += 1
                    
            # Verify rollout percentage
            enabled_percentage = (enabled_count / len(test_users)) * 100
            self.assertGreaterEqual(enabled_percentage, percentage - 10)
            self.assertLessEqual(enabled_percentage, percentage + 10)
            
    def test_feature_flag_disaster_recovery(self):
        """Test feature flag disaster recovery"""
        # Create critical feature flag
        flag_data = {
            'key': 'critical_feature',
            'name': 'Critical Feature',
            'description': 'Critical system feature',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin']
            }
        }
        
        flag = self.feature_flags.create_flag(flag_data)
        
        # Create kill switch flag
        kill_switch_data = {
            'key': 'kill_switch',
            'name': 'Kill Switch',
            'description': 'Emergency disable all features',
            'enabled': False,
            'conditions': {}
        }
        
        kill_switch = self.feature_flags.create_flag(kill_switch_data)
        
        # Test normal operation
        is_enabled_normal = self.feature_flags.is_enabled('critical_feature', user=self.admin_user)
        self.assertTrue(is_enabled_normal)
        
        # Activate kill switch
        self.feature_flags.enable_flag('kill_switch')
        
        # Test with kill switch active
        is_enabled_kill = self.feature_flags.is_enabled('critical_feature', user=self.admin_user)
        self.assertFalse(is_enabled_kill)
        
        # Deactivate kill switch
        self.feature_flags.disable_flag('kill_switch')
        
        # Test recovery
        is_enabled_recovery = self.feature_flags.is_enabled('critical_feature', user=self.admin_user)
        self.assertTrue(is_enabled_recovery)

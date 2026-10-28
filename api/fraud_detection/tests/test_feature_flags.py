"""
Comprehensive feature flag testing for fraud_detection module.

This test file covers all feature flag functionality and dynamic configuration
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.core.management import call_command
import time
import threading

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.feature_flags import (
    FraudFeatureFlags, FeatureFlagManager, DynamicConfig,
    FeatureFlagValidator, FeatureFlagAuditor, FeatureFlagCache
)
from api.fraud_detection.views import FeatureFlagAPIView
from api.users.models import User

User = get_user_model()


class BaseFeatureFlagTest(TestCase):
    """Base test class for feature flag testing"""
    
    def setUp(self):
        """Set up common test data"""
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
        
        # Create test fraud data
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
        
        self.fraud_attempt = FraudAttempt.objects.create(
            user=self.regular_user,
            attempt_type='multi_account',
            description='Test fraud attempt',
            detected_by='TestDetector',
            fraud_score=85,
            status='detected'
        )
        
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class FraudFeatureFlagsTest(BaseFeatureFlagTest):
    """Test cases for FraudFeatureFlags"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.feature_flags = FraudFeatureFlags()
    
    def test_is_enabled_basic_feature(self):
        """Test basic feature flag checking"""
        # Test with known feature
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'advanced_fraud_detection': {
                'enabled': True,
                'description': 'Advanced fraud detection algorithms'
            }
        }):
            is_enabled = self.feature_flags.is_enabled('advanced_fraud_detection')
            self.assertTrue(is_enabled)
            
            # Test disabled feature
            with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
                'advanced_fraud_detection': {
                    'enabled': False,
                    'description': 'Advanced fraud detection algorithms'
                }
            }):
                is_disabled = self.feature_flags.is_enabled('advanced_fraud_detection')
                self.assertFalse(is_disabled)
    
    def test_is_enabled_with_conditions(self):
        """Test feature flag with conditions"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'beta_features': {
                'enabled': True,
                'conditions': {
                    'user_roles': ['admin', 'fraud_analyst'],
                    'tenant_ids': [1, 2, 3],
                    'percentage': 50
                }
            }
        }):
            # Test with admin user (should be enabled)
            is_enabled_admin = self.feature_flags.is_enabled(
                'beta_features',
                user=self.admin_user,
                tenant_id=1
            )
            self.assertTrue(is_enabled_admin)
            
            # Test with regular user (should be disabled)
            is_enabled_regular = self.feature_flags.is_enabled(
                'beta_features',
                user=self.regular_user,
                tenant_id=1
            )
            self.assertFalse(is_enabled_regular)
    
    def test_is_enabled_with_percentage_rollout(self):
        """Test percentage-based feature rollout"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'new_algorithm': {
                'enabled': True,
                'conditions': {
                    'percentage': 50
                }
            }
        }):
            # Mock user ID for consistent testing
            with patch.object(self.feature_flags, '_get_user_hash', return_value=0.3):
                # 30% should be below 50% threshold
                is_enabled = self.feature_flags.is_enabled('new_algorithm', user=self.regular_user)
                self.assertTrue(is_enabled)
            
            with patch.object(self.feature_flags, '_get_user_hash', return_value=0.7):
                # 70% should be above 50% threshold
                is_enabled = self.feature_flags.is_enabled('new_algorithm', user=self.regular_user)
                self.assertFalse(is_enabled)
    
    def test_get_feature_config(self):
        """Test getting feature configuration"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'advanced_detection': {
                'enabled': True,
                'description': 'Advanced detection algorithms',
                'parameters': {
                    'sensitivity': 0.8,
                    'max_processing_time': 5.0,
                    'supported_types': ['account', 'payment', 'behavioral']
                }
            }
        }):
            config = self.feature_flags.get_feature_config('advanced_detection')
            
            self.assertTrue(config['enabled'])
            self.assertEqual(config['description'], 'Advanced detection algorithms')
            self.assertIn('parameters', config)
            self.assertEqual(config['parameters']['sensitivity'], 0.8)
    
    def test_get_all_enabled_features(self):
        """Test getting all enabled features"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'feature_a': {'enabled': True, 'description': 'Feature A'},
            'feature_b': {'enabled': False, 'description': 'Feature B'},
            'feature_c': {'enabled': True, 'description': 'Feature C'},
            'feature_d': {'enabled': False, 'description': 'Feature D'}
        }):
            enabled_features = self.feature_flags.get_all_enabled_features()
            
            self.assertEqual(len(enabled_features), 2)
            self.assertIn('feature_a', enabled_features)
            self.assertIn('feature_c', enabled_features)
            self.assertNotIn('feature_b', enabled_features)
            self.assertNotIn('feature_d', enabled_features)
    
    def test_get_features_for_user(self):
        """Test getting features available to specific user"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'admin_feature': {
                'enabled': True,
                'conditions': {'user_roles': ['admin']}
            },
            'user_feature': {
                'enabled': True,
                'conditions': {'user_roles': ['user', 'admin']}
            },
            'beta_feature': {
                'enabled': True,
                'conditions': {'percentage': 100}  # Available to all
            }
        }):
            # Admin user should have access to all features
            admin_features = self.feature_flags.get_features_for_user(self.admin_user)
            self.assertEqual(len(admin_features), 3)
            
            # Regular user should have access to user_feature and beta_feature
            user_features = self.feature_flags.get_features_for_user(self.regular_user)
            self.assertEqual(len(user_features), 2)
            self.assertIn('user_feature', user_features)
            self.assertIn('beta_feature', user_features)
            self.assertNotIn('admin_feature', user_features)
    
    def test_feature_flag_caching(self):
        """Test feature flag caching"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'cached_feature': {
                'enabled': True,
                'description': 'Cached feature'
            }
        }):
            # First call should compute and cache
            with patch.object(self.feature_flags, '_compute_feature_enabled') as mock_compute:
                mock_compute.return_value = True
                
                result1 = self.feature_flags.is_enabled('cached_feature', user=self.regular_user)
                self.assertTrue(result1)
                mock_compute.assert_called_once()
            
            # Second call should use cache
            with patch.object(self.feature_flags, '_compute_feature_enabled') as mock_compute:
                result2 = self.feature_flags.is_enabled('cached_feature', user=self.regular_user)
                self.assertTrue(result2)
                mock_compute.assert_not_called()  # Should not be called due to cache
    
    def test_feature_flag_invalidation(self):
        """Test feature flag cache invalidation"""
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'invalidate_feature': {
                'enabled': True,
                'description': 'Feature to invalidate'
            }
        }):
            # Enable feature and cache result
            result1 = self.feature_flags.is_enabled('invalidate_feature', user=self.regular_user)
            self.assertTrue(result1)
            
            # Invalidate cache
            self.feature_flags.invalidate_cache('invalidate_feature')
            
            # Next call should recompute
            with patch.object(self.feature_flags, '_compute_feature_enabled') as mock_compute:
                mock_compute.return_value = False
                
                result2 = self.feature_flags.is_enabled('invalidate_feature', user=self.regular_user)
                self.assertFalse(result2)
                mock_compute.assert_called_once()
    
    def test_feature_flag_with_time_constraints(self):
        """Test feature flags with time-based constraints"""
        current_time = timezone.now()
        
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'time_limited_feature': {
                'enabled': True,
                'conditions': {
                    'start_time': (current_time - timezone.timedelta(hours=1)).isoformat(),
                    'end_time': (current_time + timezone.timedelta(hours=1)).isoformat()
                }
            }
        }):
            # Should be enabled within time window
            is_enabled = self.feature_flags.is_enabled('time_limited_feature')
            self.assertTrue(is_enabled)
        
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'expired_feature': {
                'enabled': True,
                'conditions': {
                    'start_time': (current_time - timezone.timedelta(hours=2)).isoformat(),
                    'end_time': (current_time - timezone.timedelta(hours=1)).isoformat()
                }
            }
        }):
            # Should be disabled outside time window
            is_enabled = self.feature_flags.is_enabled('expired_feature')
            self.assertFalse(is_enabled)


class FeatureFlagManagerTest(BaseFeatureFlagTest):
    """Test cases for FeatureFlagManager"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.flag_manager = FeatureFlagManager()
    
    def test_create_feature_flag(self):
        """Test creating a new feature flag"""
        flag_data = {
            'name': 'new_detection_algorithm',
            'description': 'New machine learning detection algorithm',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin', 'fraud_analyst'],
                'percentage': 25
            },
            'parameters': {
                'sensitivity': 0.9,
                'processing_limit': 1000
            }
        }
        
        with patch.object(self.flag_manager, '_store_feature_flag') as mock_store:
            mock_store.return_value = {'id': 'flag_123', **flag_data}
            
            created_flag = self.flag_manager.create_feature_flag(flag_data)
            
            self.assertEqual(created_flag['name'], 'new_detection_algorithm')
            self.assertTrue(created_flag['enabled'])
            self.assertIn('id', created_flag)
            mock_store.assert_called_once()
    
    def test_update_feature_flag(self):
        """Test updating an existing feature flag"""
        flag_id = 'existing_flag_123'
        update_data = {
            'enabled': False,
            'conditions': {
                'percentage': 50  # Changed from 25
            }
        }
        
        with patch.object(self.flag_manager, '_get_feature_flag') as mock_get:
            mock_get.return_value = {
                'id': flag_id,
                'name': 'existing_flag',
                'enabled': True,
                'conditions': {'percentage': 25}
            }
            
            with patch.object(self.flag_manager, '_store_feature_flag') as mock_store:
                mock_store.return_value = {
                    'id': flag_id,
                    'name': 'existing_flag',
                    'enabled': False,
                    'conditions': {'percentage': 50}
                }
                
                updated_flag = self.flag_manager.update_feature_flag(flag_id, update_data)
                
                self.assertFalse(updated_flag['enabled'])
                self.assertEqual(updated_flag['conditions']['percentage'], 50)
    
    def test_delete_feature_flag(self):
        """Test deleting a feature flag"""
        flag_id = 'flag_to_delete_123'
        
        with patch.object(self.flag_manager, '_delete_feature_flag') as mock_delete:
            mock_delete.return_value = True
            
            result = self.flag_manager.delete_feature_flag(flag_id)
            
            self.assertTrue(result)
            mock_delete.assert_called_once_with(flag_id)
    
    def test_list_feature_flags(self):
        """Test listing all feature flags"""
        with patch.object(self.flag_manager, '_get_all_feature_flags') as mock_get_all:
            mock_get_all.return_value = [
                {
                    'id': 'flag_1',
                    'name': 'feature_a',
                    'enabled': True,
                    'description': 'Feature A'
                },
                {
                    'id': 'flag_2',
                    'name': 'feature_b',
                    'enabled': False,
                    'description': 'Feature B'
                }
            ]
            
            flags = self.flag_manager.list_feature_flags()
            
            self.assertEqual(len(flags), 2)
            self.assertEqual(flags[0]['name'], 'feature_a')
            self.assertEqual(flags[1]['name'], 'feature_b')
    
    def test_get_feature_flag_usage_stats(self):
        """Test getting feature flag usage statistics"""
        with patch.object(self.flag_manager, '_get_usage_stats') as mock_stats:
            mock_stats.return_value = {
                'feature_a': {
                    'total_checks': 1000,
                    'enabled_checks': 750,
                    'disabled_checks': 250,
                    'usage_percentage': 75.0,
                    'last_checked': timezone.now().isoformat()
                },
                'feature_b': {
                    'total_checks': 500,
                    'enabled_checks': 100,
                    'disabled_checks': 400,
                    'usage_percentage': 20.0,
                    'last_checked': timezone.now().isoformat()
                }
            }
            
            stats = self.flag_manager.get_feature_flag_usage_stats()
            
            self.assertIn('feature_a', stats)
            self.assertIn('feature_b', stats)
            self.assertEqual(stats['feature_a']['total_checks'], 1000)
            self.assertEqual(stats['feature_b']['usage_percentage'], 20.0)
    
    def test_bulk_feature_flag_operations(self):
        """Test bulk operations on feature flags"""
        bulk_operations = [
            {
                'action': 'create',
                'data': {
                    'name': 'bulk_feature_1',
                    'enabled': True,
                    'description': 'Bulk feature 1'
                }
            },
            {
                'action': 'update',
                'flag_id': 'existing_flag',
                'data': {'enabled': False}
            },
            {
                'action': 'delete',
                'flag_id': 'flag_to_delete'
            }
        ]
        
        with patch.multiple(
            self.flag_manager,
            create_feature_flag=MagicMock(return_value={'id': 'new_1'}),
            update_feature_flag=MagicMock(return_value={'id': 'existing_flag', 'enabled': False}),
            delete_feature_flag=MagicMock(return_value=True)
        ):
            results = self.flag_manager.bulk_operations(bulk_operations)
            
            self.assertEqual(len(results), 3)
            self.assertIn('created', results[0])
            self.assertIn('updated', results[1])
            self.assertIn('deleted', results[2])


class DynamicConfigTest(BaseFeatureFlagTest):
    """Test cases for DynamicConfig"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.dynamic_config = DynamicConfig()
    
    def test_get_config_value(self):
        """Test getting configuration values"""
        with patch('api.fraud_detection.feature_flags.DYNAMIC_CONFIG', {
            'fraud_detection': {
                'max_processing_time': 5.0,
                'default_sensitivity': 0.8,
                'enabled_detectors': ['multi_account', 'vpn_proxy', 'click_fraud']
            },
            'alerts': {
                'max_alerts_per_user': 10,
                'alert_retention_days': 30
            }
        }):
            # Test getting specific value
            max_time = self.dynamic_config.get('fraud_detection.max_processing_time')
            self.assertEqual(max_time, 5.0)
            
            # Test getting nested value
            detectors = self.dynamic_config.get('fraud_detection.enabled_detectors')
            self.assertEqual(detectors, ['multi_account', 'vpn_proxy', 'click_fraud'])
            
            # Test getting non-existent value with default
            non_existent = self.dynamic_config.get('non_existent.key', 'default_value')
            self.assertEqual(non_existent, 'default_value')
    
    def test_set_config_value(self):
        """Test setting configuration values"""
        with patch.object(self.dynamic_config, '_store_config') as mock_store:
            mock_store.return_value = True
            
            # Set simple value
            result = self.dynamic_config.set('new_config.value', 42)
            self.assertTrue(result)
            
            # Set nested value
            result = self.dynamic_config.set('fraud_detection.new_setting', True)
            self.assertTrue(result)
            
            # Verify store was called
            self.assertEqual(mock_store.call_count, 2)
    
    def test_update_config_section(self):
        """Test updating entire configuration section"""
        new_section = {
            'max_processing_time': 10.0,
            'default_sensitivity': 0.9,
            'new_parameter': 'test_value'
        }
        
        with patch.object(self.dynamic_config, '_store_config') as mock_store:
            mock_store.return_value = True
            
            result = self.dynamic_config.update_section('fraud_detection', new_section)
            
            self.assertTrue(result)
            mock_store.assert_called_once()
    
    def test_watch_config_changes(self):
        """Test watching for configuration changes"""
        callback_called = []
        
        def config_callback(key, old_value, new_value):
            callback_called.append((key, old_value, new_value))
        
        with patch.object(self.dynamic_config, '_register_watcher') as mock_register:
            mock_register.return_value = 'watcher_id_123'
            
            watcher_id = self.dynamic_config.watch('fraud_detection.max_processing_time', config_callback)
            
            self.assertEqual(watcher_id, 'watcher_id_123')
            mock_register.assert_called_once()
    
    def test_config_validation(self):
        """Test configuration value validation"""
        # Test valid configuration
        valid_config = {
            'max_processing_time': 5.0,
            'default_sensitivity': 0.8,
            'enabled_detectors': ['multi_account', 'vpn_proxy']
        }
        
        is_valid = self.dynamic_config.validate_config('fraud_detection', valid_config)
        self.assertTrue(is_valid)
        
        # Test invalid configuration
        invalid_config = {
            'max_processing_time': 'invalid_type',  # Should be float
            'default_sensitivity': 1.5,  # Should be <= 1.0
            'enabled_detectors': 'not_a_list'  # Should be list
        }
        
        is_invalid = self.dynamic_config.validate_config('fraud_detection', invalid_config)
        self.assertFalse(is_invalid)
    
    def test_config_environment_overrides(self):
        """Test environment-based configuration overrides"""
        with patch.dict('os.environ', {'FRAUD_DETECTION_MAX_PROCESSING_TIME': '15.0'}):
            with patch('api.fraud_detection.feature_flags.DYNAMIC_CONFIG', {
                'fraud_detection': {
                    'max_processing_time': 5.0,  # Default value
                    'default_sensitivity': 0.8
                }
            }):
                # Environment override should take precedence
                value = self.dynamic_config.get('fraud_detection.max_processing_time')
                self.assertEqual(value, 15.0)
                
                # Non-overridden value should use default
                sensitivity = self.dynamic_config.get('fraud_detection.default_sensitivity')
                self.assertEqual(sensitivity, 0.8)


class FeatureFlagValidatorTest(BaseFeatureFlagTest):
    """Test cases for FeatureFlagValidator"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.validator = FeatureFlagValidator()
    
    def test_validate_flag_definition(self):
        """Test feature flag definition validation"""
        # Valid flag definition
        valid_flag = {
            'name': 'test_flag',
            'description': 'Test feature flag',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin', 'user'],
                'percentage': 50
            },
            'parameters': {
                'sensitivity': 0.8
            }
        }
        
        validation_result = self.validator.validate_flag_definition(valid_flag)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_invalid_flag_definition(self):
        """Test invalid feature flag definition validation"""
        invalid_flag = {
            'name': '',  # Empty name
            'description': '',  # Empty description
            'enabled': 'not_boolean',  # Invalid type
            'conditions': {
                'user_roles': 'not_a_list',  # Should be list
                'percentage': 150  # Should be <= 100
            },
            'parameters': {
                'sensitivity': 1.5  # Should be <= 1.0
            }
        }
        
        validation_result = self.validator.validate_flag_definition(invalid_flag)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
        
        # Check for specific errors
        errors = validation_result['errors']
        self.assertTrue(any('name' in error.lower() for error in errors))
        self.assertTrue(any('enabled' in error.lower() for error in errors))
        self.assertTrue(any('percentage' in error.lower() for error in errors))
    
    def test_validate_conditions(self):
        """Test condition validation"""
        # Valid conditions
        valid_conditions = {
            'user_roles': ['admin', 'user'],
            'tenant_ids': [1, 2, 3],
            'percentage': 25,
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timezone.timedelta(hours=1)).isoformat()
        }
        
        is_valid = self.validator.validate_conditions(valid_conditions)
        self.assertTrue(is_valid)
        
        # Invalid conditions
        invalid_conditions = {
            'user_roles': 'not_a_list',
            'tenant_ids': [1, 'not_integer', 3],
            'percentage': -10,
            'start_time': 'invalid_datetime'
        }
        
        is_invalid = self.validator.validate_conditions(invalid_conditions)
        self.assertFalse(is_invalid)
    
    def test_validate_parameters(self):
        """Test parameter validation"""
        # Valid parameters
        valid_params = {
            'sensitivity': 0.8,
            'max_processing_time': 5.0,
            'retry_attempts': 3,
            'enabled_features': ['feature_a', 'feature_b']
        }
        
        is_valid = self.validator.validate_parameters(valid_params)
        self.assertTrue(is_valid)
        
        # Invalid parameters
        invalid_params = {
            'sensitivity': 1.5,  # > 1.0
            'max_processing_time': -1.0,  # Negative
            'retry_attempts': 'not_integer',
            'enabled_features': 'not_a_list'
        }
        
        is_invalid = self.validator.validate_parameters(invalid_params)
        self.assertFalse(is_invalid)
    
    def test_check_flag_conflicts(self):
        """Test checking for flag conflicts"""
        existing_flags = [
            {
                'name': 'existing_flag',
                'conditions': {'user_roles': ['admin']},
                'parameters': {'sensitivity': 0.8}
            }
        ]
        
        # Conflicting flag (same name)
        conflicting_flag = {
            'name': 'existing_flag',
            'description': 'Conflicting flag',
            'enabled': True
        }
        
        conflicts = self.validator.check_flag_conflicts(conflicting_flag, existing_flags)
        
        self.assertGreater(len(conflicts), 0)
        self.assertTrue(any('name' in conflict['type'].lower() for conflict in conflicts))
    
    def test_validate_flag_dependencies(self):
        """Test flag dependency validation"""
        flag_with_dependencies = {
            'name': 'dependent_flag',
            'description': 'Flag with dependencies',
            'enabled': True,
            'dependencies': ['base_flag', 'another_flag']
        }
        
        existing_flags = ['base_flag', 'another_flag', 'third_flag']
        
        # All dependencies exist
        is_valid = self.validator.validate_dependencies(flag_with_dependencies, existing_flags)
        self.assertTrue(is_valid)
        
        # Missing dependencies
        missing_deps = self.validator.validate_dependencies(
            flag_with_dependencies,
            ['base_flag']  # Missing 'another_flag'
        )
        self.assertFalse(missing_deps)


class FeatureFlagAuditorTest(BaseFeatureFlagTest):
    """Test cases for FeatureFlagAuditor"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.auditor = FeatureFlagAuditor()
    
    def test_log_flag_usage(self):
        """Test logging flag usage"""
        with patch.object(self.auditor, '_record_usage') as mock_record:
            mock_record.return_value = {'id': 'usage_123', 'timestamp': timezone.now().isoformat()}
            
            usage_log = self.auditor.log_usage(
                flag_name='test_flag',
                user=self.regular_user,
                result=True,
                context={'ip_address': '192.168.1.1'}
            )
            
            self.assertIn('id', usage_log)
            self.assertIn('timestamp', usage_log)
            mock_record.assert_called_once()
    
    def test_get_flag_usage_history(self):
        """Test getting flag usage history"""
        with patch.object(self.auditor, '_get_usage_history') as mock_history:
            mock_history.return_value = [
                {
                    'id': 'usage_1',
                    'flag_name': 'test_flag',
                    'user_id': self.regular_user.pk,
                    'result': True,
                    'timestamp': timezone.now().isoformat(),
                    'context': {'ip_address': '192.168.1.1'}
                },
                {
                    'id': 'usage_2',
                    'flag_name': 'test_flag',
                    'user_id': self.admin_user.pk,
                    'result': False,
                    'timestamp': timezone.now().isoformat(),
                    'context': {'ip_address': '192.168.1.2'}
                }
            ]
            
            history = self.auditor.get_usage_history('test_flag', days=7)
            
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['flag_name'], 'test_flag')
            self.assertTrue(history[0]['result'])
            self.assertFalse(history[1]['result'])
    
    def test_generate_usage_report(self):
        """Test generating usage reports"""
        with patch.object(self.auditor, '_generate_report_data') as mock_report:
            mock_report.return_value = {
                'flag_name': 'test_flag',
                'period': '7_days',
                'total_checks': 1000,
                'enabled_checks': 750,
                'disabled_checks': 250,
                'usage_percentage': 75.0,
                'unique_users': 50,
                'top_users': [
                    {'user_id': self.admin_user.pk, 'check_count': 25},
                    {'user_id': self.regular_user.pk, 'check_count': 20}
                ],
                'daily_breakdown': [
                    {'date': '2023-01-01', 'checks': 150, 'enabled': 120},
                    {'date': '2023-01-02', 'checks': 140, 'enabled': 105}
                ]
            }
            
            report = self.auditor.generate_usage_report('test_flag', days=7)
            
            self.assertEqual(report['total_checks'], 1000)
            self.assertEqual(report['usage_percentage'], 75.0)
            self.assertEqual(len(report['top_users']), 2)
            self.assertIn('daily_breakdown', report)
    
    def test_audit_flag_changes(self):
        """Test auditing flag changes"""
        with patch.object(self.auditor, '_record_change') as mock_record:
            mock_record.return_value = {'id': 'change_123', 'timestamp': timezone.now().isoformat()}
            
            change_log = self.auditor.log_change(
                flag_name='test_flag',
                change_type='updated',
                old_values={'enabled': False},
                new_values={'enabled': True},
                changed_by=self.admin_user,
                reason='Enable feature for testing'
            )
            
            self.assertIn('id', change_log)
            self.assertEqual(change_log['change_type'], 'updated')
            mock_record.assert_called_once()
    
    def test_get_change_history(self):
        """Test getting change history"""
        with patch.object(self.auditor, '_get_change_history') as mock_history:
            mock_history.return_value = [
                {
                    'id': 'change_1',
                    'flag_name': 'test_flag',
                    'change_type': 'created',
                    'changed_by': self.admin_user.pk,
                    'timestamp': timezone.now().isoformat(),
                    'reason': 'Initial creation'
                },
                {
                    'id': 'change_2',
                    'flag_name': 'test_flag',
                    'change_type': 'updated',
                    'changed_by': self.admin_user.pk,
                    'timestamp': timezone.now().isoformat(),
                    'old_values': {'enabled': False},
                    'new_values': {'enabled': True},
                    'reason': 'Enable feature'
                }
            ]
            
            history = self.auditor.get_change_history('test_flag')
            
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]['change_type'], 'created')
            self.assertEqual(history[1]['change_type'], 'updated')
    
    def test_compliance_audit(self):
        """Test compliance audit"""
        with patch.object(self.auditor, '_perform_compliance_check') as mock_compliance:
            mock_compliance.return_value = {
                'compliant': True,
                'issues': [],
                'recommendations': [],
                'last_audit': timezone.now().isoformat(),
                'audit_score': 100
            }
            
            compliance_result = self.auditor.perform_compliance_audit()
            
            self.assertTrue(compliance_result['compliant'])
            self.assertEqual(compliance_result['audit_score'], 100)
            self.assertEqual(len(compliance_result['issues']), 0)


class FeatureFlagCacheTest(BaseFeatureFlagTest):
    """Test cases for FeatureFlagCache"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.cache = FeatureFlagCache()
    
    def test_cache_set_and_get(self):
        """Test cache set and get operations"""
        cache_key = 'test_flag:user_123'
        cache_value = {'enabled': True, 'parameters': {'sensitivity': 0.8}}
        
        # Set cache
        self.cache.set(cache_key, cache_value, ttl=300)
        
        # Get cache
        retrieved_value = self.cache.get(cache_key)
        
        self.assertEqual(retrieved_value, cache_value)
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        cache_key = 'expiring_flag:user_123'
        cache_value = {'enabled': True}
        
        # Set with very short TTL
        self.cache.set(cache_key, cache_value, ttl=1)
        
        # Should be available immediately
        retrieved_value = self.cache.get(cache_key)
        self.assertEqual(retrieved_value, cache_value)
        
        # Wait for expiration (in real implementation, this would use time mocking)
        time.sleep(2)
        
        # Should be expired
        expired_value = self.cache.get(cache_key)
        self.assertIsNone(expired_value)
    
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        cache_key = 'invalidatable_flag:user_123'
        cache_value = {'enabled': True}
        
        # Set cache
        self.cache.set(cache_key, cache_value, ttl=300)
        
        # Verify it's cached
        retrieved_value = self.cache.get(cache_key)
        self.assertEqual(retrieved_value, cache_value)
        
        # Invalidate cache
        self.cache.invalidate(cache_key)
        
        # Should be gone
        invalidated_value = self.cache.get(cache_key)
        self.assertIsNone(invalidated_value)
    
    def test_cache_pattern_invalidation(self):
        """Test pattern-based cache invalidation"""
        # Set multiple cache entries
        cache_entries = [
            ('feature_a:user_123', {'enabled': True}),
            ('feature_a:user_456', {'enabled': False}),
            ('feature_b:user_123', {'enabled': True}),
            ('feature_a:user_789', {'enabled': True})
        ]
        
        for key, value in cache_entries:
            self.cache.set(key, value, ttl=300)
        
        # Invalidate all entries for feature_a
        self.cache.invalidate_pattern('feature_a:*')
        
        # feature_a entries should be gone
        self.assertIsNone(self.cache.get('feature_a:user_123'))
        self.assertIsNone(self.cache.get('feature_a:user_456'))
        self.assertIsNone(self.cache.get('feature_a:user_789'))
        
        # feature_b entry should remain
        self.assertIsNotNone(self.cache.get('feature_b:user_123'))
    
    def test_cache_statistics(self):
        """Test cache statistics"""
        # Perform cache operations
        self.cache.set('stat_test_1', {'value': 1}, ttl=300)
        self.cache.get('stat_test_1')
        self.cache.get('non_existent_key')
        self.cache.invalidate('stat_test_1')
        
        stats = self.cache.get_statistics()
        
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('sets', stats)
        self.assertIn('invalidations', stats)
        
        self.assertEqual(stats['sets'], 1)
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['invalidations'], 1)
    
    def test_cache_warm_up(self):
        """Test cache warm up functionality"""
        warm_up_data = {
            'feature_a:user_123': {'enabled': True},
            'feature_a:user_456': {'enabled': False},
            'feature_b:user_123': {'enabled': True}
        }
        
        with patch.object(self.cache, 'set') as mock_set:
            self.cache.warm_up(warm_up_data, ttl=300)
            
            # Should call set for each entry
            self.assertEqual(mock_set.call_count, 3)
            
            # Verify all entries were warmed up
            call_args_list = mock_set.call_args_list
            warmed_keys = [call[0][0] for call in call_args_list]
            
            self.assertIn('feature_a:user_123', warmed_keys)
            self.assertIn('feature_a:user_456', warmed_keys)
            self.assertIn('feature_b:user_123', warmed_keys)


class FeatureFlagAPIViewTest(BaseFeatureFlagTest):
    """Test cases for FeatureFlagAPIView"""
    
    def test_list_feature_flags_api(self):
        """Test listing feature flags via API"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:feature-flags-list')
        
        with patch('api.fraud_detection.feature_flags.FeatureFlagManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.list_feature_flags.return_value = [
                {
                    'id': 'flag_1',
                    'name': 'feature_a',
                    'enabled': True,
                    'description': 'Feature A'
                },
                {
                    'id': 'flag_2',
                    'name': 'feature_b',
                    'enabled': False,
                    'description': 'Feature B'
                }
            ]
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]['name'], 'feature_a')
            self.assertEqual(data[1]['enabled'], False)
    
    def test_create_feature_flag_api(self):
        """Test creating feature flag via API"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:feature-flags-list')
        
        flag_data = {
            'name': 'new_api_feature',
            'description': 'Feature created via API',
            'enabled': True,
            'conditions': {
                'user_roles': ['admin'],
                'percentage': 25
            }
        }
        
        with patch('api.fraud_detection.feature_flags.FeatureFlagManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.create_feature_flag.return_value = {
                'id': 'new_flag_123',
                **flag_data
            }
            
            response = self.client.post(url, flag_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            
            data = response.json()
            self.assertEqual(data['name'], 'new_api_feature')
            self.assertTrue(data['enabled'])
    
    def test_update_feature_flag_api(self):
        """Test updating feature flag via API"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:feature-flags-detail', kwargs={'pk': 'flag_123'})
        
        update_data = {
            'enabled': False,
            'conditions': {
                'percentage': 50
            }
        }
        
        with patch('api.fraud_detection.feature_flags.FeatureFlagManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.update_feature_flag.return_value = {
                'id': 'flag_123',
                'name': 'existing_flag',
                'enabled': False,
                'conditions': {'percentage': 50}
            }
            
            response = self.client.patch(url, update_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertFalse(data['enabled'])
            self.assertEqual(data['conditions']['percentage'], 50)
    
    def test_check_feature_flag_api(self):
        """Test checking feature flag via API"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:feature-flags-check', kwargs={'pk': 'test_flag'})
        
        with patch('api.fraud_detection.feature_flags.FraudFeatureFlags') as mock_flags:
            mock_instance = mock_flags.return_value
            mock_instance.is_enabled.return_value = True
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertTrue(data['enabled'])
            self.assertIn('checked_at', data)
    
    def test_feature_flag_usage_stats_api(self):
        """Test getting usage statistics via API"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:feature-flags-usage-stats')
        
        with patch('api.fraud_detection.feature_flags.FeatureFlagManager') as mock_manager:
            mock_instance = mock_manager.return_value
            mock_instance.get_feature_flag_usage_stats.return_value = {
                'feature_a': {
                    'total_checks': 1000,
                    'enabled_checks': 750,
                    'usage_percentage': 75.0
                },
                'feature_b': {
                    'total_checks': 500,
                    'enabled_checks': 100,
                    'usage_percentage': 20.0
                }
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('feature_a', data)
            self.assertIn('feature_b', data)
            self.assertEqual(data['feature_a']['usage_percentage'], 75.0)
    
    def test_feature_flag_unauthorized(self):
        """Test feature flag API authorization"""
        url = reverse('frauddetection:feature-flags-list')
        
        # Test without authentication
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test with regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeatureFlagIntegrationTest(BaseFeatureFlagTest):
    """Integration tests for feature flag functionality"""
    
    def test_end_to_end_feature_flag_workflow(self):
        """Test complete feature flag workflow"""
        # Step 1: Create feature flag
        flag_manager = FeatureFlagManager()
        with patch.object(flag_manager, '_store_feature_flag') as mock_store:
            mock_store.return_value = {'id': 'workflow_flag', 'name': 'workflow_test'}
            
            flag = flag_manager.create_feature_flag({
                'name': 'workflow_test',
                'description': 'Workflow test flag',
                'enabled': True,
                'conditions': {'percentage': 100}
            })
            
            self.assertEqual(flag['name'], 'workflow_test')
        
        # Step 2: Check flag status
        feature_flags = FraudFeatureFlags()
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'workflow_test': {
                'enabled': True,
                'conditions': {'percentage': 100}
            }
        }):
            is_enabled = feature_flags.is_enabled('workflow_test', user=self.regular_user)
            self.assertTrue(is_enabled)
        
        # Step 3: Log usage
        auditor = FeatureFlagAuditor()
        with patch.object(auditor, '_record_usage') as mock_record:
            mock_record.return_value = {'id': 'usage_123'}
            
            usage_log = auditor.log_usage('workflow_test', self.regular_user, True)
            self.assertIn('id', usage_log)
        
        # Step 4: Get usage statistics
        with patch.object(flag_manager, '_get_usage_stats') as mock_stats:
            mock_stats.return_value = {
                'workflow_test': {
                    'total_checks': 1,
                    'enabled_checks': 1,
                    'usage_percentage': 100.0
                }
            }
            
            stats = flag_manager.get_feature_flag_usage_stats()
            self.assertEqual(stats['workflow_test']['total_checks'], 1)
    
    def test_feature_flag_with_fraud_detection_integration(self):
        """Test feature flag integration with fraud detection"""
        # Create a feature flag that controls a detection algorithm
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'advanced_ml_detection': {
                'enabled': True,
                'conditions': {
                    'user_roles': ['admin'],
                    'percentage': 50
                }
            }
        }):
            feature_flags = FraudFeatureFlags()
            
            # Mock user hash for consistent testing
            with patch.object(feature_flags, '_get_user_hash', return_value=0.3):
                # Admin user with 30% hash (below 50% threshold)
                admin_enabled = feature_flags.is_enabled(
                    'advanced_ml_detection',
                    user=self.admin_user
                )
                self.assertTrue(admin_enabled)
            
            with patch.object(feature_flags, '_get_user_hash', return_value=0.7):
                # Regular user with 70% hash (above 50% threshold, but also wrong role)
                regular_enabled = feature_flags.is_enabled(
                    'advanced_ml_detection',
                    user=self.regular_user
                )
                self.assertFalse(regular_enabled)
    
    def test_feature_flag_performance_impact(self):
        """Test feature flag performance impact"""
        feature_flags = FraudFeatureFlags()
        
        # Measure performance with caching
        start_time = time.time()
        
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'performance_test': {
                'enabled': True,
                'description': 'Performance test flag'
            }
        }):
            # First call (computes and caches)
            result1 = feature_flags.is_enabled('performance_test', user=self.regular_user)
            
            # Second call (uses cache)
            result2 = feature_flags.is_enabled('performance_test', user=self.regular_user)
            
            # Third call (uses cache)
            result3 = feature_flags.is_enabled('performance_test', user=self.regular_user)
        
        total_time = time.time() - start_time
        
        # All calls should return the same result
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertTrue(result3)
        
        # Should be very fast due to caching (under 10ms for mocked operations)
        self.assertLess(total_time, 0.01)
    
    def test_concurrent_feature_flag_access(self):
        """Test concurrent feature flag access"""
        feature_flags = FraudFeatureFlags()
        
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'concurrent_test': {
                'enabled': True,
                'description': 'Concurrent access test'
            }
        }):
            def check_flag():
                return feature_flags.is_enabled('concurrent_test', user=self.regular_user)
            
            # Run multiple concurrent checks
            threads = []
            results = []
            
            for i in range(10):
                thread = threading.Thread(target=lambda: results.append(check_flag()))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # All results should be consistent
            self.assertEqual(len(results), 10)
            for result in results:
                self.assertTrue(result)
    
    def test_feature_flag_disaster_recovery(self):
        """Test feature flag disaster recovery scenarios"""
        # Test 1: Configuration file missing
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {}):
            feature_flags = FraudFeatureFlags()
            
            # Should return default (disabled) for missing flags
            is_enabled = feature_flags.is_enabled('missing_flag')
            self.assertFalse(is_enabled)
        
        # Test 2: Cache failure
        feature_flags = FraudFeatureFlags()
        
        with patch.object(feature_flags, '_get_cached_result') as mock_cache:
            mock_cache.side_effect = Exception("Cache failure")
            
            with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
                'fallback_test': {
                    'enabled': True,
                    'description': 'Fallback test flag'
                }
            }):
                # Should fall back to direct computation
                is_enabled = feature_flags.is_enabled('fallback_test', user=self.regular_user)
                self.assertTrue(is_enabled)
        
        # Test 3: Invalid configuration
        with patch('api.fraud_detection.feature_flags.FEATURE_FLAGS_CONFIG', {
            'invalid_flag': {
                'enabled': 'not_boolean',  # Invalid type
                'conditions': 'not_a_dict'   # Invalid type
            }
        }):
            # Should handle gracefully and return default
            is_enabled = feature_flags.is_enabled('invalid_flag', user=self.regular_user)
            self.assertFalse(is_enabled)  # Default to disabled

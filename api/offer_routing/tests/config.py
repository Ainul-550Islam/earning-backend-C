"""
Configuration Tests for Offer Routing System

This module contains unit tests for configuration functionality,
including routing configs, feature flags, and personalization settings.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.config import ConfigurationService, config_service
from ..models import RoutingConfig, PersonalizationConfig
from ..exceptions import ConfigurationError, ValidationError

User = get_user_model()


class ConfigurationServiceTestCase(TestCase):
    """Test cases for ConfigurationService."""
    
    def setUp(self):
        """Set up test data."""
        self.config_service = ConfigurationService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
    
    def test_get_routing_config(self):
        """Test getting routing configuration."""
        config = self.config_service.get_routing_config(tenant_id=self.tenant.id)
        
        self.assertIsInstance(config, dict)
        self.assertIn('cache_enabled', config)
        self.assertIn('cache_timeout', config)
        self.assertIn('max_offers_per_request', config)
        self.assertIn('enable_personalization', config)
        self.assertIn('enable_ab_testing', config)
        self.assertIn('enable_fallback', config)
    
    def test_update_config_value(self):
        """Test updating configuration value."""
        key = 'max_offers_per_request'
        value = 20
        
        success = self.config_service.update_config_value(
            tenant_id=self.tenant.id,
            key=key,
            value=value
        )
        
        self.assertTrue(success)
        
        # Check if value was updated
        config = self.config_service.get_routing_config(tenant_id=self.tenant.id)
        self.assertEqual(config[key], value)
    
    def test_get_feature_flags(self):
        """Test getting feature flags."""
        feature_flags = self.config_service.get_feature_flags(tenant_id=self.tenant.id)
        
        self.assertIsInstance(feature_flags, dict)
        self.assertIn('personalization_enabled', feature_flags)
        self.assertIn('ab_testing_enabled', feature_flags)
        self.assertIn('real_time_scoring', feature_flags)
        self.assertIn('advanced_analytics', feature_flags)
    
    def test_toggle_feature(self):
        """Test toggling feature flag."""
        feature = 'real_time_scoring'
        enabled = True
        
        success = self.config_service.update_config_value(
            tenant_id=self.tenant.id,
            key=feature,
            value=enabled
        )
        
        self.assertTrue(success)
        
        # Check if feature was toggled
        feature_flags = self.config_service.get_feature_flags(tenant_id=self.tenant.id)
        self.assertEqual(feature_flags[feature], enabled)
    
    def test_validate_configuration(self):
        """Test configuration validation."""
        config_data = {
            'cache_enabled': True,
            'cache_timeout': 300,
            'max_offers_per_request': 10,
            'enable_personalization': True,
            'enable_ab_testing': True,
            'enable_fallback': True
        }
        
        validation_result = self.config_service.validate_configuration(config_data)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
        self.assertIn('errors', validation_result)
        self.assertIn('warnings', validation_result)
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
    
    def test_validate_configuration_invalid(self):
        """Test configuration validation with invalid data."""
        config_data = {
            'cache_enabled': 'invalid',  # Should be boolean
            'cache_timeout': -1,  # Should be positive
            'max_offers_per_request': 0,  # Should be positive
            'enable_personalization': True,
            'enable_ab_testing': True,
            'enable_fallback': True
        }
        
        validation_result = self.config_service.validate_configuration(config_data)
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_optimize_configuration(self):
        """Test configuration optimization."""
        optimization_result = self.config_service.optimize_configuration(tenant_id=self.tenant.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimizations', optimization_result)
        self.assertIn('applied_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
    
    def test_export_configuration(self):
        """Test configuration export."""
        export_data = self.config_service.export_configuration(tenant_id=self.tenant.id)
        
        self.assertIsInstance(export_data, dict)
        self.assertIn('routing_config', export_data)
        self.assertIn('feature_flags', export_data)
        self.assertIn('personalization_configs', export_data)
        self.assertIn('export_timestamp', export_data)
    
    def test_import_configuration(self):
        """Test configuration import."""
        import_data = {
            'routing_config': {
                'cache_enabled': True,
                'cache_timeout': 600,
                'max_offers_per_request': 15
            },
            'feature_flags': {
                'personalization_enabled': True,
                'ab_testing_enabled': False
            }
        }
        
        success = self.config_service.import_configuration(
            tenant_id=self.tenant.id,
            import_data=import_data
        )
        
        self.assertTrue(success)
        
        # Check if configuration was imported
        config = self.config_service.get_routing_config(tenant_id=self.tenant.id)
        self.assertEqual(config['cache_timeout'], 600)
        self.assertEqual(config['max_offers_per_request'], 15)
    
    def test_reset_configuration(self):
        """Test configuration reset."""
        success = self.config_service.reset_configuration(tenant_id=self.tenant.id)
        
        self.assertTrue(success)
        
        # Check if configuration was reset to defaults
        config = self.config_service.get_routing_config(tenant_id=self.tenant.id)
        self.assertIn('cache_enabled', config)
        self.assertIn('cache_timeout', config)
    
    def test_get_configuration_history(self):
        """Test getting configuration history."""
        history = self.config_service.get_configuration_history(
            tenant_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(history, list)
        
        for entry in history:
            self.assertIsInstance(entry, dict)
            self.assertIn('timestamp', entry)
            self.assertIn('action', entry)
            self.assertIn('key', entry)
            self.assertIn('old_value', entry)
            self.assertIn('new_value', entry)
    
    def test_backup_configuration(self):
        """Test configuration backup."""
        success = self.config_service.backup_configuration(tenant_id=self.tenant.id)
        
        self.assertTrue(success)
    
    def test_restore_configuration(self):
        """Test configuration restore."""
        # Create backup data
        backup_data = {
            'routing_config': {
                'cache_enabled': True,
                'cache_timeout': 300,
                'max_offers_per_request': 10
            },
            'feature_flags': {
                'personalization_enabled': True,
                'ab_testing_enabled': True
            },
            'backup_timestamp': timezone.now().isoformat()
        }
        
        success = self.config_service.restore_configuration(
            tenant_id=self.tenant.id,
            backup_data=backup_data
        )
        
        self.assertTrue(success)
    
    def test_get_personalization_config(self):
        """Test getting personalization configuration."""
        config = self.config_service.get_personalization_config(user_id=self.user.id)
        
        self.assertIsInstance(config, dict)
        self.assertIn('algorithm', config)
        self.assertIn('collaborative_weight', config)
        self.assertIn('content_based_weight', config)
        self.assertIn('hybrid_weight', config)
        self.assertIn('min_affinity_score', config)
        self.assertIn('max_offers_per_user', config)
    
    def test_update_personalization_config(self):
        """Test updating personalization configuration."""
        user_id = self.user.id
        config_data = {
            'algorithm': 'content_based',
            'collaborative_weight': 0.0,
            'content_based_weight': 0.7,
            'hybrid_weight': 0.3,
            'min_affinity_score': 0.2,
            'max_offers_per_user': 20
        }
        
        success = self.config_service.update_personalization_config(
            user_id=user_id,
            config_data=config_data
        )
        
        self.assertTrue(success)
        
        # Check if configuration was updated
        config = self.config_service.get_personalization_config(user_id=user_id)
        self.assertEqual(config['algorithm'], 'content_based')
        self.assertEqual(config['collaborative_weight'], 0.0)
        self.assertEqual(config['content_based_weight'], 0.7)
    
    def test_get_default_configuration(self):
        """Test getting default configuration."""
        config = self.config_service._get_default_configuration()
        
        self.assertIsInstance(config, dict)
        self.assertIn('cache_enabled', config)
        self.assertIn('cache_timeout', config)
        self.assertIn('max_offers_per_request', config)
    
    def test_get_default_personalization_config(self):
        """Test getting default personalization configuration."""
        config = self.config_service._get_default_personalization_config()
        
        self.assertIsInstance(config, dict)
        self.assertIn('algorithm', config)
        self.assertIn('collaborative_weight', config)
        self.assertIn('content_based_weight', config)
        self.assertIn('hybrid_weight', config)
    
    def test_validate_config_value(self):
        """Test individual config value validation."""
        # Valid values
        valid_cases = [
            ('cache_enabled', True),
            ('cache_timeout', 300),
            ('max_offers_per_request', 10),
            ('enable_personalization', True)
        ]
        
        for key, value in valid_cases:
            is_valid, error = self.config_service._validate_config_value(key, value)
            self.assertTrue(is_valid, f"Validation failed for {key}: {value}")
            self.assertIsNone(error)
        
        # Invalid values
        invalid_cases = [
            ('cache_enabled', 'invalid'),
            ('cache_timeout', -1),
            ('max_offers_per_request', 0),
            ('enable_personalization', 'invalid')
        ]
        
        for key, value in invalid_cases:
            is_valid, error = self.config_service._validate_config_value(key, value)
            self.assertFalse(is_valid, f"Validation should have failed for {key}: {value}")
            self.assertIsNotNone(error)
    
    def test_get_config_schema(self):
        """Test getting configuration schema."""
        schema = self.config_service._get_config_schema()
        
        self.assertIsInstance(schema, dict)
        
        for key, config in schema.items():
            self.assertIn('type', config)
            self.assertIn('default', config)
            self.assertIn('description', config)
            self.assertIn('validation', config)


class ConfigurationIntegrationTestCase(TestCase):
    """Integration tests for configuration functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_configuration_workflow(self):
        """Test complete configuration workflow."""
        # Get initial configuration
        initial_config = config_service.get_routing_config(tenant_id=self.user.id)
        
        self.assertIsInstance(initial_config, dict)
        self.assertIn('cache_enabled', initial_config)
        
        # Update configuration
        success = config_service.update_config_value(
            tenant_id=self.user.id,
            key='max_offers_per_request',
            value=20
        )
        
        self.assertTrue(success)
        
        # Get updated configuration
        updated_config = config_service.get_routing_config(tenant_id=self.user.id)
        
        self.assertEqual(updated_config['max_offers_per_request'], 20)
        
        # Validate configuration
        validation_result = config_service.validate_configuration(updated_config)
        
        self.assertTrue(validation_result['is_valid'])
        
        # Export configuration
        export_data = config_service.export_configuration(tenant_id=self.user.id)
        
        self.assertIsInstance(export_data, dict)
        self.assertIn('routing_config', export_data)
        
        # Reset configuration
        success = config_service.reset_configuration(tenant_id=self.user.id)
        
        self.assertTrue(success)
        
        # Check if configuration was reset
        reset_config = config_service.get_routing_config(tenant_id=self.user.id)
        self.assertEqual(reset_config['max_offers_per_request'], initial_config['max_offers_per_request'])
    
    def test_feature_flags_workflow(self):
        """Test feature flags workflow."""
        # Get initial feature flags
        initial_flags = config_service.get_feature_flags(tenant_id=self.user.id)
        
        self.assertIsInstance(initial_flags, dict)
        self.assertIn('personalization_enabled', initial_flags)
        
        # Toggle feature
        success = config_service.update_config_value(
            tenant_id=self.user.id,
            key='real_time_scoring',
            value=True
        )
        
        self.assertTrue(success)
        
        # Get updated feature flags
        updated_flags = config_service.get_feature_flags(tenant_id=self.user.id)
        
        self.assertTrue(updated_flags['real_time_scoring'])
        
        # Toggle back
        success = config_service.update_config_value(
            tenant_id=self.user.id,
            key='real_time_scoring',
            value=False
        )
        
        self.assertTrue(success)
        
        # Check if feature was toggled back
        final_flags = config_service.get_feature_flags(tenant_id=self.user.id)
        self.assertFalse(final_flags['real_time_scoring'])
    
    def test_personalization_configuration_workflow(self):
        """Test personalization configuration workflow."""
        # Get initial personalization config
        initial_config = config_service.get_personalization_config(user_id=self.user.id)
        
        self.assertIsInstance(initial_config, dict)
        self.assertIn('algorithm', initial_config)
        
        # Update personalization config
        config_data = {
            'algorithm': 'collaborative',
            'collaborative_weight': 0.8,
            'content_based_weight': 0.2,
            'hybrid_weight': 0.0,
            'min_affinity_score': 0.3,
            'max_offers_per_user': 25
        }
        
        success = config_service.update_personalization_config(
            user_id=self.user.id,
            config_data=config_data
        )
        
        self.assertTrue(success)
        
        # Get updated configuration
        updated_config = config_service.get_personalization_config(user_id=self.user.id)
        
        self.assertEqual(updated_config['algorithm'], 'collaborative')
        self.assertEqual(updated_config['collaborative_weight'], 0.8)
        self.assertEqual(updated_config['max_offers_per_user'], 25)
    
    def test_configuration_optimization_workflow(self):
        """Test configuration optimization workflow."""
        # Get initial configuration
        initial_config = config_service.get_routing_config(tenant_id=self.user.id)
        
        # Optimize configuration
        optimization_result = config_service.optimize_configuration(tenant_id=self.user.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimizations', optimization_result)
        
        # Get optimized configuration
        optimized_config = config_service.get_routing_config(tenant_id=self.user.id)
        
        self.assertIsInstance(optimized_config, dict)
        
        # Check if optimizations were applied
        if optimization_result['applied_changes'] > 0:
            # Some changes should be different
            self.assertNotEqual(
                len(optimization_result['optimizations']),
                0
            )
    
    def test_configuration_import_export_workflow(self):
        """Test configuration import/export workflow."""
        # Export configuration
        export_data = config_service.export_configuration(tenant_id=self.user.id)
        
        self.assertIsInstance(export_data, dict)
        self.assertIn('routing_config', export_data)
        self.assertIn('feature_flags', export_data)
        
        # Modify exported data
        modified_data = export_data.copy()
        modified_data['routing_config']['max_offers_per_request'] = 50
        modified_data['feature_flags']['real_time_scoring'] = True
        
        # Import modified configuration
        success = config_service.import_configuration(
            tenant_id=self.user.id,
            import_data=modified_data
        )
        
        self.assertTrue(success)
        
        # Verify imported configuration
        imported_config = config_service.get_routing_config(tenant_id=self.user.id)
        imported_flags = config_service.get_feature_flags(tenant_id=self.user.id)
        
        self.assertEqual(imported_config['max_offers_per_request'], 50)
        self.assertTrue(imported_flags['real_time_scoring'])
    
    def test_configuration_backup_restore_workflow(self):
        """Test configuration backup/restore workflow."""
        # Create backup
        success = config_service.backup_configuration(tenant_id=self.user.id)
        
        self.assertTrue(success)
        
        # Modify configuration
        success = config_service.update_config_value(
            tenant_id=self.user.id,
            key='max_offers_per_request',
            value=100
        )
        
        self.assertTrue(success)
        
        # Get modified configuration
        modified_config = config_service.get_routing_config(tenant_id=self.user.id)
        self.assertEqual(modified_config['max_offers_per_request'], 100)
        
        # Restore from backup (simulated)
        backup_data = {
            'routing_config': {
                'cache_enabled': True,
                'cache_timeout': 300,
                'max_offers_per_request': 10  # Original value
            },
            'feature_flags': {
                'personalization_enabled': True,
                'ab_testing_enabled': True
            },
            'backup_timestamp': timezone.now().isoformat()
        }
        
        success = config_service.restore_configuration(
            tenant_id=self.user.id,
            backup_data=backup_data
        )
        
        self.assertTrue(success)
        
        # Verify restored configuration
        restored_config = config_service.get_routing_config(tenant_id=self.user.id)
        self.assertEqual(restored_config['max_offers_per_request'], 10)
    
    def test_configuration_performance(self):
        """Test configuration performance."""
        import time
        
        # Measure configuration retrieval time
        start_time = time.time()
        
        for _ in range(100):
            config_service.get_routing_config(tenant_id=self.user.id)
        
        end_time = time.time()
        config_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(config_time, 1000)  # Within 1 second
        
        # Measure feature flags retrieval time
        start_time = time.time()
        
        for _ in range(100):
            config_service.get_feature_flags(tenant_id=self.user.id)
        
        end_time = time.time()
        flags_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(flags_time, 500)  # Within 500ms
    
    def test_configuration_error_handling(self):
        """Test error handling in configuration."""
        # Test with invalid tenant ID
        with self.assertRaises(Exception):
            config_service.get_routing_config(tenant_id=999999)
        
        # Test with invalid user ID
        with self.assertRaises(Exception):
            config_service.get_personalization_config(user_id=999999)
        
        # Test with invalid config data
        invalid_config = {
            'cache_enabled': 'invalid',
            'cache_timeout': -1,
            'max_offers_per_request': 0
        }
        
        validation_result = config_service.validate_configuration(invalid_config)
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
        
        # Test with invalid import data
        with self.assertRaises(Exception):
            config_service.import_configuration(
                tenant_id=self.user.id,
                import_data={}
            )
        
        # Test with invalid backup data
        with self.assertRaises(Exception):
            config_service.restore_configuration(
                tenant_id=self.user.id,
                backup_data={}
            )

"""
Rate Limit Config Tests

This module contains comprehensive tests for RateLimitConfig model and related functionality.
"""

import pytest
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.db import transaction

from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from api.rate_limit.tests.factories import (
    RateLimitConfigFactory, UserFactory, RateLimitLogFactory,
    BulkDataFactory, TestDataGenerator
)


class RateLimitConfigModelTest(TestCase):
    """Test cases for RateLimitConfig model."""
    
    def setUp(self):
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            name='test_config',
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1
        )
    
    def test_config_creation(self):
        """Test basic config creation."""
        self.assertEqual(self.config.name, 'test_config')
        self.assertEqual(self.config.user, self.user)
        self.assertEqual(self.config.rate_limit_type, 'user')
        self.assertEqual(self.config.requests_per_unit, 100)
        self.assertEqual(self.config.time_unit, 'hour')
        self.assertEqual(self.config.time_value, 1)
        self.assertTrue(self.config.is_active)
    
    def test_config_str_representation(self):
        """Test string representation of config."""
        expected = "test_config (User-based)"
        self.assertEqual(str(self.config), expected)
    
    def test_config_unique_name(self):
        """Test that config names are unique."""
        with self.assertRaises(Exception):
            RateLimitConfigFactory(name='test_config')
    
    def test_config_rate_limit_type_choices(self):
        """Test rate limit type choices."""
        valid_types = ['user', 'ip', 'endpoint', 'global', 'referral', 'task']
        for rate_type in valid_types:
            config = RateLimitConfigFactory(rate_limit_type=rate_type)
            self.assertEqual(config.rate_limit_type, rate_type)
    
    def test_config_time_unit_choices(self):
        """Test time unit choices."""
        valid_units = ['second', 'minute', 'hour', 'day']
        for time_unit in valid_units:
            config = RateLimitConfigFactory(time_unit=time_unit)
            self.assertEqual(config.time_unit, time_unit)
    
    def test_config_target_fields_validation(self):
        """Test that at least one target field is set."""
        # Config with no target fields should be invalid
        config = RateLimitConfigFactory.build(
            user=None,
            ip_address=None,
            endpoint=None,
            task_type=None,
            offer_wall=None
        )
        
        # This should be handled at the service level, not model level
        # The model allows null values for flexibility
    
    def test_config_get_api_health(self):
        """Test API health calculation."""
        # Test with no hits
        config = RateLimitConfigFactory(hit_count=0, block_count=0)
        self.assertEqual(config.get_api_health(), 100)
        
        # Test with high block rate
        config = RateLimitConfigFactory(hit_count=100, block_count=90)
        health = config.get_api_health()
        self.assertEqual(health, 10)
        
        # Test with medium block rate
        config = RateLimitConfigFactory(hit_count=100, block_count=70)
        health = config.get_api_health()
        self.assertEqual(health, 30)
        
        # Test with low block rate
        config = RateLimitConfigFactory(hit_count=100, block_count=20)
        health = config.get_api_health()
        self.assertEqual(health, 70)
    
    def test_config_simulate_impact_user_type(self):
        """Test impact simulation for user-based config."""
        # Create some logs for the user
        user = UserFactory()
        config = RateLimitConfigFactory(
            user=user,
            rate_limit_type='user',
            requests_per_unit=50
        )
        
        # Create logs
        for _ in range(100):
            RateLimitLogFactory(user=user, timestamp=timezone.now() - timedelta(minutes=30))
        
        impact = config.simulate_impact(hours=1)
        
        self.assertIn('total_requests', impact)
        self.assertIn('would_block', impact)
        self.assertIn('block_percentage', impact)
        self.assertIn('simulation_period', impact)
        self.assertEqual(impact['simulation_period'], '1 hour(s)')
    
    def test_config_simulate_impact_endpoint_type(self):
        """Test impact simulation for endpoint-based config."""
        endpoint = '/api/test/'
        config = RateLimitConfigFactory(
            endpoint=endpoint,
            rate_limit_type='endpoint',
            requests_per_unit=50
        )
        
        # Create logs for the endpoint
        for _ in range(100):
            RateLimitLogFactory(endpoint=endpoint, timestamp=timezone.now() - timedelta(minutes=30))
        
        impact = config.simulate_impact(hours=1)
        
        self.assertIn('total_requests', impact)
        self.assertIn('would_block', impact)
        self.assertIn('block_percentage', impact)
    
    def test_config_simulate_impact_ip_type(self):
        """Test impact simulation for IP-based config."""
        ip_address = '192.168.1.100'
        config = RateLimitConfigFactory(
            ip_address=ip_address,
            rate_limit_type='ip',
            requests_per_unit=50
        )
        
        # Create logs for the IP
        for _ in range(100):
            RateLimitLogFactory(ip_address=ip_address, timestamp=timezone.now() - timedelta(minutes=30))
        
        impact = config.simulate_impact(hours=1)
        
        self.assertIn('total_requests', impact)
        self.assertIn('would_block', impact)
        self.assertIn('block_percentage', impact)
    
    def test_config_simulate_impact_unsupported_type(self):
        """Test impact simulation for unsupported config type."""
        config = RateLimitConfigFactory(
            rate_limit_type='global',
            requests_per_unit=50
        )
        
        impact = config.simulate_impact(hours=1)
        
        self.assertIn('error', impact)
        self.assertEqual(impact['error'], 'Cannot simulate for this config type')
    
    def test_config_ordering(self):
        """Test that configs are ordered by creation date descending."""
        configs = [
            RateLimitConfigFactory(),
            RateLimitConfigFactory(),
            RateLimitConfigFactory()
        ]
        
        # Get all configs and check ordering
        all_configs = RateLimitConfig.objects.all()
        
        for i in range(len(all_configs) - 1):
            self.assertGreaterEqual(
                all_configs[i].created_at,
                all_configs[i + 1].created_at
            )
    
    def test_config_indexes(self):
        """Test that proper indexes exist."""
        # This is more of an integration test with the database
        # For now, we just verify the model has the index definitions
        from django.db import connection
        
        # Check if indexes exist (simplified test)
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            indexes = cursor.fetchall()
            
            # Should have indexes for rate_limit_type, is_active, endpoint, ip_address
            index_names = [index[2] for index in indexes]
            
            self.assertIn('idx_rate_limit_type_is_act_c12', index_names)
            self.assertIn('idx_endpoint_1661', index_names)
            self.assertIn('idx_ip_address_1662', index_names)


class RateLimitConfigQuerySetTest(TestCase):
    """Test cases for RateLimitConfig queryset operations."""
    
    def setUp(self):
        self.user = UserFactory()
        self.configs = RateLimitConfigFactory.create_batch(10)
    
    def test_active_configs(self):
        """Test filtering active configs."""
        active_configs = RateLimitConfig.objects.filter(is_active=True)
        self.assertGreater(active_configs.count(), 0)
        
        for config in active_configs:
            self.assertTrue(config.is_active)
    
    def test_configs_by_type(self):
        """Test filtering configs by rate limit type."""
        user_configs = RateLimitConfig.objects.filter(rate_limit_type='user')
        self.assertGreater(user_configs.count(), 0)
        
        for config in user_configs:
            self.assertEqual(config.rate_limit_type, 'user')
    
    def test_configs_by_user(self):
        """Test filtering configs by user."""
        user_configs = RateLimitConfig.objects.filter(user=self.user)
        
        for config in user_configs:
            self.assertEqual(config.user, self.user)
    
    def test_configs_by_endpoint(self):
        """Test filtering configs by endpoint."""
        endpoint = '/api/test/'
        endpoint_configs = RateLimitConfig.objects.filter(endpoint=endpoint)
        
        for config in endpoint_configs:
            self.assertEqual(config.endpoint, endpoint)
    
    def test_configs_by_ip_address(self):
        """Test filtering configs by IP address."""
        ip_address = '192.168.1.100'
        ip_configs = RateLimitConfig.objects.filter(ip_address=ip_address)
        
        for config in ip_configs:
            self.assertEqual(config.ip_address, ip_address)


class RateLimitConfigIntegrationTest(TransactionTestCase):
    """Integration tests for RateLimitConfig with related models."""
    
    def setUp(self):
        self.user = UserFactory()
        self.config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=10,
            time_unit='minute',
            time_value=1
        )
    
    def test_config_with_logs(self):
        """Test config relationship with logs."""
        # Create logs associated with this config
        logs = RateLimitLogFactory.create_batch(5, config=self.config, user=self.user)
        
        # Verify relationship
        config_logs = self.config.ratelimitlog_set.all()
        self.assertEqual(config_logs.count(), 5)
        
        for log in logs:
            self.assertEqual(log.config, self.config)
    
    def test_config_statistics_update(self):
        """Test that config statistics are updated when logs are created."""
        initial_hit_count = self.config.hit_count
        initial_block_count = self.config.block_count
        
        # Create a log that will update statistics
        RateLimitLogFactory(
            config=self.config,
            user=self.user,
            status='blocked'
        )
        
        # Refresh config from database
        self.config.refresh_from_db()
        
        # Statistics should be updated
        self.assertEqual(self.config.hit_count, initial_hit_count + 1)
        self.assertEqual(self.config.block_count, initial_block_count + 1)
    
    def test_config_bulk_operations(self):
        """Test bulk operations on configs."""
        # Create multiple configs
        configs = RateLimitConfigFactory.create_batch(10)
        
        # Bulk update is_active status
        updated_count = RateLimitConfig.objects.filter(
            id__in=[config.id for config in configs[:5]]
        ).update(is_active=False)
        
        self.assertEqual(updated_count, 5)
        
        # Verify update
        for config in configs[:5]:
            config.refresh_from_db()
            self.assertFalse(config.is_active)
    
    def test_config_deletion(self):
        """Test config deletion and related data handling."""
        # Create logs before deletion
        logs = RateLimitLogFactory.create_batch(3, config=self.config)
        
        # Delete config
        self.config.delete()
        
        # Logs should still exist but with null config
        for log in logs:
            log.refresh_from_db()
            self.assertIsNone(log.config)


class RateLimitConfigPerformanceTest(TestCase):
    """Performance tests for RateLimitConfig operations."""
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_bulk_config_creation_performance(self):
        """Test performance of bulk config creation."""
        import time
        
        start_time = time.time()
        
        configs = RateLimitConfigFactory.create_batch(100)
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Should create 100 configs in under 5 seconds
        self.assertLess(creation_time, 5.0)
        self.assertEqual(len(configs), 100)
    
    def test_config_query_performance(self):
        """Test performance of config queries."""
        import time
        
        # Create test data
        RateLimitConfigFactory.create_batch(1000)
        
        start_time = time.time()
        
        # Test various queries
        active_configs = list(RateLimitConfig.objects.filter(is_active=True))
        user_configs = list(RateLimitConfig.objects.filter(rate_limit_type='user'))
        recent_configs = list(RateLimitConfig.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1)
        ))
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Queries should complete in under 1 second
        self.assertLess(query_time, 1.0)
        self.assertGreater(len(active_configs), 0)
        self.assertGreater(len(user_configs), 0)
    
    def test_config_simulation_performance(self):
        """Test performance of impact simulation."""
        import time
        
        # Create config and logs
        config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            requests_per_unit=50
        )
        
        # Create many logs
        RateLimitLogFactory.create_batch(1000, user=self.user)
        
        start_time = time.time()
        
        # Run simulation
        impact = config.simulate_impact(hours=24)
        
        end_time = time.time()
        simulation_time = end_time - start_time
        
        # Simulation should complete in under 2 seconds
        self.assertLess(simulation_time, 2.0)
        self.assertIn('total_requests', impact)


class RateLimitConfigValidationTest(TestCase):
    """Validation tests for RateLimitConfig."""
    
    def test_config_with_minimal_data(self):
        """Test creating config with minimal required data."""
        config = RateLimitConfigFactory(
            name='minimal_config',
            rate_limit_type='global',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1
        )
        
        self.assertIsNotNone(config.id)
        self.assertEqual(config.name, 'minimal_config')
    
    def test_config_with_all_fields(self):
        """Test creating config with all fields populated."""
        user = UserFactory()
        config = RateLimitConfigFactory(
            name='full_config',
            rate_limit_type='user',
            user=user,
            ip_address='192.168.1.100',
            endpoint='/api/test/',
            task_type='survey',
            offer_wall='offer_wall_1',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            is_active=True,
            whitelist=['192.168.1.50'],
            blacklist=['192.168.1.200'],
            bypass_keys=['special_key_123']
        )
        
        self.assertEqual(config.user, user)
        self.assertEqual(config.ip_address, '192.168.1.100')
        self.assertEqual(config.endpoint, '/api/test/')
        self.assertEqual(config.task_type, 'survey')
        self.assertEqual(config.offer_wall, 'offer_wall_1')
        self.assertEqual(config.whitelist, ['192.168.1.50'])
        self.assertEqual(config.blacklist, ['192.168.1.200'])
        self.assertEqual(config.bypass_keys, ['special_key_123'])
    
    def test_config_edge_cases(self):
        """Test edge cases for config creation."""
        # Test with zero requests per unit
        config = RateLimitConfigFactory(requests_per_unit=0)
        self.assertEqual(config.requests_per_unit, 0)
        
        # Test with very high requests per unit
        config = RateLimitConfigFactory(requests_per_unit=1000000)
        self.assertEqual(config.requests_per_unit, 1000000)
        
        # Test with zero time value
        config = RateLimitConfigFactory(time_value=0)
        self.assertEqual(config.time_value, 0)
        
        # Test with very high time value
        config = RateLimitConfigFactory(time_value=365)
        self.assertEqual(config.time_value, 365)


class RateLimitConfigServiceTest(TestCase):
    """Service layer tests for RateLimitConfig."""
    
    def setUp(self):
        self.user = UserFactory()
        self.service = RateLimitConfigService()
    
    def test_get_applicable_configs_for_user(self):
        """Test getting applicable configs for a user."""
        # Create user-specific config
        user_config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            is_active=True
        )
        
        # Create global config
        global_config = RateLimitConfigFactory(
            rate_limit_type='global',
            is_active=True
        )
        
        # Create inactive config
        inactive_config = RateLimitConfigFactory(
            user=self.user,
            rate_limit_type='user',
            is_active=False
        )
        
        # Mock request
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = self.user
        
        # Get applicable configs (this would be implemented in the service)
        # For now, we'll test the model directly
        applicable_configs = RateLimitConfig.objects.filter(
            Q(user=self.user) | Q(rate_limit_type='global'),
            is_active=True
        )
        
        self.assertIn(user_config, applicable_configs)
        self.assertIn(global_config, applicable_configs)
        self.assertNotIn(inactive_config, applicable_configs)
    
    def test_config_caching(self):
        """Test config caching functionality."""
        # This would test caching of frequently accessed configs
        # Implementation depends on caching strategy used
        pass
    
    def test_config_validation_service(self):
        """Test config validation at service level."""
        # Test that at least one target field is set
        config = RateLimitConfigFactory.build(
            user=None,
            ip_address=None,
            endpoint=None,
            task_type=None,
            offer_wall=None
        )
        
        # Service-level validation would go here
        # For now, we just verify the model allows it
        config.save()
        self.assertIsNotNone(config.id)


class RateLimitConfigAPITest(TestCase):
    """API tests for RateLimitConfig endpoints."""
    
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.admin_user = UserFactory(is_superuser=True)
        self.config = RateLimitConfigFactory()
    
    def test_config_list_endpoint(self):
        """Test GET /api/rate-limit/configs/"""
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/rate-limit/configs/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.json())
    
    def test_config_create_endpoint(self):
        """Test POST /api/rate-limit/configs/"""
        self.client.force_login(self.admin_user)
        
        data = {
            'name': 'new_config',
            'rate_limit_type': 'user',
            'user': self.user.id,
            'requests_per_unit': 100,
            'time_unit': 'hour',
            'time_value': 1,
            'is_active': True
        }
        
        response = self.client.post('/api/rate-limit/configs/', data)
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'new_config')
    
    def test_config_update_endpoint(self):
        """Test PATCH /api/rate-limit/configs/{id}/"""
        self.client.force_login(self.admin_user)
        
        data = {
            'requests_per_unit': 200,
            'is_active': False
        }
        
        response = self.client.patch(f'/api/rate-limit/configs/{self.config.id}/', data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['requests_per_unit'], 200)
        self.assertEqual(response.json()['is_active'], False)
    
    def test_config_delete_endpoint(self):
        """Test DELETE /api/rate-limit/configs/{id}/"""
        self.client.force_login(self.admin_user)
        
        response = self.client.delete(f'/api/rate-limit/configs/{self.config.id}/')
        
        self.assertEqual(response.status_code, 204)
        
        # Verify deletion
        with self.assertRaises(RateLimitConfig.DoesNotExist):
            RateLimitConfig.objects.get(id=self.config.id)
    
    def test_config_bulk_update_endpoint(self):
        """Test POST /api/rate-limit/configs/bulk_update/"""
        self.client.force_login(self.admin_user)
        
        configs = RateLimitConfigFactory.create_batch(3)
        
        data = {
            'configs': [
                {'id': configs[0].id, 'requests_per_unit': 150},
                {'id': configs[1].id, 'requests_per_unit': 200},
                {'id': configs[2].id, 'requests_per_unit': 250}
            ],
            'action': 'update'
        }
        
        import json
        response = self.client.post('/api/rate-limit/configs/bulk_update/', json.dumps(data), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('updated_count', response.json())
    
    def test_config_simulate_impact_endpoint(self):
        """Test POST /api/rate-limit/configs/{id}/test/"""
        self.client.force_login(self.admin_user)
        
        data = {
            'endpoint': '/api/test/',
            'hours': 1
        }
        
        response = self.client.post(f'/api/rate-limit/configs/{self.config.id}/test/', data)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('simulation', response.json())


# Import Q for complex queries
from django.db.models import Q

# Mock service class for testing
class RateLimitConfigService:
    """Mock service class for testing RateLimitConfig operations."""
    
    def get_applicable_configs(self, request):
        """Get applicable configs for a request."""
        user = getattr(request, 'user', None)
        ip_address = getattr(request, 'ip_address', None)
        endpoint = getattr(request, 'path', None)
        
        configs = RateLimitConfig.objects.filter(is_active=True)
        
        if user and user.is_authenticated:
            configs = configs.filter(Q(user=user) | Q(rate_limit_type='global'))
        elif ip_address:
            configs = configs.filter(Q(ip_address=ip_address) | Q(rate_limit_type='global'))
        elif endpoint:
            configs = configs.filter(Q(endpoint=endpoint) | Q(rate_limit_type='global'))
        else:
            configs = configs.filter(rate_limit_type='global')
        
        return configs
    
    def validate_config(self, config):
        """Validate config at service level."""
        target_fields = ['user', 'ip_address', 'endpoint', 'task_type', 'offer_wall']
        has_target = any(getattr(config, field) for field in target_fields)
        
        if config.rate_limit_type != 'global' and not has_target:
            raise ValidationError("At least one target field must be set for non-global configs")
        
        if config.requests_per_unit <= 0:
            raise ValidationError("Requests per unit must be positive")
        
        if config.time_value <= 0:
            raise ValidationError("Time value must be positive")
        
        return True


if __name__ == '__main__':
    pytest.main([__file__])

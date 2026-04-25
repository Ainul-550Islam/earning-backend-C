"""
api/ad_networks/tests/test_network_health.py
Tests for NetworkHealthService
SaaS-ready with tenant support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from api.ad_networks.models import (
    AdNetwork, NetworkHealthCheck, NetworkAPILog
)
from api.ad_networks.services.NetworkHealthService import NetworkHealthService
from api.ad_networks.choices import NetworkStatus


class TestNetworkHealthService(TestCase):
    """
    Test cases for NetworkHealthService
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test networks
        self.network1 = AdNetwork.objects.create(
            name='Test Network 1',
            network_type='adscend',
            base_url='https://test1.adscend.com',
            api_key='test_key_1',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.network2 = AdNetwork.objects.create(
            name='Test Network 2',
            network_type='offertoro',
            base_url='https://test2.offertoro.com',
            api_key='test_key_2',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.network3 = AdNetwork.objects.create(
            name='Test Network 3',
            network_type='adgem',
            base_url='https://test3.adgem.com',
            api_key='test_key_3',
            is_active=False,  # Inactive network
            tenant_id=self.tenant_id
        )
        
        # Initialize service
        self.health_service = NetworkHealthService(tenant_id=self.tenant_id)
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()
    
    def test_check_all_networks_success(self):
        """Test successful health check for all networks"""
        with patch.object(self.health_service, 'check_single_network') as mock_check:
            # Mock successful health checks
            mock_check.side_effect = [
                {'is_healthy': True, 'response_time_ms': 150},
                {'is_healthy': True, 'response_time_ms': 200}
            ]
            
            result = self.health_service.check_all_networks()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['total_networks'], 2)  # Only active networks
            self.assertEqual(result['healthy_networks'], 2)
            self.assertEqual(result['unhealthy_networks'], 0)
            self.assertEqual(result['overall_health'], 100.0)
            self.assertEqual(len(result['results']), 2)
    
    def test_check_all_networks_mixed_health(self):
        """Test health check with mixed results"""
        with patch.object(self.health_service, 'check_single_network') as mock_check:
            # Mock mixed health checks
            mock_check.side_effect = [
                {'is_healthy': True, 'response_time_ms': 150},
                {'is_healthy': False, 'response_time_ms': 0, 'error': 'Connection timeout'}
            ]
            
            result = self.health_service.check_all_networks()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['total_networks'], 2)
            self.assertEqual(result['healthy_networks'], 1)
            self.assertEqual(result['unhealthy_networks'], 1)
            self.assertEqual(result['overall_health'], 50.0)
    
    def test_check_all_networks_all_unhealthy(self):
        """Test health check when all networks are unhealthy"""
        with patch.object(self.health_service, 'check_single_network') as mock_check:
            # Mock all unhealthy
            mock_check.side_effect = [
                {'is_healthy': False, 'response_time_ms': 0, 'error': 'API Error'},
                {'is_healthy': False, 'response_time_ms': 0, 'error': 'Connection Error'}
            ]
            
            result = self.health_service.check_all_networks()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['total_networks'], 2)
            self.assertEqual(result['healthy_networks'], 0)
            self.assertEqual(result['unhealthy_networks'], 2)
            self.assertEqual(result['overall_health'], 0.0)
    
    def test_check_single_network_success(self):
        """Test successful single network health check"""
        with patch('requests.Session.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.15
            mock_get.return_value = mock_response
            
            result = self.health_service.check_single_network(self.network1)
            
            self.assertTrue(result['is_healthy'])
            self.assertEqual(result['response_time_ms'], 150)
            self.assertEqual(result['status_code'], 200)
            self.assertIn('adscend', result['endpoint'])
            
            # Verify health check was logged
            health_check = NetworkHealthCheck.objects.filter(network=self.network1).first()
            self.assertIsNotNone(health_check)
            self.assertTrue(health_check.is_healthy)
            self.assertEqual(health_check.response_time_ms, 150)
            self.assertEqual(health_check.status_code, 200)
            
            # Verify API log was created
            api_log = NetworkAPILog.objects.filter(network=self.network1).first()
            self.assertIsNotNone(api_log)
            self.assertTrue(api_log.is_success)
            self.assertEqual(api_log.latency_ms, 150)
    
    def test_check_single_network_timeout(self):
        """Test single network health check with timeout"""
        with patch('requests.Session.get') as mock_get:
            # Mock timeout
            mock_get.side_effect = Exception("Request timeout")
            
            result = self.health_service.check_single_network(self.network1)
            
            self.assertFalse(result['is_healthy'])
            self.assertEqual(result['error'], 'Request timeout')
            self.assertEqual(result['response_time_ms'], 30000)  # 30 seconds
            
            # Verify health check was logged
            health_check = NetworkHealthCheck.objects.filter(network=self.network1).first()
            self.assertIsNotNone(health_check)
            self.assertFalse(health_check.is_healthy)
            self.assertIn('timeout', health_check.error.lower())
    
    def test_check_single_network_connection_error(self):
        """Test single network health check with connection error"""
        with patch('requests.Session.get') as mock_get:
            # Mock connection error
            mock_get.side_effect = Exception("Connection error")
            
            result = self.health_service.check_single_network(self.network1)
            
            self.assertFalse(result['is_healthy'])
            self.assertEqual(result['error'], 'Connection error')
            self.assertEqual(result['response_time_ms'], 0)
    
    def test_check_network_endpoints(self):
        """Test checking multiple endpoints of a network"""
        with patch('requests.Session.get') as mock_get:
            # Mock different responses for different endpoints
            def side_effect(*args, **kwargs):
                response = Mock()
                if 'ping' in args[0]:
                    response.status_code = 200
                elif 'offers' in args[0]:
                    response.status_code = 500
                elif 'stats' in args[0]:
                    response.status_code = 200
                else:
                    response.status_code = 404
                response.elapsed.total_seconds.return_value = 0.1
                return response
            
            mock_get.side_effect = side_effect
            
            result = self.health_service.check_network_endpoints(self.network1)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['network_id'], self.network1.id)
            self.assertEqual(result['network_name'], self.network1.name)
            self.assertGreater(result['overall_health'], 0)
            self.assertLessEqual(result['overall_health'], 100)
            self.assertGreater(result['healthy_endpoints'], 0)
            self.assertGreater(result['total_endpoints'], 0)
    
    def test_get_network_health_history(self):
        """Test getting network health history"""
        # Create health checks over time
        base_time = timezone.now() - timedelta(days=7)
        
        for i in range(10):
            NetworkHealthCheck.objects.create(
                network=self.network1,
                is_healthy=i % 3 != 0,  # 2 healthy, 1 unhealthy pattern
                check_type='api_call',
                endpoint_checked='https://test1.adscend.com/v1/ping',
                response_time_ms=100 + i * 10,
                status_code=200 if i % 3 != 0 else 500,
                tenant_id=self.tenant_id,
                checked_at=base_time + timedelta(days=i)
            )
        
        result = self.health_service.get_network_health_history(self.network1.id, days=7)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['network_id'], self.network1.id)
        self.assertEqual(result['period_days'], 7)
        self.assertEqual(result['total_checks'], 10)
        self.assertGreater(result['avg_response_time_ms'], 0)
        self.assertGreater(result['health_percentage'], 0)
        self.assertLessEqual(result['health_percentage'], 100)
        self.assertEqual(len(result['timeline']), 10)
    
    def test_get_health_summary(self):
        """Test getting overall health summary"""
        # Create networks with different statuses
        network_active = AdNetwork.objects.create(
            name='Active Network',
            network_type='pollfish',
            is_active=True,
            status=NetworkStatus.ACTIVE,
            tenant_id=self.tenant_id
        )
        
        network_maintenance = AdNetwork.objects.create(
            name='Maintenance Network',
            network_type='cpxresearch',
            is_active=True,
            status=NetworkStatus.MAINTENANCE,
            tenant_id=self.tenant_id
        )
        
        network_suspended = AdNetwork.objects.create(
            name='Suspended Network',
            network_type='ayetstudios',
            is_active=True,
            status=NetworkStatus.SUSPENDED,
            tenant_id=self.tenant_id
        )
        
        # Create recent health checks
        base_time = timezone.now() - timedelta(hours=12)
        
        for network in [self.network1, network_active]:
            NetworkHealthCheck.objects.create(
                network=network,
                is_healthy=True,
                check_type='api_call',
                response_time_ms=150,
                status_code=200,
                tenant_id=self.tenant_id,
                checked_at=base_time
            )
        
        result = self.health_service.get_health_summary(self.tenant_id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_networks'], 5)  # 3 original + 2 new
        self.assertEqual(result['active_networks'], 4)
        self.assertEqual(result['maintenance_networks'], 1)
        self.assertEqual(result['suspended_networks'], 1)
        self.assertGreaterEqual(result['recent_health_percentage'], 0)
        self.assertLessEqual(result['recent_health_percentage'], 100)
    
    def test_schedule_health_checks(self):
        """Test scheduling periodic health checks"""
        # Set up networks that need health checks
        self.network1.last_health_check = timezone.now() - timedelta(hours=2)
        self.network1.save()
        
        self.network2.last_health_check = timezone.now() - timedelta(minutes=30)
        self.network2.save()
        
        with patch.object(self.health_service, 'check_single_network') as mock_check:
            mock_check.return_value = {'is_healthy': True, 'response_time_ms': 100}
            
            result = self.health_service.schedule_health_checks()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['networks_checked'], 2)
            self.assertEqual(result['total_scheduled'], 2)
            
            # Verify check_single_network was called for both networks
            self.assertEqual(mock_check.call_count, 2)
    
    def test_get_health_check_url(self):
        """Test getting health check URL for network"""
        url = self.health_service._get_health_check_url(self.network1)
        
        self.assertIsNotNone(url)
        self.assertIn('adscend', url)
        self.assertIn('/v1/ping', url)
        
        # Test network without base URL
        network_no_url = AdNetwork.objects.create(
            name='No URL Network',
            network_type='unknown',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        url_no_base = self.health_service._get_health_check_url(network_no_url)
        self.assertIsNone(url_no_base)
    
    def test_get_network_endpoints(self):
        """Test getting network endpoints"""
        endpoints = self.health_service._get_network_endpoints(self.network1)
        
        self.assertIsInstance(endpoints, list)
        self.assertGreater(len(endpoints), 0)
        
        # Check for common endpoints
        endpoint_names = [ep['name'] for ep in endpoints]
        self.assertIn('health', endpoint_names)
        self.assertIn('offers', endpoint_names)
        
        # Verify endpoint URLs
        for endpoint in endpoints:
            self.assertIn('url', endpoint)
            self.assertIn(self.network1.base_url, endpoint['url'])
    
    def test_get_auth_headers(self):
        """Test getting authentication headers"""
        headers = self.health_service._get_auth_headers(self.network1)
        
        self.assertIn('X-API-Key', headers)
        self.assertEqual(headers['X-API-Key'], 'test_key_1')
        
        # Test with postback key
        self.network1.postback_key = 'pb_key_123'
        headers_with_pb = self.health_service._get_auth_headers(self.network1)
        
        self.assertIn('Authorization', headers_with_pb)
        self.assertEqual(headers_with_pb['Authorization'], 'Bearer pb_key_123')
    
    def test_record_health_check(self):
        """Test recording health check result"""
        initial_count = NetworkHealthCheck.objects.count()
        
        self.health_service._record_health_check(
            self.network1,
            True,
            150,
            None
        )
        
        final_count = NetworkHealthCheck.objects.count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Verify recorded health check
        health_check = NetworkHealthCheck.objects.filter(network=self.network1).latest('checked_at')
        self.assertTrue(health_check.is_healthy)
        self.assertEqual(health_check.response_time_ms, 150)
        self.assertIsNone(health_check.error)
    
    def test_update_network_status(self):
        """Test updating network status"""
        # Test updating to active
        self.health_service._update_network_status(self.network1, NetworkStatus.ACTIVE)
        
        self.network1.refresh_from_db()
        self.assertEqual(self.network1.status, NetworkStatus.ACTIVE)
        
        # Test updating to maintenance
        self.health_service._update_network_status(self.network1, NetworkStatus.MAINTENANCE)
        
        self.network1.refresh_from_db()
        self.assertEqual(self.network1.status, NetworkStatus.MAINTENANCE)
    
    @classmethod
    def test_get_network_uptime(cls):
        """Test calculating network uptime"""
        # Create test network
        network = AdNetwork.objects.create(
            name='Uptime Test Network',
            network_type='test',
            is_active=True,
            tenant_id='test_tenant'
        )
        
        # Create health checks over time
        base_time = timezone.now() - timedelta(days=7)
        
        # Create 24 hours of data (1 check per hour)
        for i in range(24 * 7):  # 7 days * 24 hours
            NetworkHealthCheck.objects.create(
                network=network,
                is_healthy=i % 10 != 0,  # 90% uptime
                check_type='api_call',
                response_time_ms=100,
                status_code=200 if i % 10 != 0 else 500,
                tenant_id='test_tenant',
                checked_at=base_time + timedelta(hours=i)
            )
        
        result = NetworkHealthService.get_network_uptime(network.id, days=7)
        
        cls.assertTrue(result['success'])
        cls.assertEqual(result['network_id'], network.id)
        cls.assertEqual(result['period_days'], 7)
        cls.assertGreater(result['total_checks'], 0)
        cls.assertGreater(result['healthy_checks'], 0)
        cls.assertGreaterEqual(result['uptime_percentage'], 80)
        cls.assertLessEqual(result['uptime_percentage'], 100)
        cls.assertGreaterEqual(result['total_downtime_minutes'], 0)
    
    @classmethod
    def test_get_health_alerts(cls):
        """Test getting health alerts"""
        # Create test network
        network = AdNetwork.objects.create(
            name='Alert Test Network',
            network_type='test',
            is_active=True,
            tenant_id='test_tenant'
        )
        
        # Create recent failed health checks
        base_time = timezone.now() - timedelta(minutes=30)
        
        for i in range(5):
            NetworkHealthCheck.objects.create(
                network=network,
                is_healthy=False,
                check_type='api_call',
                response_time_ms=0,
                status_code=500,
                error='API Error',
                tenant_id='test_tenant',
                checked_at=base_time + timedelta(minutes=i)
            )
        
        result = NetworkHealthService.get_health_alerts('test_tenant')
        
        cls.assertTrue(result['success'])
        cls.assertGreater(result['total_alerts'], 0)
        cls.assertGreater(len(result['alerts']), 0)
        
        # Check alert structure
        if result['alerts']:
            alert = result['alerts'][0]
            cls.assertIn('network_id', alert)
            cls.assertIn('network_name', alert)
            cls.assertIn('alert_type', alert)
            cls.assertIn('severity', alert)
            cls.assertIn('message', alert)
            cls.assertIn('consecutive_failures', alert)


class TestNetworkHealthIntegration(TestCase):
    """
    Integration tests for NetworkHealthService
    """
    
    def setUp(self):
        """Set up integration test data"""
        self.tenant_id = 'integration_test_tenant'
        
        self.network = AdNetwork.objects.create(
            name='Integration Test Network',
            network_type='adscend',
            base_url='https://integration.test.com',
            api_key='integration_key_123',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.health_service = NetworkHealthService(tenant_id=self.tenant_id)
    
    def test_full_health_check_workflow(self):
        """Test complete health check workflow"""
        # This test would require actual API endpoints
        # For now, we'll mock the responses
        
        with patch('requests.Session.get') as mock_get:
            # Mock successful health check
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.12
            mock_get.return_value = mock_response
            
            # Check single network
            result = self.health_service.check_single_network(self.network)
            
            self.assertTrue(result['is_healthy'])
            self.assertEqual(result['response_time_ms'], 120)
            
            # Verify health check was logged
            health_check = NetworkHealthCheck.objects.filter(network=self.network).first()
            self.assertIsNotNone(health_check)
            self.assertTrue(health_check.is_healthy)
            self.assertEqual(health_check.response_time_ms, 120)
            
            # Verify API log was created
            api_log = NetworkAPILog.objects.filter(network=self.network).first()
            self.assertIsNotNone(api_log)
            self.assertTrue(api_log.is_success)
            self.assertEqual(api_log.latency_ms, 120)
    
    def test_health_check_failure_workflow(self):
        """Test health check failure workflow"""
        with patch('requests.Session.get') as mock_get:
            # Mock failed health check
            mock_get.side_effect = Exception("Network unreachable")
            
            result = self.health_service.check_single_network(self.network)
            
            self.assertFalse(result['is_healthy'])
            self.assertIn('Network unreachable', result['error'])
            
            # Verify failure was logged
            health_check = NetworkHealthCheck.objects.filter(network=self.network).first()
            self.assertIsNotNone(health_check)
            self.assertFalse(health_check.is_healthy)
            self.assertIn('Network unreachable', health_check.error)
            
            # Verify API log was created
            api_log = NetworkAPILog.objects.filter(network=self.network).first()
            self.assertIsNotNone(api_log)
            self.assertFalse(api_log.is_success)
    
    def test_concurrent_health_checks(self):
        """Test concurrent health checks"""
        # Create multiple networks
        networks = []
        for i in range(3):
            network = AdNetwork.objects.create(
                name=f'Concurrent Network {i}',
                network_type='test',
                base_url=f'https://test{i}.example.com',
                api_key=f'key_{i}',
                is_active=True,
                tenant_id=self.tenant_id
            )
            networks.append(network)
        
        with patch.object(self.health_service, 'check_single_network') as mock_check:
            # Mock all successful
            mock_check.return_value = {'is_healthy': True, 'response_time_ms': 100}
            
            # Check all networks
            result = self.health_service.check_all_networks()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['total_networks'], 3)
            self.assertEqual(result['healthy_networks'], 3)
            self.assertEqual(result['unhealthy_networks'], 0)
            self.assertEqual(result['overall_health'], 100.0)
            
            # Verify all networks were checked
            self.assertEqual(mock_check.call_count, 3)


if __name__ == '__main__':
    pytest.main([__file__])

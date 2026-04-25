"""
api/ad_networks/tests/test_offer_sync.py
Tests for OfferSyncService
SaaS-ready with tenant support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from api.ad_networks.models import AdNetwork, Offer, NetworkAPILog, NetworkHealthCheck
from api.ad_networks.services.OfferSyncService import OfferSyncService
from api.ad_networks.choices import NetworkStatus, OfferStatus
from api.ad_networks.exceptions import NetworkUnavailableException


class TestOfferSyncService(TestCase):
    """
    Test cases for OfferSyncService
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test network
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            base_url='https://test.adscend.com',
            api_key='test_api_key_123',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        # Create test offer
        self.offer = Offer.objects.create(
            ad_network=self.network,
            external_id='test_offer_123',
            title='Test Offer',
            reward_amount=Decimal('5.00'),
            status=OfferStatus.ACTIVE,
            tenant_id=self.tenant_id
        )
        
        # Initialize service
        self.sync_service = OfferSyncService(
            network=self.network,
            tenant_id=self.tenant_id
        )
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()
    
    def test_sync_all_offers_success(self):
        """Test successful offer sync"""
        # Mock successful API response
        mock_offers_data = [
            {
                'external_id': 'offer_1',
                'title': 'Test Offer 1',
                'reward_amount': 5.00,
                'is_available': True,
                'description': 'Test description 1'
            },
            {
                'external_id': 'offer_2',
                'title': 'Test Offer 2',
                'reward_amount': 10.00,
                'is_available': True,
                'description': 'Test description 2'
            }
        ]
        
        with patch.object(self.sync_service, '_fetch_offers_from_api') as mock_fetch:
            mock_fetch.return_value = mock_offers_data
            
            with patch.object(self.sync_service, '_check_network_health') as mock_health:
                mock_health.return_value = True
                
                result = self.sync_service.sync_all_offers()
                
                self.assertTrue(result['success'])
                self.assertEqual(result['offers_synced'], 2)
                self.assertEqual(result['offers_created'], 2)
                self.assertEqual(result['offers_updated'], 0)
                self.assertEqual(result['offers_failed'], 0)
    
    def test_sync_all_offers_network_unhealthy(self):
        """Test sync when network is unhealthy"""
        with patch.object(self.sync_service, '_check_network_health') as mock_health:
            mock_health.return_value = False
            
            result = self.sync_service.sync_all_offers()
            
            self.assertFalse(result['success'])
            self.assertIn('Network health check failed', result['error'])
            self.assertEqual(result['offers_synced'], 0)
    
    def test_sync_all_offers_api_error(self):
        """Test sync when API returns error"""
        with patch.object(self.sync_service, '_check_network_health') as mock_health:
            mock_health.return_value = True
            
            with patch.object(self.sync_service, '_fetch_offers_from_api') as mock_fetch:
                mock_fetch.side_effect = Exception("API Error")
                
                result = self.sync_service.sync_all_offers()
                
                self.assertFalse(result['success'])
                self.assertIn('API Error', result['error'])
    
    def test_sync_all_offers_no_offers(self):
        """Test sync when no offers available"""
        with patch.object(self.sync_service, '_check_network_health') as mock_health:
            mock_health.return_value = True
            
            with patch.object(self.sync_service, '_fetch_offers_from_api') as mock_fetch:
                mock_fetch.return_value = []
                
                result = self.sync_service.sync_all_offers()
                
                self.assertTrue(result['success'])
                self.assertEqual(result['offers_synced'], 0)
                self.assertIn('No offers available', result['message'])
    
    def test_sync_single_offer_success(self):
        """Test successful single offer sync"""
        mock_offer_data = {
            'external_id': 'single_offer',
            'title': 'Single Test Offer',
            'reward_amount': 7.50,
            'is_available': True
        }
        
        with patch.object(self.sync_service, '_fetch_single_offer_from_api') as mock_fetch:
            mock_fetch.return_value = mock_offer_data
            
            result = self.sync_service.sync_single_offer('single_offer')
            
            self.assertTrue(result['success'])
            self.assertTrue(result['created'])
            self.assertEqual(result['offer_id'], self.offer.id + 1)  # New offer created
    
    def test_sync_single_offer_not_found(self):
        """Test single offer sync when offer not found"""
        with patch.object(self.sync_service, '_fetch_single_offer_from_api') as mock_fetch:
            mock_fetch.return_value = None
            
            result = self.sync_service.sync_single_offer('nonexistent_offer')
            
            self.assertFalse(result['success'])
            self.assertIn('not found', result['error'])
    
    def test_process_offers_data_new_offer(self):
        """Test processing offers data for new offer"""
        offers_data = [
            {
                'external_id': 'new_offer',
                'title': 'New Test Offer',
                'reward_amount': 8.00,
                'is_available': True,
                'description': 'New test offer'
            }
        ]
        
        result = self.sync_service._process_offers_data(offers_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['offers_created'], 1)
        self.assertEqual(result['offers_updated'], 0)
        self.assertEqual(result['offers_synced'], 1)
    
    def test_process_offers_data_existing_offer(self):
        """Test processing offers data for existing offer"""
        offers_data = [
            {
                'external_id': 'test_offer_123',  # Existing offer
                'title': 'Updated Test Offer',
                'reward_amount': 6.00,  # Different amount
                'is_available': True,
                'description': 'Updated description'
            }
        ]
        
        result = self.sync_service._process_offers_data(offers_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['offers_created'], 0)
        self.assertEqual(result['offers_updated'], 1)
        self.assertEqual(result['offers_synced'], 1)
    
    def test_prepare_offer_fields(self):
        """Test offer fields preparation"""
        offer_data = {
            'title': 'Test Offer',
            'description': 'Test description',
            'reward_amount': 5.50,
            'payout': 4.00,
            'is_available': True,
            'expires_at': '2024-12-31T23:59:59Z',
            'countries': ['US', 'GB', 'CA'],
            'platforms': ['android', 'ios'],
            'difficulty': 'medium',
            'estimated_time': 15,
            'is_featured': True,
            'metadata': {'key': 'value'}
        }
        
        fields = self.sync_service._prepare_offer_fields(offer_data)
        
        self.assertEqual(fields['title'], 'Test Offer')
        self.assertEqual(fields['description'], 'Test description')
        self.assertEqual(fields['reward_amount'], Decimal('5.50'))
        self.assertEqual(fields['network_payout'], Decimal('4.00'))
        self.assertEqual(fields['status'], 'active')
        self.assertTrue(fields['is_featured'])
        self.assertEqual(fields['countries'], ['US', 'GB', 'CA'])
        self.assertEqual(fields['platforms'], ['android', 'ios'])
        self.assertEqual(fields['difficulty'], 'medium')
        self.assertEqual(fields['estimated_time'], 15)
    
    def test_parse_datetime_iso_format(self):
        """Test datetime parsing for ISO format"""
        iso_datetime = '2024-12-31T23:59:59Z'
        
        parsed = self.sync_service._parse_datetime(iso_datetime)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
    
    def test_parse_datetime_unix_timestamp(self):
        """Test datetime parsing for Unix timestamp"""
        unix_timestamp = '1704067999'  # 2024-12-31 23:59:59 UTC
        
        parsed = self.sync_service._parse_datetime(unix_timestamp)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
    
    def test_parse_datetime_invalid(self):
        """Test datetime parsing for invalid format"""
        invalid_datetime = 'invalid_datetime'
        
        parsed = self.sync_service._parse_datetime(invalid_datetime)
        
        self.assertIsNone(parsed)
    
    def test_update_network_sync_status(self):
        """Test network sync status update"""
        initial_sync = self.network.last_sync
        
        self.sync_service._update_network_sync_status(5)
        
        self.network.refresh_from_db()
        self.assertIsNotNone(self.network.last_sync)
        self.assertNotEqual(self.network.last_sync, initial_sync)
        self.assertIsNotNone(self.network.next_sync)
    
    def test_clear_relevant_caches(self):
        """Test cache clearing"""
        # Set some test cache values
        cache.set('network_123_offers', 'test_value')
        cache.set('offer_list_test', 'test_value')
        cache.set('category_test_offers', 'test_value')
        
        self.sync_service._clear_relevant_caches()
        
        self.assertIsNone(cache.get('network_123_offers'))
        self.assertIsNone(cache.get('offer_list_test'))
        self.assertIsNone(cache.get('category_test_offers'))
    
    def test_get_offers_url(self):
        """Test getting offers URL for network"""
        url = self.sync_service._get_offers_url()
        
        self.assertIsNotNone(url)
        self.assertIn('adscend', url)
        self.assertIn('/v1/offers', url)
    
    def test_get_health_check_url(self):
        """Test getting health check URL"""
        url = self.sync_service._get_health_check_url()
        
        self.assertIsNotNone(url)
        self.assertIn('adscend', url)
        self.assertIn('/v1/ping', url)
    
    def test_log_api_error(self):
        """Test API error logging"""
        error_message = 'Test API error'
        
        initial_log_count = NetworkAPILog.objects.count()
        self.sync_service._log_api_error('test_operation', error_message)
        
        final_log_count = NetworkAPILog.objects.count()
        self.assertEqual(final_log_count, initial_log_count + 1)
        
        # Check the logged error
        log_entry = NetworkAPILog.objects.latest('request_timestamp')
        self.assertEqual(log_entry.network, self.network)
        self.assertEqual(log_entry.endpoint, 'test_operation')
        self.assertEqual(log_entry.error_message, error_message)
        self.assertFalse(log_entry.is_success)
    
    @patch('api.ad_networks.services.OfferSyncService.OfferSyncService')
    def test_sync_network_by_type(self, mock_service_class):
        """Test syncing networks by type"""
        # Create another network of same type
        network2 = AdNetwork.objects.create(
            name='Test Network 2',
            network_type='adscend',
            base_url='https://test2.adscend.com',
            api_key='test_api_key_456',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        # Mock the service instance
        mock_instance = Mock()
        mock_instance.sync_all_offers.return_value = {
            'success': True,
            'offers_synced': 3
        }
        mock_service_class.return_value = mock_instance
        
        # Call the class method
        result = OfferSyncService.sync_network_by_type('adscend', self.tenant_id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['network_type'], 'adscend')
        self.assertEqual(result['networks_processed'], 2)
        self.assertEqual(result['total_offers_synced'], 6)  # 3 * 2 networks
    
    def test_get_sync_status(self):
        """Test getting sync status"""
        # Set a specific sync time
        test_sync_time = timezone.now() - timedelta(hours=2)
        self.network.last_sync = test_sync_time
        self.network.next_sync = test_sync_time + timedelta(hours=1)
        self.network.save()
        
        status = OfferSyncService.get_sync_status(self.network.id)
        
        self.assertEqual(status['network_id'], self.network.id)
        self.assertEqual(status['network_name'], self.network.name)
        self.assertEqual(status['is_sync_due'], True)  # Should be due
        self.assertEqual(status['sync_overdue_minutes'], 60)  # 1 hour overdue


class TestOfferSyncServiceIntegration(TestCase):
    """
    Integration tests for OfferSyncService
    """
    
    def setUp(self):
        """Set up integration test data"""
        self.tenant_id = 'integration_test_tenant'
        
        # Create test network with real-like configuration
        self.network = AdNetwork.objects.create(
            name='Integration Test Network',
            network_type='adscend',
            base_url='https://integration.test.com',
            api_key='integration_key_123',
            postback_key='pb_key_123',
            supports_postback=True,
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.sync_service = OfferSyncService(
            network=self.network,
            tenant_id=self.tenant_id
        )
    
    def test_full_sync_workflow(self):
        """Test complete sync workflow"""
        # This test would require actual API endpoints
        # For now, we'll mock the API responses
        
        mock_api_response = {
            'offers': [
                {
                    'id': 1,
                    'title': 'Integration Test Offer 1',
                    'description': 'Test offer 1',
                    'payout': 5.00,
                    'countries': ['US', 'GB'],
                    'platforms': ['android', 'ios']
                },
                {
                    'id': 2,
                    'title': 'Integration Test Offer 2',
                    'description': 'Test offer 2',
                    'payout': 10.00,
                    'countries': ['CA', 'AU'],
                    'platforms': ['web']
                }
            ]
        }
        
        with patch('requests.Session.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_response['offers']
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_get.return_value = mock_response
            
            result = self.sync_service.sync_all_offers()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['offers_synced'], 2)
            
            # Verify offers were created in database
            offers = Offer.objects.filter(ad_network=self.network)
            self.assertEqual(offers.count(), 2)
            
            # Verify specific offer data
            offer1 = offers.get(external_id='1')
            self.assertEqual(offer1.title, 'Integration Test Offer 1')
            self.assertEqual(offer1.reward_amount, Decimal('5.00'))
    
    def test_error_handling_workflow(self):
        """Test error handling in sync workflow"""
        with patch('requests.Session.get') as mock_get:
            # Mock network error
            mock_get.side_effect = Exception("Network unreachable")
            
            result = self.sync_service.sync_all_offers()
            
            self.assertFalse(result['success'])
            self.assertIn('Network unreachable', result['error'])
            
            # Verify error was logged
            error_logs = NetworkAPILog.objects.filter(
                network=self.network,
                is_success=False
            )
            self.assertEqual(error_logs.count(), 1)
    
    def test_concurrent_sync_handling(self):
        """Test handling of concurrent sync attempts"""
        # This would test thread safety in a real scenario
        # For now, we'll test the basic logic
        
        with patch.object(self.sync_service, '_check_network_health') as mock_health:
            mock_health.return_value = True
            
            # Simulate multiple sync attempts
            result1 = self.sync_service.sync_all_offers()
            result2 = self.sync_service.sync_all_offers()
            
            # Both should succeed (no locking in current implementation)
            self.assertTrue(result1['success'])
            self.assertTrue(result2['success'])


if __name__ == '__main__':
    pytest.main([__file__])

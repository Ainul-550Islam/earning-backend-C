"""
api/ad_networks/tests/test_api_views.py
Tests for API views
SaaS-ready with tenant support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from api.ad_networks.models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, OfferCategory
)
from api.ad_networks.choices import (
    NetworkStatus, OfferStatus, EngagementStatus,
    ConversionStatus, RewardStatus
)
from api.ad_networks.serializers import (
    OfferClickSerializer, OfferRewardSerializer,
    NetworkHealthSerializer, AdminAdNetworkSerializer
)


class TestOfferViews(APITestCase):
    """
    Test cases for Offer API views
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        # Create test network and offer
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.category = OfferCategory.objects.create(
            name='Test Category',
            slug='test-category',
            is_active=True
        )
        
        self.offer = Offer.objects.create(
            ad_network=self.network,
            category=self.category,
            external_id='test_offer_123',
            title='Test Offer',
            description='Test offer description',
            reward_amount=Decimal('10.00'),
            status=OfferStatus.ACTIVE,
            countries=['US', 'GB', 'CA'],
            platforms=['android', 'ios'],
            tenant_id=self.tenant_id
        )
        
        # Create user wallet
        self.wallet = UserWallet.objects.create(
            user=self.user,
            balance=Decimal('100.00'),
            total_earned=Decimal('500.00'),
            currency='USD',
            tenant_id=self.tenant_id
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_offer_list_success(self):
        """Test successful offer list retrieval"""
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        offer_data = response.data['results'][0]
        self.assertEqual(offer_data['title'], 'Test Offer')
        self.assertEqual(offer_data['reward_amount'], '10.00')
        self.assertEqual(offer_data['status'], OfferStatus.ACTIVE)
    
    def test_offer_list_with_filters(self):
        """Test offer list with filters"""
        url = reverse('offer-list')
        
        # Test status filter
        response = self.client.get(url, {'status': 'active'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test category filter
        response = self.client.get(url, {'category': 'test-category'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test min_reward filter
        response = self.client.get(url, {'min_reward': '5.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test max_reward filter (should return none)
        response = self.client.get(url, {'max_reward': '5.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_offer_detail_success(self):
        """Test successful offer detail retrieval"""
        url = reverse('offer-detail', kwargs={'pk': self.offer.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        offer_data = response.data
        self.assertEqual(offer_data['title'], 'Test Offer')
        self.assertEqual(offer_data['description'], 'Test offer description')
        self.assertEqual(offer_data['reward_amount'], '10.00')
        self.assertEqual(offer_data['countries'], ['US', 'GB', 'CA'])
        self.assertEqual(offer_data['platforms'], ['android', 'ios'])
    
    def test_offer_detail_not_found(self):
        """Test offer detail for non-existent offer"""
        url = reverse('offer-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_offer_click_tracking(self):
        """Test offer click tracking"""
        url = reverse('offer-click', kwargs={'pk': self.offer.id})
        click_data = {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'device': 'desktop',
            'country': 'US'
        }
        
        response = self.client.post(url, click_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify click was created
        from api.ad_networks.models import OfferClick
        click = OfferClick.objects.filter(offer=self.offer, user=self.user).first()
        self.assertIsNotNone(click)
        self.assertEqual(click.ip_address, '192.168.1.100')
        self.assertEqual(click.device, 'desktop')
        self.assertEqual(click.country, 'US')
    
    def test_offer_engagement_create(self):
        """Test creating offer engagement"""
        url = reverse('offer-engage', kwargs={'pk': self.offer.id})
        engagement_data = {
            'ip_address': '192.168.1.101',
            'device_info': {
                'device': 'mobile',
                'browser': 'Chrome',
                'os': 'Android'
            }
        }
        
        response = self.client.post(url, engagement_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify engagement was created
        engagement = UserOfferEngagement.objects.filter(
            offer=self.offer, 
            user=self.user
        ).first()
        self.assertIsNotNone(engagement)
        self.assertEqual(engagement.status, EngagementStatus.STARTED)
        self.assertEqual(engagement.ip_address, '192.168.1.101')
    
    def test_offer_recommendations(self):
        """Test getting offer recommendations"""
        url = reverse('offer-recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        recommendations = response.data
        self.assertIn('recommendations', recommendations)
        self.assertIn('total_recommendations', recommendations)
        self.assertIsInstance(recommendations['recommendations'], list)
    
    def test_offer_analytics(self):
        """Test offer analytics (admin only)"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('offer-analytics', kwargs={'pk': self.offer.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        analytics = response.data
        self.assertIn('total_clicks', analytics)
        self.assertIn('total_conversions', analytics)
        self.assertIn('conversion_rate', analytics)
        self.assertIn('total_payout', analytics)


class TestAdNetworkViews(APITestCase):
    """
    Test cases for AdNetwork API views
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        # Create regular user
        self.user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='regularpass123'
        )
        
        # Create test network
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
    
    def test_network_list_success(self):
        """Test successful network list retrieval"""
        url = reverse('adnetwork-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        network_data = response.data['results'][0]
        self.assertEqual(network_data['name'], 'Test Network')
        self.assertEqual(network_data['network_type'], 'adscend')
        self.assertEqual(network_data['is_active'], True)
    
    def test_network_list_unauthorized(self):
        """Test network list for non-admin user"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('adnetwork-list')
        response = self.client.get(url)
        
        # Should return 403 for non-admin
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_network_create_success(self):
        """Test successful network creation"""
        url = reverse('adnetwork-list')
        network_data = {
            'name': 'New Test Network',
            'network_type': 'offertoro',
            'base_url': 'https://new.test.com',
            'api_key': 'new_api_key_123',
            'is_active': True
        }
        
        response = self.client.post(url, network_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify network was created
        network = AdNetwork.objects.get(name='New Test Network')
        self.assertEqual(network.network_type, 'offertoro')
        self.assertEqual(network.base_url, 'https://new.test.com')
        self.assertEqual(network.api_key, 'new_api_key_123')
    
    def test_network_create_validation_error(self):
        """Test network creation with validation error"""
        url = reverse('adnetwork-list')
        network_data = {
            'name': '',  # Empty name
            'network_type': 'invalid_type',
            'base_url': 'invalid_url'
        }
        
        response = self.client.post(url, network_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
        self.assertIn('network_type', response.data)
        self.assertIn('base_url', response.data)
    
    def test_network_detail_success(self):
        """Test successful network detail retrieval"""
        url = reverse('adnetwork-detail', kwargs={'pk': self.network.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        network_data = response.data
        self.assertEqual(network_data['name'], 'Test Network')
        self.assertEqual(network_data['network_type'], 'adscend')
        self.assertIn('total_conversions', network_data)
        self.assertIn('total_payout', network_data)
    
    def test_network_update_success(self):
        """Test successful network update"""
        url = reverse('adnetwork-detail', kwargs={'pk': self.network.id})
        update_data = {
            'name': 'Updated Network Name',
            'is_active': False
        }
        
        response = self.client.patch(url, update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify network was updated
        self.network.refresh_from_db()
        self.assertEqual(self.network.name, 'Updated Network Name')
        self.assertEqual(self.network.is_active, False)
    
    def test_network_delete_success(self):
        """Test successful network deletion"""
        url = reverse('adnetwork-detail', kwargs={'pk': self.network.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify network was deleted (soft delete)
        self.assertFalse(AdNetwork.objects.filter(id=self.network.id, is_active=True).exists())
    
    def test_network_health_check(self):
        """Test network health check endpoint"""
        url = reverse('adnetwork-health-check', kwargs={'pk': self.network.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        health_data = response.data
        self.assertIn('is_healthy', health_data)
        self.assertIn('response_time_ms', health_data)
        self.assertIn('last_check', health_data)


class TestConversionViews(APITestCase):
    """
    Test cases for Conversion API views
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        # Create test network and offer
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.offer = Offer.objects.create(
            ad_network=self.network,
            external_id='test_offer_123',
            title='Test Offer',
            reward_amount=Decimal('10.00'),
            status=OfferStatus.ACTIVE,
            tenant_id=self.tenant_id
        )
        
        # Create engagement
        self.engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.COMPLETED,
            ip_address='192.168.1.1',
            tenant_id=self.tenant_id
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_conversion_list_success(self):
        """Test successful conversion list retrieval"""
        # Create a conversion
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('10.00'),
            conversion_status=ConversionStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        url = reverse('conversion-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        conversion_data = response.data['results'][0]
        self.assertEqual(conversion_data['payout'], '10.00')
        self.assertEqual(conversion_data['conversion_status'], ConversionStatus.APPROVED)
    
    def test_conversion_list_admin_only(self):
        """Test conversion list for admin user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('conversion-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_conversion_detail_success(self):
        """Test successful conversion detail retrieval"""
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('15.00'),
            conversion_status=ConversionStatus.PENDING,
            fraud_score=25.0,
            tenant_id=self.tenant_id
        )
        
        url = reverse('conversion-detail', kwargs={'pk': conversion.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        conversion_data = response.data
        self.assertEqual(conversion_data['payout'], '15.00')
        self.assertEqual(conversion_data['conversion_status'], ConversionStatus.PENDING)
        self.assertEqual(conversion_data['fraud_score'], 25.0)
    
    def test_conversion_verify_success(self):
        """Test conversion verification"""
        self.client.force_authenticate(user=self.admin_user)
        
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('20.00'),
            conversion_status=ConversionStatus.PENDING,
            tenant_id=self.tenant_id
        )
        
        url = reverse('conversion-verify', kwargs={'pk': conversion.id})
        verify_data = {
            'approved': True,
            'notes': 'Manual verification passed'
        }
        
        response = self.client.post(url, verify_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify conversion was approved
        conversion.refresh_from_db()
        self.assertEqual(conversion.conversion_status, ConversionStatus.APPROVED)
        self.assertIsNotNone(conversion.verified_at)
    
    def test_conversion_reverse_success(self):
        """Test conversion reversal"""
        self.client.force_authenticate(user=self.admin_user)
        
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('25.00'),
            conversion_status=ConversionStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        url = reverse('conversion-reverse', kwargs={'pk': conversion.id})
        reverse_data = {
            'reason': 'User requested refund'
        }
        
        response = self.client.post(url, reverse_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify conversion was reversed
        conversion.refresh_from_db()
        self.assertEqual(conversion.conversion_status, ConversionStatus.CHARGEBACK)
        self.assertIsNotNone(conversion.chargeback_at)
    
    def test_conversion_stats_success(self):
        """Test conversion statistics"""
        url = reverse('conversion-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        stats = response.data
        self.assertIn('total_conversions', stats)
        self.assertIn('approved_conversions', stats)
        self.assertIn('rejected_conversions', stats)
        self.assertIn('approval_rate', stats)
        self.assertIn('fraud_rate', stats)


class TestRewardViews(APITestCase):
    """
    Test cases for Reward API views
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test network and offer
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.offer = Offer.objects.create(
            ad_network=self.network,
            external_id='test_offer_123',
            title='Test Offer',
            reward_amount=Decimal('10.00'),
            status=OfferStatus.ACTIVE,
            tenant_id=self.tenant_id
        )
        
        # Create user wallet
        self.wallet = UserWallet.objects.create(
            user=self.user,
            balance=Decimal('100.00'),
            total_earned=Decimal('500.00'),
            currency='USD',
            tenant_id=self.tenant_id
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_reward_list_success(self):
        """Test successful reward list retrieval"""
        # Create a reward
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('15.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        url = reverse('reward-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        reward_data = response.data['results'][0]
        self.assertEqual(reward_data['amount'], '15.00')
        self.assertEqual(reward_data['status'], RewardStatus.APPROVED)
    
    def test_reward_detail_success(self):
        """Test successful reward detail retrieval"""
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('20.00'),
            status=RewardStatus.PENDING,
            tenant_id=self.tenant_id
        )
        
        url = reverse('reward-detail', kwargs={'pk': reward.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        reward_data = response.data
        self.assertEqual(reward_data['amount'], '20.00')
        self.assertEqual(reward_data['status'], RewardStatus.PENDING)
    
    def test_wallet_balance_success(self):
        """Test wallet balance retrieval"""
        url = reverse('wallet-balance')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        wallet_data = response.data
        self.assertEqual(wallet_data['balance'], '100.00')
        self.assertEqual(wallet_data['total_earned'], '500.00')
        self.assertEqual(wallet_data['currency'], 'USD')
    
    def test_payout_request_success(self):
        """Test successful payout request"""
        # Create approved rewards
        for i in range(3):
            OfferReward.objects.create(
                user=self.user,
                offer=self.offer,
                amount=Decimal(f'{i+1}.00'),
                status=RewardStatus.APPROVED,
                tenant_id=self.tenant_id
            )
        
        url = reverse('payout-request')
        payout_data = {
            'reward_ids': [1, 2, 3],  # Would be actual IDs
            'payment_method': 'paypal',
            'payout_address': 'test@example.com'
        }
        
        response = self.client.post(url, payout_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        payout_request = response.data
        self.assertIn('payout_request_id', payout_request)
        self.assertEqual(payout_request['status'], 'pending')
    
    def test_payout_request_insufficient_balance(self):
        """Test payout request with insufficient balance"""
        # Set wallet to low balance
        self.wallet.balance = Decimal('1.00')
        self.wallet.save()
        
        url = reverse('payout-request')
        payout_data = {
            'reward_ids': [1, 2, 3],
            'payment_method': 'paypal',
            'payout_address': 'test@example.com'
        }
        
        response = self.client.post(url, payout_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient wallet balance', response.data)


class TestHealthCheckViews(APITestCase):
    """
    Test cases for Health Check API views
    """
    
    def setUp(self):
        """Set up test data"""
        self.tenant_id = 'test_tenant_123'
        
        # Create test network
        self.network = AdNetwork.objects.create(
            name='Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
    
    def test_health_summary_success(self):
        """Test health summary retrieval"""
        url = reverse('health-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        summary = response.data
        self.assertIn('total_networks', summary)
        self.assertIn('healthy_networks', summary)
        self.assertIn('unhealthy_networks', summary)
        self.assertIn('overall_health', summary)
    
    def test_network_health_history_success(self):
        """Test network health history retrieval"""
        # Create some health checks
        for i in range(5):
            NetworkHealthCheck.objects.create(
                network=self.network,
                is_healthy=i % 2 == 0,
                response_time_ms=100 + i * 10,
                status_code=200 if i % 2 == 0 else 500,
                tenant_id=self.tenant_id,
                checked_at=timezone.now() - timedelta(hours=i)
            )
        
        url = reverse('network-health-history', kwargs={'pk': self.network.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        history = response.data
        self.assertIn('total_checks', history)
        self.assertIn('healthy_checks', history)
        self.assertIn('uptime_percentage', history)
        self.assertIn('timeline', history)
    
    def test_trigger_health_check_success(self):
        """Test triggering health check"""
        url = reverse('trigger-health-check', kwargs={'pk': self.network.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertIn('is_healthy', result)
        self.assertIn('response_time_ms', result)
    
    def test_bulk_health_check_success(self):
        """Test bulk health check"""
        url = reverse('bulk-health-check')
        bulk_data = {
            'network_ids': [self.network.id],
            'check_type': 'api_call'
        }
        
        response = self.client.post(url, bulk_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = response.data
        self.assertIn('total_networks', result)
        self.assertIn('healthy_networks', result)
        self.assertIn('results', result)


class TestAPIAuthentication(APITestCase):
    """
    Test cases for API authentication
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated access is denied"""
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test that authenticated access is allowed"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_admin_only_endpoint_denied_for_user(self):
        """Test that admin-only endpoints are denied for regular users"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('adnetwork-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_only_endpoint_allowed_for_admin(self):
        """Test that admin-only endpoints are allowed for admin users"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('adnetwork-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


if __name__ == '__main__':
    pytest.main([__file__])

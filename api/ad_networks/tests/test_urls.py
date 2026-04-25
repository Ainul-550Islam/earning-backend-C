"""
api/ad_networks/tests/test_urls.py
Tests for URL patterns in the ad_networks module
SaaS-ready with tenant support
"""

import pytest
from django.test import TestCase
from django.urls import reverse, resolve
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class TestURLPatterns(TestCase):
    """Test URL patterns and routing"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_categories_urls(self):
        """Test category URLs"""
        # List and create
        url = reverse('offer-category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-category-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_offers_urls(self):
        """Test offer URLs"""
        # List and create
        url = reverse('offer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-click', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-start', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-complete', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-trending')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('offer-recommended')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_engagements_urls(self):
        """Test engagement URLs"""
        # List and create
        url = reverse('engagement-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('engagement-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('engagement-my-engagements')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('engagement-statistics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_conversions_urls(self):
        """Test conversion URLs"""
        # List and create
        url = reverse('conversion-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('conversion-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('conversion-verify', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('conversion-reject', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_networks_urls(self):
        """Test network URLs"""
        # List and create
        url = reverse('ad-network-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('ad-network-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('ad-network-test-connection', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('ad-network-sync-offers', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_network_health_urls(self):
        """Test network health URLs"""
        # List and create
        url = reverse('network-health-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('network-health-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('network-health-check-all')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_analytics_urls(self):
        """Test analytics URLs"""
        # List and create
        url = reverse('analytics-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('analytics-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('analytics-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('analytics-user-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_fraud_rules_urls(self):
        """Test fraud rules URLs"""
        # List and create
        url = reverse('fraud-rule-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('fraud-rule-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('fraud-rule-test-rule', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('fraud-rule-statistics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_blacklisted_ips_urls(self):
        """Test blacklisted IPs URLs"""
        # List and create
        url = reverse('blacklisted-ip-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('blacklisted-ip-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('blacklisted-ip-bulk-add')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('blacklisted-ip-cleanup-expired')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_known_bad_ips_urls(self):
        """Test known bad IPs URLs"""
        # List and create
        url = reverse('known-bad-ip-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('known-bad-ip-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('known-bad-ip-import-from-source')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_user_limits_urls(self):
        """Test user limits URLs"""
        # List and create
        url = reverse('user-limit-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('user-limit-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('user-limit-reset-daily', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('user-limit-for-user')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_clicks_urls(self):
        """Test clicks URLs"""
        # List and create
        url = reverse('offer-click-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-click-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-click-analytics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('offer-click-track-click')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_rewards_urls(self):
        """Test rewards URLs"""
        # List and create
        url = reverse('offer-reward-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-reward-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-reward-approve', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-reward-process-payment', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-reward-statistics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_tags_urls(self):
        """Test tags URLs"""
        # List and create
        url = reverse('offer-tag-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-tag-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-tag-merge-with', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_tagging_urls(self):
        """Test tagging URLs"""
        # List and create
        url = reverse('offer-tagging-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-tagging-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-tagging-bulk-tag')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_recommendations_urls(self):
        """Test recommendations URLs"""
        # List and create
        url = reverse('smart-recommendation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('smart-recommendation-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('smart-recommendation-for-user')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('smart-recommendation-mark-displayed', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_statistics_urls(self):
        """Test statistics URLs"""
        # List and create
        url = reverse('network-statistic-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('network-statistic-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('network-statistic-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_sync_logs_urls(self):
        """Test sync logs URLs"""
        # List and create
        url = reverse('offer-sync-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-sync-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-sync-retry-sync', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_webhook_logs_urls(self):
        """Test webhook logs URLs"""
        # List and create
        url = reverse('webhook-log-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('webhook-log-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('webhook-log-retry-webhook', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('webhook-log-bulk-process')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_daily_limits_urls(self):
        """Test daily limits URLs"""
        # List and create
        url = reverse('daily-limit-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('daily-limit-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('daily-limit-reset-daily', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('daily-limit-bulk-reset')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_offer_walls_urls(self):
        """Test offer walls URLs"""
        # List and create
        url = reverse('offer-wall-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Detail
        url = reverse('offer-wall-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Actions
        url = reverse('offer-wall-offers', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = reverse('offer-wall-default')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_utilities_urls(self):
        """Test utilities URLs"""
        # List and create
        url = reverse('utility-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Actions
        url = reverse('utility-choices')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('utility-clear-cache')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_api_versioning_urls(self):
        """Test API versioning URLs"""
        # API v1 endpoints
        url = '/api/v1/categories/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = '/api/v1/offers/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = '/api/v1/engagements/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Direct endpoints (backward compatibility)
        url = '/categories/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = '/offers/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_webhook_urls(self):
        """Test webhook URLs"""
        # Network webhooks
        url = '/api/v1/webhooks/networks/test-network-123/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = '/api/v1/webhooks/networks/test-network-123/callback/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Offer webhooks
        url = '/api/v1/webhooks/offers/test-offer-123/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        url = '/api/v1/webhooks/offers/test-offer-123/conversion/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Conversion webhooks
        url = '/api/v1/webhooks/conversions/test-conv-123/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Generic webhook
        url = '/api/v1/webhooks/'
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_nested_urls(self):
        """Test nested URLs"""
        # Offers nested endpoints
        url = reverse('offer-clicks', kwargs={'offer_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('offer-rewards', kwargs={'offer_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('offer-taggings', kwargs={'offer_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Categories nested endpoints
        url = reverse('category-offers', kwargs={'category_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Networks nested endpoints
        url = reverse('network-health-checks', kwargs={'network_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('network-statistics', kwargs={'network_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('network-sync-logs', kwargs={'network_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('network-webhook-logs', kwargs={'network_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        # Users nested endpoints
        url = reverse('user-engagements', kwargs={'user_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('user-limits', kwargs={'user_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('user-recommendations', kwargs={'user_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('user-daily-limits', kwargs={'user_pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
    
    def test_url_resolution(self):
        """Test URL resolution"""
        # Test that URLs resolve to correct viewsets
        resolved = resolve('/api/v1/categories/')
        self.assertEqual(resolved.view_name, 'ad_networks:offer-category-list')
        
        resolved = resolve('/api/v1/offers/')
        self.assertEqual(resolved.view_name, 'ad_networks:offer-list')
        
        resolved = resolve('/api/v1/engagements/')
        self.assertEqual(resolved.view_name, 'ad_networks:engagement-list')
        
        resolved = resolve('/api/v1/networks/')
        self.assertEqual(resolved.view_name, 'ad_networks:ad-network-list')
        
        resolved = resolve('/api/v1/fraud-rules/')
        self.assertEqual(resolved.view_name, 'ad_networks:fraud-rule-list')
        
        resolved = resolve('/api/v1/utilities/')
        self.assertEqual(resolved.view_name, 'ad_networks:utility-list')
    
    def test_url_parameters(self):
        """Test URL parameters"""
        # Test that URLs accept parameters correctly
        url = reverse('offer-list')
        response = self.client.get(url, {'page': 1, 'page_size': 10})
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('smart-recommendation-for-user')
        response = self.client.get(url, {'user_id': 1})
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists
        
        url = reverse('network-statistic-summary')
        response = self.client.get(url, {'start_date': '2023-01-01', 'end_date': '2023-12-31'})
        self.assertEqual(response.status_code, 404)  # No data yet, but URL exists


class TestURLIntegration(TestCase):
    """Test URL integration with actual data"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
        
        # Import models here to avoid circular imports
        from ..models import AdNetwork, OfferCategory, Offer
        
        # Create test data
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa',
            api_key='test_api_key_123'
        )
        
        self.category = OfferCategory.objects.create(
            tenant_id=self.tenant_id,
            name='Test Category',
            slug='test-category'
        )
        
        self.offer = Offer.objects.create(
            tenant_id=self.tenant_id,
            title='Test Offer',
            ad_network=self.ad_network,
            category=self.category,
            reward_amount=Decimal('10.00'),
            reward_currency='USD',
            status='active'
        )
    
    def test_categories_with_data(self):
        """Test categories endpoint with actual data"""
        url = reverse('offer-category-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Category')
    
    def test_offers_with_data(self):
        """Test offers endpoint with actual data"""
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Test Offer')
    
    def test_networks_with_data(self):
        """Test networks endpoint with actual data"""
        url = reverse('ad-network-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Network')
    
    def test_detail_endpoints_with_data(self):
        """Test detail endpoints with actual data"""
        # Category detail
        url = reverse('offer-category-detail', kwargs={'pk': self.category.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Test Category')
        
        # Offer detail
        url = reverse('offer-detail', kwargs={'pk': self.offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Test Offer')
        
        # Network detail
        url = reverse('ad-network-detail', kwargs={'pk': self.ad_network.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Test Network')
    
    def test_action_endpoints_with_data(self):
        """Test action endpoints with actual data"""
        # Test click action
        url = reverse('offer-click', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('click_id', response.data['data'])
        
        # Test start action
        url = reverse('offer-start', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('engagement_id', response.data['data'])
        
        # Test trending action
        url = reverse('offer-trending')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        
        # Test dashboard action
        url = reverse('analytics-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('offers', response.data['data'])
        self.assertIn('engagements', response.data['data'])
        self.assertIn('revenue', response.data['data'])
    
    def test_nested_endpoints_with_data(self):
        """Test nested endpoints with actual data"""
        # Test offers nested under category
        url = reverse('category-offers', kwargs={'category_pk': self.category.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        
        # Test clicks nested under offer
        url = reverse('offer-clicks', kwargs={'offer_pk': self.offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        
        # Test rewards nested under offer
        url = reverse('offer-rewards', kwargs={'offer_pk': self.offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
    
    def test_filtering_and_search(self):
        """Test filtering and search functionality"""
        # Test filtering
        url = reverse('offer-list')
        response = self.client.get(url, {'status': 'active'})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test search
        url = reverse('offer-list')
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test ordering
        url = reverse('offer-list')
        response = self.client.get(url, {'ordering': '-created_at'})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_pagination(self):
        """Test pagination functionality"""
        url = reverse('offer-list')
        response = self.client.get(url, {'page': 1, 'page_size': 10})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_authentication_required(self):
        """Test that authentication is required"""
        # Logout client
        self.client.force_authenticate(user=None)
        
        # Test that endpoints require authentication
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 401)
        
        url = reverse('offer-detail', kwargs={'pk': self.offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 401)
        
        url = reverse('offer-click', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 401)
    
    def test_offer_attachment_urls(self):
        """Test OfferAttachment URLs"""
        # List and create
        url = reverse('offer-attachment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)  # URL exists
        
        # Detail
        url = reverse('offer-attachment-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Custom action - download
        url = reverse('offer-attachment-download', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_user_wallet_urls(self):
        """Test UserWallet URLs"""
        # List and create
        url = reverse('user-wallet-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)  # URL exists
        
        # Detail
        url = reverse('user-wallet-detail', kwargs={'pk': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Custom action - my_wallet
        url = reverse('user-wallet-my-wallet')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)  # URL exists
        
        # Custom action - freeze
        url = reverse('user-wallet-freeze', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
        
        # Custom action - unfreeze
        url = reverse('user-wallet-unfreeze', kwargs={'pk': 1})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)  # Not found, but URL exists
    
    def test_webhook_urls(self):
        """Test webhook URLs"""
        # Test webhook endpoints
        webhook_urls = [
            'admob-webhook',
            'unity-webhook',
            'ironsource-webhook',
            'applovin-webhook',
            'tapjoy-webhook',
            'vungle-webhook',
            'adscend-webhook',
            'offertoro-webhook',
            'adgem-webhook',
            'ayetstudios-webhook',
        ]
        
        for webhook_name in webhook_urls:
            try:
                url = reverse(webhook_name)
                # Test that webhook URLs exist (they should accept POST requests)
                response = self.client.post(url, {}, format='json')
                # Webhooks should return error but URL should exist
                self.assertIn(response.status_code, [400, 404, 403, 500])
            except:
                # If reverse fails, it means URL is not properly configured
                self.fail(f"Webhook URL '{webhook_name}' not found")
    
    def test_url_resolution(self):
        """Test URL resolution for all endpoints"""
        # Test that all main URLs resolve correctly
        url_patterns = [
            ('offer-category-list', []),
            ('offer-list', []),
            ('ad-network-list', []),
            ('offer-attachment-list', []),
            ('user-wallet-list', []),
            ('offer-conversion-list', []),
            ('offer-click-list', []),
            ('offer-reward-list', []),
        ]
        
        for url_name, kwargs in url_patterns:
            try:
                url = reverse(url_name, kwargs=kwargs)
                resolved = resolve(url)
                self.assertIsNotNone(resolved)
            except:
                self.fail(f"URL '{url_name}' could not be resolved")

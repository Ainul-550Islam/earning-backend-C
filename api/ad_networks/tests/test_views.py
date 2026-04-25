"""
api/ad_networks/tests/test_views.py
Tests for all viewsets in the ad_networks module
SaaS-ready with tenant support
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from decimal import Decimal

from ..models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    FraudDetectionRule, BlacklistedIP, KnownBadIP, OfferClick,
    OfferReward, NetworkAPILog, OfferTag, OfferTagging,
    NetworkHealthCheck, OfferDailyLimit, OfferAttachment, UserWallet
)

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
        
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


class TestOfferCategoryViewSet(BaseTestCase):
    """Test OfferCategoryViewSet"""
    
    def test_list_categories(self):
        """Test listing categories"""
        url = reverse('offer-category-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_category(self):
        """Test creating a category"""
        url = reverse('offer-category-list')
        data = {
            'name': 'New Category',
            'slug': 'new-category',
            'category_type': 'surveys',
            'color': '#FF0000'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OfferCategory.objects.count(), 2)
    
    def test_retrieve_category(self):
        """Test retrieving a category"""
        url = reverse('offer-category-detail', kwargs={'pk': self.category.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Category')
    
    def test_update_category(self):
        """Test updating a category"""
        url = reverse('offer-category-detail', kwargs={'pk': self.category.pk})
        data = {'name': 'Updated Category'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Updated Category')
    
    def test_delete_category(self):
        """Test deleting a category"""
        url = reverse('offer-category-detail', kwargs={'pk': self.category.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OfferCategory.objects.count(), 0)
    
    def test_featured_categories_action(self):
        """Test featured categories action"""
        # Mark category as featured
        self.category.is_featured = True
        self.category.save()
        
        url = reverse('offer-category-featured')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)


class TestOfferViewSet(BaseTestCase):
    """Test OfferViewSet"""
    
    def test_list_offers(self):
        """Test listing offers"""
        url = reverse('offer-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_offer(self):
        """Test creating an offer"""
        url = reverse('offer-list')
        data = {
            'title': 'New Offer',
            'ad_network': self.ad_network.pk,
            'category': self.category.pk,
            'reward_amount': '15.00',
            'reward_currency': 'USD',
            'difficulty': 'medium',
            'estimated_time': 15,
            'status': 'active'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Offer.objects.count(), 2)
    
    def test_retrieve_offer(self):
        """Test retrieving an offer"""
        url = reverse('offer-detail', kwargs={'pk': self.offer.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Offer')
    
    def test_click_offer_action(self):
        """Test click offer action"""
        url = reverse('offer-click', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('click_id', response.data['data'])
        self.assertIn('fraud_score', response.data['data'])
    
    def test_start_offer_action(self):
        """Test start offer action"""
        url = reverse('offer-start', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('engagement_id', response.data['data'])
        self.assertIn('reward_id', response.data['data'])
    
    def test_complete_offer_action(self):
        """Test complete offer action"""
        # First start the offer
        engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            status='started'
        )
        
        url = reverse('offer-complete', kwargs={'pk': self.offer.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversion_id', response.data['data'])
    
    def test_trending_offers_action(self):
        """Test trending offers action"""
        url = reverse('offer-trending')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)


class TestUserOfferEngagementViewSet(BaseTestCase):
    """Test UserOfferEngagementViewSet"""
    
    def setUp(self):
        super().setUp()
        self.engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            status='started',
            ip_address='127.0.0.1'
        )
    
    def test_list_engagements(self):
        """Test listing engagements"""
        url = reverse('engagement-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_my_engagements_action(self):
        """Test my engagements action"""
        url = reverse('engagement-my-engagements')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
    
    def test_statistics_action(self):
        """Test statistics action"""
        url = reverse('engagement-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_engagements', response.data['data'])


class TestAdNetworkViewSet(BaseTestCase):
    """Test AdNetworkViewSet"""
    
    def test_list_networks(self):
        """Test listing networks"""
        url = reverse('ad-network-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_network(self):
        """Test creating a network"""
        url = reverse('ad-network-list')
        data = {
            'name': 'New Network',
            'network_type': 'cps',
            'api_key': 'new_api_key_123',
            'webhook_url': 'https://example.com/webhook'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AdNetwork.objects.count(), 2)
    
    def test_test_connection_action(self):
        """Test test connection action"""
        url = reverse('ad-network-test-connection', kwargs={'pk': self.ad_network.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status_code', response.data['data'])
    
    def test_sync_offers_action(self):
        """Test sync offers action"""
        url = reverse('ad-network-sync-offers', kwargs={'pk': self.ad_network.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('offers_fetched', response.data['data'])


class TestFraudDetectionRuleViewSet(BaseTestCase):
    """Test FraudDetectionRuleViewSet"""
    
    def setUp(self):
        super().setUp()
        self.rule = FraudDetectionRule.objects.create(
            tenant_id=self.tenant_id,
            name='Test Rule',
            rule_type='ip_based',
            action='block',
            severity='high',
            priority=80,
            conditions={'field': 'ip_address', 'operator': 'in_list'}
        )
    
    def test_list_rules(self):
        """Test listing fraud rules"""
        url = reverse('fraud-rule-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_rule(self):
        """Test creating a fraud rule"""
        url = reverse('fraud-rule-list')
        data = {
            'name': 'New Rule',
            'rule_type': 'frequency_based',
            'action': 'flag',
            'severity': 'medium',
            'priority': 60,
            'conditions': {'field': 'user_id', 'operator': 'count', 'value': 10}
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FraudDetectionRule.objects.count(), 2)
    
    def test_test_rule_action(self):
        """Test test rule action"""
        url = reverse('fraud-rule-test-rule', kwargs={'pk': self.rule.pk})
        data = {'test_data': {'ip_address': '192.168.1.100'}}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_triggered', response.data['data'])
    
    def test_statistics_action(self):
        """Test statistics action"""
        url = reverse('fraud-rule-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_rules', response.data['data'])


class TestBlacklistedIPViewSet(BaseTestCase):
    """Test BlacklistedIPViewSet"""
    
    def setUp(self):
        super().setUp()
        self.blacklisted_ip = BlacklistedIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.100',
            reason='fraud',
            description='Suspicious activity'
        )
    
    def test_list_blacklisted_ips(self):
        """Test listing blacklisted IPs"""
        url = reverse('blacklisted-ip-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_blacklisted_ip(self):
        """Test creating a blacklisted IP"""
        url = reverse('blacklisted-ip-list')
        data = {
            'ip_address': '192.168.1.200',
            'reason': 'spam',
            'description': 'Spam activity detected'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BlacklistedIP.objects.count(), 2)
    
    def test_bulk_add_action(self):
        """Test bulk add action"""
        url = reverse('blacklisted-ip-bulk-add')
        data = {
            'ips': [
                {'ip_address': '192.168.1.201', 'reason': 'spam'},
                {'ip_address': '192.168.1.202', 'reason': 'malware'}
            ]
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('created_count', response.data['data'])


class TestOfferClickViewSet(BaseTestCase):
    """Test OfferClickViewSet"""
    
    def setUp(self):
        super().setUp()
        self.click = OfferClick.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            click_id='test_click_123',
            ip_address='127.0.0.1',
            is_unique=True
        )
    
    def test_list_clicks(self):
        """Test listing clicks"""
        url = reverse('offer-click-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_analytics_action(self):
        """Test analytics action"""
        url = reverse('offer-click-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_clicks', response.data['data'])
    
    def test_track_click_action(self):
        """Test track click action"""
        url = reverse('offer-click-track-click')
        data = {
            'offer_id': self.offer.pk,
            'click_id': 'new_click_123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('click_id', response.data['data'])


class TestOfferRewardViewSet(BaseTestCase):
    """Test OfferRewardViewSet"""
    
    def setUp(self):
        super().setUp()
        self.engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            status='completed'
        )
        self.reward = OfferReward.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            engagement=self.engagement,
            amount=Decimal('10.00'),
            currency='USD',
            status='pending'
        )
    
    def test_list_rewards(self):
        """Test listing rewards"""
        url = reverse('offer-reward-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_approve_action(self):
        """Test approve action"""
        url = reverse('offer-reward-approve', kwargs={'pk': self.reward.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.status, 'approved')
    
    def test_process_payment_action(self):
        """Test process payment action"""
        # First approve the reward
        self.reward.status = 'approved'
        self.reward.save()
        
        url = reverse('offer-reward-process-payment', kwargs={'pk': self.reward.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.status, 'paid')


class TestOfferTagViewSet(BaseTestCase):
    """Test OfferTagViewSet"""
    
    def setUp(self):
        super().setUp()
        self.tag = OfferTag.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tag',
            slug='test-tag',
            color='#FF0000',
            created_by=self.user
        )
    
    def test_list_tags(self):
        """Test listing tags"""
        url = reverse('offer-tag-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_tag(self):
        """Test creating a tag"""
        url = reverse('offer-tag-list')
        data = {
            'name': 'New Tag',
            'slug': 'new-tag',
            'color': '#00FF00'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OfferTag.objects.count(), 2)


class TestAnalyticsViewSet(BaseTestCase):
    """Test AnalyticsViewSet"""
    
    def test_dashboard_action(self):
        """Test dashboard action"""
        url = reverse('analytics-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('offers', response.data['data'])
        self.assertIn('engagements', response.data['data'])
        self.assertIn('revenue', response.data['data'])
    
    def test_user_stats_action(self):
        """Test user stats action"""
        url = reverse('analytics-user-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_engagements', response.data['data'])


class TestUtilityViewSet(BaseTestCase):
    """Test UtilityViewSet"""
    
    def test_choices_action(self):
        """Test choices action"""
        url = reverse('utility-choices')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_clear_cache_action(self):
        """Test clear cache action (admin only)"""
        # Use admin user
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('utility-clear-cache')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('cleared_count', response.data['data'])


class TestNetworkHealthCheckViewSet(BaseTestCase):
    """Test NetworkHealthCheckViewSet"""
    
    def setUp(self):
        super().setUp()
        self.health_check = NetworkHealthCheck.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            check_type='connection_test',
            endpoint_checked='https://example.com',
            is_healthy=True,
            status_code=200
        )
    
    def test_list_health_checks(self):
        """Test listing health checks"""
        url = reverse('network-health-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_check_all_action(self):
        """Test check all action"""
        url = reverse('network-health-check-all')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data['data'])


class TestOfferWallViewSet(BaseTestCase):
    """Test OfferWallViewSet"""
    
    def setUp(self):
        super().setUp()
        self.offer_wall = OfferWall.objects.create(
            tenant_id=self.tenant_id,
            name='Test Offer Wall',
            wall_type='standard',
            min_payout=Decimal('5.00'),
            max_payout=Decimal('100.00')
        )
        self.offer_wall.ad_networks.add(self.ad_network)
    
    def test_list_offer_walls(self):
        """Test listing offer walls"""
        url = reverse('offer-wall-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_offers_action(self):
        """Test offers action"""
        url = reverse('offer-wall-offers', kwargs={'pk': self.offer_wall.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
    
    def test_default_action(self):
        """Test default action"""
        # Set as default
        self.offer_wall.is_default = True
        self.offer_wall.save()
        
        url = reverse('offer-wall-default')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)


# Test remaining viewsets...

class TestKnownBadIPViewSet(BaseTestCase):
    """Test KnownBadIPViewSet"""
    
    def setUp(self):
        super().setUp()
        self.bad_ip = KnownBadIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.200',
            threat_type='malware',
            source='external_feed',
            confidence_score=95.0
        )
    
    def test_list_known_bad_ips(self):
        """Test listing known bad IPs"""
        url = reverse('known-bad-ip-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_import_from_source_action(self):
        """Test import from source action"""
        url = reverse('known-bad-ip-import-from-source')
        data = {'source': 'spamhaus'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('imported_count', response.data['data'])


class TestNetworkAPILogViewSet(BaseTestCase):
    """Test NetworkAPILogViewSet"""
    
    def setUp(self):
        super().setUp()
        self.api_log = NetworkAPILog.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            method='GET',
            endpoint='/api/offers',
            status_code=200,
            is_success=True
        )
    
    def test_list_api_logs(self):
        """Test listing API logs"""
        url = reverse('network-api-log-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_statistics_action(self):
        """Test statistics action"""
        url = reverse('network-api-log-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_calls', response.data['data'])


class TestOfferTaggingViewSet(BaseTestCase):
    """Test OfferTaggingViewSet"""
    
    def setUp(self):
        super().setUp()
        self.tag = OfferTag.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tag',
            slug='test-tag',
            created_by=self.user
        )
        self.tagging = OfferTagging.objects.create(
            tenant_id=self.tenant_id,
            offer=self.offer,
            tag=self.tag,
            added_by=self.user,
            confidence_score=90.0
        )
    
    def test_list_taggings(self):
        """Test listing taggings"""
        url = reverse('offer-tagging-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_bulk_tag_action(self):
        """Test bulk tag action"""
        url = reverse('offer-tagging-bulk-tag')
        data = {
            'offer_ids': [self.offer.pk],
            'tag_id': self.tag.pk
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tagged_count', response.data['data'])


class TestSmartOfferRecommendationViewSet(BaseTestCase):
    """Test SmartOfferRecommendationViewSet"""
    
    def setUp(self):
        super().setUp()
        self.recommendation = SmartOfferRecommendation.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            score=85.5
        )
    
    def test_list_recommendations(self):
        """Test listing recommendations"""
        url = reverse('smart-recommendation-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_for_user_action(self):
        """Test for user action"""
        url = reverse('smart-recommendation-for-user')
        response = self.client.get(url, {'user_id': self.user.pk})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)


class TestNetworkStatisticViewSet(BaseTestCase):
    """Test NetworkStatisticViewSet"""
    
    def setUp(self):
        super().setUp()
        self.statistic = NetworkStatistic.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            date=timezone.now().date(),
            clicks=1000,
            conversions=100,
            payout=Decimal('1000.00')
        )
    
    def test_list_statistics(self):
        """Test listing statistics"""
        url = reverse('network-statistic-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_summary_action(self):
        """Test summary action"""
        url = reverse('network-statistic-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_clicks', response.data['data'])


class TestUserOfferLimitViewSet(BaseTestCase):
    """Test UserOfferLimitViewSet"""
    
    def setUp(self):
        super().setUp()
        self.limit = UserOfferLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=5,
            total_limit=50
        )
    
    def test_list_limits(self):
        """Test listing limits"""
        url = reverse('user-limit-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_reset_daily_action(self):
        """Test reset daily action"""
        url = reverse('user-limit-reset-daily', kwargs={'pk': self.limit.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.limit.refresh_from_db()
        self.assertEqual(self.limit.daily_count, 0)
    
    def test_for_user_action(self):
        """Test for user action"""
        url = reverse('user-limit-for-user')
        response = self.client.get(url, {'user_id': self.user.pk})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)


class TestOfferSyncLogViewSet(BaseTestCase):
    """Test OfferSyncLogViewSet"""
    
    def setUp(self):
        super().setUp()
        self.sync_log = OfferSyncLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            sync_type='manual',
            status='completed',
            offers_fetched=100,
            offers_created=50
        )
    
    def test_list_sync_logs(self):
        """Test listing sync logs"""
        url = reverse('offer-sync-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_retry_sync_action(self):
        """Test retry sync action"""
        # Set status to failed
        self.sync_log.status = 'failed'
        self.sync_log.save()
        
        url = reverse('offer-sync-retry-sync', kwargs={'pk': self.sync_log.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sync_id', response.data['data'])


class TestAdNetworkWebhookLogViewSet(BaseTestCase):
    """Test AdNetworkWebhookLogViewSet"""
    
    def setUp(self):
        super().setUp()
        self.webhook_log = AdNetworkWebhookLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            event_type='offer.created',
            payload={'offer_id': 123},
            processed=False
        )
    
    def test_list_webhook_logs(self):
        """Test listing webhook logs"""
        url = reverse('webhook-log-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_retry_webhook_action(self):
        """Test retry webhook action"""
        url = reverse('webhook-log-retry-webhook', kwargs={'pk': self.webhook_log.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('retry_count', response.data['data'])
    
    def test_bulk_process_action(self):
        """Test bulk process action"""
        url = reverse('webhook-log-bulk-process')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('processed_count', response.data['data'])


class TestOfferDailyLimitViewSet(BaseTestCase):
    """Test OfferDailyLimitViewSet"""
    
    def setUp(self):
        super().setUp()
        self.daily_limit = OfferDailyLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=10,
            count_today=3
        )
    
    def test_list_daily_limits(self):
        """Test listing daily limits"""
        url = reverse('daily-limit-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_reset_daily_action(self):
        """Test reset daily action"""
        url = reverse('daily-limit-reset-daily', kwargs={'pk': self.daily_limit.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.daily_limit.refresh_from_db()
        self.assertEqual(self.daily_limit.count_today, 0)
    
    def test_bulk_reset_action(self):
        """Test bulk reset action"""
        url = reverse('daily-limit-bulk-reset')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reset_count', response.data['data'])


class TestOfferConversionViewSet(BaseTestCase):
    """Test OfferConversionViewSet"""
    
    def setUp(self):
        super().setUp()
        self.engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            status='completed'
        )
        self.conversion = OfferConversion.objects.create(
            tenant_id=self.tenant_id,
            engagement=self.engagement,
            conversion_id='conv_123',
            conversion_status='pending',
            payout=Decimal('10.00')
        )
    
    def test_list_conversions(self):
        """Test listing conversions"""
        url = reverse('conversion-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_verify_action(self):
        """Test verify action"""
        url = reverse('conversion-verify', kwargs={'pk': self.conversion.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.conversion.refresh_from_db()
        self.assertTrue(self.conversion.is_verified)
    
    def test_reject_action(self):
        """Test reject action"""
        url = reverse('conversion-reject', kwargs={'pk': self.conversion.pk})
        data = {'reason': 'Invalid conversion'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.conversion.refresh_from_db()
        self.assertEqual(self.conversion.conversion_status, 'rejected')


class TestOfferAttachmentViewSet(BaseTestCase):
    """Test OfferAttachmentViewSet"""
    
    def setUp(self):
        super().setUp()
        
        # Create test data
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.offer = Offer.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            title='Test Offer',
            description='Test Description',
            payout=Decimal('10.00')
        )
        
        # Create mock file
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.test_file = SimpleUploadedFile(
            "test.jpg", 
            b"file_content", 
            content_type="image/jpeg"
        )
        
        self.attachment = OfferAttachment.objects.create(
            tenant_id=self.tenant_id,
            offer=self.offer,
            file=self.test_file,
            filename='test.jpg',
            original_filename='original_test.jpg',
            file_type='image',
            mime_type='image/jpeg',
            file_size=1024,
            file_hash='abc123def456',
            description='Test attachment'
        )
        
        # Authenticate user
        self.client.force_authenticate(user=self.user)
    
    def test_list_attachments(self):
        """Test listing attachments"""
        url = reverse('offer-attachment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 1)
    
    def test_create_attachment(self):
        """Test creating attachment"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        url = reverse('offer-attachment-list')
        data = {
            'offer': self.offer.id,
            'file': SimpleUploadedFile("new.jpg", b"new_content", content_type="image/jpeg"),
            'filename': 'new.jpg',
            'original_filename': 'original_new.jpg',
            'file_type': 'image',
            'mime_type': 'image/jpeg',
            'file_size': 2048,
            'file_hash': 'xyz789abc123',
            'description': 'New attachment'
        }
        
        response = self.client.post(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OfferAttachment.objects.count(), 2)
    
    def test_retrieve_attachment(self):
        """Test retrieving attachment"""
        url = reverse('offer-attachment-detail', kwargs={'pk': self.attachment.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.attachment.id)
        self.assertEqual(response.data['filename'], 'test.jpg')
    
    def test_update_attachment(self):
        """Test updating attachment"""
        url = reverse('offer-attachment-detail', kwargs={'pk': self.attachment.pk})
        data = {
            'description': 'Updated description',
            'is_primary': True
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.description, 'Updated description')
        self.assertTrue(self.attachment.is_primary)
    
    def test_delete_attachment(self):
        """Test deleting attachment"""
        url = reverse('offer-attachment-detail', kwargs={'pk': self.attachment.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OfferAttachment.objects.count(), 0)
    
    def test_download_action(self):
        """Test download action"""
        url = reverse('offer-attachment-download', kwargs={'pk': self.attachment.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('download_url', response.data)
        self.assertEqual(response.data['filename'], 'test.jpg')
    
    def test_filter_by_offer(self):
        """Test filtering attachments by offer"""
        url = reverse('offer-attachment-list')
        response = self.client.get(url, {'offer': self.offer.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['offer'], self.offer.id)


class TestUserWalletViewSet(BaseTestCase):
    """Test UserWalletViewSet"""
    
    def setUp(self):
        super().setUp()
        
        self.wallet = UserWallet.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            current_balance=Decimal('1000.50'),
            total_earned=Decimal('1500.00'),
            total_withdrawn=Decimal('400.00'),
            pending_balance=Decimal('50.00'),
            currency='BDT',
            is_active=True,
            is_frozen=False,
            daily_limit=Decimal('5000.00'),
            monthly_limit=Decimal('100000.00')
        )
        
        # Authenticate user
        self.client.force_authenticate(user=self.user)
    
    def test_list_wallets(self):
        """Test listing wallets"""
        url = reverse('user-wallet-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 1)
    
    def test_create_wallet(self):
        """Test creating wallet"""
        # Create another user
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123'
        )
        
        url = reverse('user-wallet-list')
        data = {
            'user': new_user.id,
            'current_balance': '2000.00',
            'total_earned': '3000.00',
            'total_withdrawn': '800.00',
            'pending_balance': '100.00',
            'currency': 'USD',
            'is_active': True,
            'is_frozen': False,
            'daily_limit': '10000.00',
            'monthly_limit': '200000.00'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserWallet.objects.count(), 2)
    
    def test_retrieve_wallet(self):
        """Test retrieving wallet"""
        url = reverse('user-wallet-detail', kwargs={'pk': self.wallet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.wallet.id)
        self.assertEqual(response.data['current_balance'], '1000.50')
        self.assertEqual(response.data['currency'], 'BDT')
    
    def test_update_wallet(self):
        """Test updating wallet"""
        url = reverse('user-wallet-detail', kwargs={'pk': self.wallet.pk})
        data = {
            'current_balance': '1500.00',
            'daily_limit': '7500.00'
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(str(self.wallet.current_balance), '1500.00')
        self.assertEqual(str(self.wallet.daily_limit), '7500.00')
    
    def test_my_wallet_action(self):
        """Test my_wallet action"""
        url = reverse('user-wallet-my-wallet')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.wallet.id)
        self.assertEqual(response.data['user'], self.user.id)
    
    def test_freeze_action(self):
        """Test freeze action"""
        url = reverse('user-wallet-freeze', kwargs={'pk': self.wallet.pk})
        data = {'reason': 'Suspicious activity'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.is_frozen)
        self.assertEqual(self.wallet.freeze_reason, 'Suspicious activity')
        self.assertIsNotNone(self.wallet.frozen_at)
    
    def test_unfreeze_action(self):
        """Test unfreeze action"""
        # First freeze the wallet
        self.wallet.is_frozen = True
        self.wallet.freeze_reason = 'Test freeze'
        self.wallet.save()
        
        url = reverse('user-wallet-unfreeze', kwargs={'pk': self.wallet.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertFalse(self.wallet.is_frozen)
        self.assertIsNone(self.wallet.freeze_reason)
        self.assertIsNone(self.wallet.frozen_at)
    
    def test_filter_by_currency(self):
        """Test filtering wallets by currency"""
        url = reverse('user-wallet-list')
        response = self.client.get(url, {'currency': 'BDT'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['currency'], 'BDT')
    
    def test_filter_by_status(self):
        """Test filtering wallets by status"""
        url = reverse('user-wallet-list')
        response = self.client.get(url, {'is_active': True})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertTrue(response.data['data'][0]['is_active'])

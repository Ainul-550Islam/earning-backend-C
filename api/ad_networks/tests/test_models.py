"""
api/ad_networks/tests/test_models.py
Tests for all models in the ad_networks module
SaaS-ready with tenant support
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import timedelta

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


class TestAdNetworkModel(TestCase):
    """Test AdNetwork model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa',
            api_key='test_api_key_123',
            api_secret='test_secret_123',
            webhook_url='https://example.com/webhook'
        )
    
    def test_ad_network_creation(self):
        """Test AdNetwork creation"""
        self.assertEqual(self.ad_network.name, 'Test Network')
        self.assertEqual(self.ad_network.network_type, 'cpa')
        self.assertEqual(self.ad_network.tenant_id, self.tenant_id)
        self.assertTrue(self.ad_network.is_active)
    
    def test_ad_network_str(self):
        """Test AdNetwork string representation"""
        self.assertEqual(str(self.ad_network), 'Test Network')
    
    def test_ad_network_config_json(self):
        """Test AdNetwork config JSON field"""
        config = {'timeout': 30, 'retries': 3}
        self.ad_network.config = config
        self.ad_network.save()
        
        self.assertEqual(self.ad_network.config, config)


class TestOfferCategoryModel(TestCase):
    """Test OfferCategory model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.category = OfferCategory.objects.create(
            tenant_id=self.tenant_id,
            name='Test Category',
            slug='test-category',
            category_type='surveys',
            color='#FF0000'
        )
    
    def test_offer_category_creation(self):
        """Test OfferCategory creation"""
        self.assertEqual(self.category.name, 'Test Category')
        self.assertEqual(self.category.slug, 'test-category')
        self.assertEqual(self.category.tenant_id, self.tenant_id)
        self.assertTrue(self.category.is_active)
    
    def test_offer_category_str(self):
        """Test OfferCategory string representation"""
        self.assertEqual(str(self.category), 'Test Category')


class TestOfferModel(TestCase):
    """Test Offer model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            difficulty='easy',
            estimated_time=10,
            status='active'
        )
    
    def test_offer_creation(self):
        """Test Offer creation"""
        self.assertEqual(self.offer.title, 'Test Offer')
        self.assertEqual(self.offer.ad_network, self.ad_network)
        self.assertEqual(self.offer.category, self.category)
        self.assertEqual(self.offer.reward_amount, Decimal('10.00'))
        self.assertEqual(self.offer.tenant_id, self.tenant_id)
    
    def test_offer_str(self):
        """Test Offer string representation"""
        self.assertEqual(str(self.offer), 'Test Offer')
    
    def test_offer_countries_list(self):
        """Test Offer countries list field"""
        countries = ['US', 'GB', 'CA']
        self.offer.countries = countries
        self.offer.save()
        
        self.assertEqual(self.offer.countries, countries)


class TestUserOfferEngagementModel(TestCase):
    """Test UserOfferEngagement model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            click_id='test_click_123',
            status='started',
            ip_address='127.0.0.1'
        )
    
    def test_engagement_creation(self):
        """Test UserOfferEngagement creation"""
        self.assertEqual(self.engagement.user, self.user)
        self.assertEqual(self.engagement.offer, self.offer)
        self.assertEqual(self.engagement.click_id, 'test_click_123')
        self.assertEqual(self.engagement.status, 'started')
        self.assertEqual(self.engagement.tenant_id, self.tenant_id)
    
    def test_engagement_str(self):
        """Test UserOfferEngagement string representation"""
        expected = f"{self.user.username} - {self.offer.title}"
        self.assertEqual(str(self.engagement), expected)


class TestOfferConversionModel(TestCase):
    """Test OfferConversion model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
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
            payout=Decimal('10.00'),
            currency='USD'
        )
    
    def test_conversion_creation(self):
        """Test OfferConversion creation"""
        self.assertEqual(self.conversion.engagement, self.engagement)
        self.assertEqual(self.conversion.conversion_id, 'conv_123')
        self.assertEqual(self.conversion.conversion_status, 'pending')
        self.assertEqual(self.conversion.payout, Decimal('10.00'))
        self.assertEqual(self.conversion.tenant_id, self.tenant_id)
    
    def test_conversion_str(self):
        """Test OfferConversion string representation"""
        expected = f"Conversion {self.conversion.conversion_id}"
        self.assertEqual(str(self.conversion), expected)


class TestFraudDetectionRuleModel(TestCase):
    """Test FraudDetectionRule model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.rule = FraudDetectionRule.objects.create(
            tenant_id=self.tenant_id,
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='ip_based',
            action='block',
            severity='high',
            priority=80,
            conditions={'field': 'ip_address', 'operator': 'in_list'}
        )
    
    def test_fraud_rule_creation(self):
        """Test FraudDetectionRule creation"""
        self.assertEqual(self.rule.name, 'Test Rule')
        self.assertEqual(self.rule.rule_type, 'ip_based')
        self.assertEqual(self.rule.action, 'block')
        self.assertEqual(self.rule.severity, 'high')
        self.assertEqual(self.rule.tenant_id, self.tenant_id)
    
    def test_fraud_rule_str(self):
        """Test FraudDetectionRule string representation"""
        self.assertEqual(str(self.rule), 'Test Rule')


class TestBlacklistedIPModel(TestCase):
    """Test BlacklistedIP model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.blacklisted_ip = BlacklistedIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.100',
            reason='fraud',
            description='Suspicious activity detected'
        )
    
    def test_blacklisted_ip_creation(self):
        """Test BlacklistedIP creation"""
        self.assertEqual(self.blacklisted_ip.ip_address, '192.168.1.100')
        self.assertEqual(self.blacklisted_ip.reason, 'fraud')
        self.assertEqual(self.blacklisted_ip.tenant_id, self.tenant_id)
        self.assertTrue(self.blacklisted_ip.is_active)
    
    def test_blacklisted_ip_str(self):
        """Test BlacklistedIP string representation"""
        self.assertEqual(str(self.blacklisted_ip), '192.168.1.100')


class TestOfferClickModel(TestCase):
    """Test OfferClick model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.click = OfferClick.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            click_id='click_123',
            ip_address='127.0.0.1',
            is_unique=True
        )
    
    def test_offer_click_creation(self):
        """Test OfferClick creation"""
        self.assertEqual(self.click.user, self.user)
        self.assertEqual(self.click.offer, self.offer)
        self.assertEqual(self.click.click_id, 'click_123')
        self.assertEqual(self.click.ip_address, '127.0.0.1')
        self.assertTrue(self.click.is_unique)
        self.assertEqual(self.click.tenant_id, self.tenant_id)
    
    def test_offer_click_str(self):
        """Test OfferClick string representation"""
        expected = f"Click {self.click.click_id}"
        self.assertEqual(str(self.click), expected)


class TestOfferRewardModel(TestCase):
    """Test OfferReward model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
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
    
    def test_offer_reward_creation(self):
        """Test OfferReward creation"""
        self.assertEqual(self.reward.user, self.user)
        self.assertEqual(self.reward.offer, self.offer)
        self.assertEqual(self.reward.engagement, self.engagement)
        self.assertEqual(self.reward.amount, Decimal('10.00'))
        self.assertEqual(self.reward.status, 'pending')
        self.assertEqual(self.reward.tenant_id, self.tenant_id)
    
    def test_offer_reward_str(self):
        """Test OfferReward string representation"""
        expected = f"Reward {self.reward.id}"
        self.assertEqual(str(self.reward), expected)


class TestOfferTagModel(TestCase):
    """Test OfferTag model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tag = OfferTag.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tag',
            slug='test-tag',
            color='#FF0000',
            created_by=self.user
        )
    
    def test_offer_tag_creation(self):
        """Test OfferTag creation"""
        self.assertEqual(self.tag.name, 'Test Tag')
        self.assertEqual(self.tag.slug, 'test-tag')
        self.assertEqual(self.tag.color, '#FF0000')
        self.assertEqual(self.tag.created_by, self.user)
        self.assertEqual(self.tag.tenant_id, self.tenant_id)
    
    def test_offer_tag_str(self):
        """Test OfferTag string representation"""
        self.assertEqual(str(self.tag), 'Test Tag')


class TestNetworkHealthCheckModel(TestCase):
    """Test NetworkHealthCheck model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.health_check = NetworkHealthCheck.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            check_type='connection_test',
            endpoint_checked='https://example.com',
            is_healthy=True,
            status_code=200,
            response_time_ms=150
        )
    
    def test_network_health_check_creation(self):
        """Test NetworkHealthCheck creation"""
        self.assertEqual(self.health_check.network, self.ad_network)
        self.assertEqual(self.health_check.check_type, 'connection_test')
        self.assertEqual(self.health_check.endpoint_checked, 'https://example.com')
        self.assertTrue(self.health_check.is_healthy)
        self.assertEqual(self.health_check.status_code, 200)
        self.assertEqual(self.health_check.tenant_id, self.tenant_id)
    
    def test_network_health_check_str(self):
        """Test NetworkHealthCheck string representation"""
        expected = f"Health check for {self.ad_network.name}"
        self.assertEqual(str(self.health_check), expected)


class TestOfferPerformanceAnalyticsModel(TestCase):
    """Test OfferPerformanceAnalytics model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.analytics = OfferPerformanceAnalytics.objects.create(
            tenant_id=self.tenant_id,
            offer=self.offer,
            date=timezone.now().date(),
            clicks=100,
            conversions=10,
            revenue=Decimal('100.00'),
            cost=Decimal('50.00')
        )
    
    def test_analytics_creation(self):
        """Test OfferPerformanceAnalytics creation"""
        self.assertEqual(self.analytics.offer, self.offer)
        self.assertEqual(self.analytics.clicks, 100)
        self.assertEqual(self.analytics.conversions, 10)
        self.assertEqual(self.analytics.revenue, Decimal('100.00'))
        self.assertEqual(self.analytics.cost, Decimal('50.00'))
        self.assertEqual(self.analytics.tenant_id, self.tenant_id)
    
    def test_analytics_profit_calculation(self):
        """Test profit calculation"""
        expected_profit = self.analytics.revenue - self.analytics.cost
        self.assertEqual(self.analytics.profit, expected_profit)


class TestSmartOfferRecommendationModel(TestCase):
    """Test SmartOfferRecommendation model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.recommendation = SmartOfferRecommendation.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            score=85.5
        )
    
    def test_recommendation_creation(self):
        """Test SmartOfferRecommendation creation"""
        self.assertEqual(self.recommendation.user, self.user)
        self.assertEqual(self.recommendation.offer, self.offer)
        self.assertEqual(self.recommendation.score, 85.5)
        self.assertFalse(self.recommendation.is_displayed)
        self.assertEqual(self.recommendation.tenant_id, self.tenant_id)
    
    def test_recommendation_str(self):
        """Test SmartOfferRecommendation string representation"""
        expected = f"Recommendation: {self.offer.title} for {self.user.username}"
        self.assertEqual(str(self.recommendation), expected)


class TestOfferWallModel(TestCase):
    """Test OfferWall model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.offer_wall = OfferWall.objects.create(
            tenant_id=self.tenant_id,
            name='Test Offer Wall',
            wall_type='standard',
            min_payout=Decimal('5.00'),
            max_payout=Decimal('100.00')
        )
    
    def test_offer_wall_creation(self):
        """Test OfferWall creation"""
        self.assertEqual(self.offer_wall.name, 'Test Offer Wall')
        self.assertEqual(self.offer_wall.wall_type, 'standard')
        self.assertEqual(self.offer_wall.min_payout, Decimal('5.00'))
        self.assertEqual(self.offer_wall.max_payout, Decimal('100.00'))
        self.assertEqual(self.offer_wall.tenant_id, self.tenant_id)
    
    def test_offer_wall_str(self):
        """Test OfferWall string representation"""
        self.assertEqual(str(self.offer_wall), 'Test Offer Wall')


# Test remaining models with similar structure...

class TestKnownBadIPModel(TestCase):
    """Test KnownBadIP model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.bad_ip = KnownBadIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.200',
            threat_type='malware',
            source='external_feed',
            confidence_score=95.0
        )
    
    def test_known_bad_ip_creation(self):
        """Test KnownBadIP creation"""
        self.assertEqual(self.bad_ip.ip_address, '192.168.1.200')
        self.assertEqual(self.bad_ip.threat_type, 'malware')
        self.assertEqual(self.bad_ip.source, 'external_feed')
        self.assertEqual(self.bad_ip.confidence_score, 95.0)
        self.assertEqual(self.bad_ip.tenant_id, self.tenant_id)


class TestNetworkAPILogModel(TestCase):
    """Test NetworkAPILog model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.api_log = NetworkAPILog.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            method='GET',
            endpoint='/api/offers',
            status_code=200,
            is_success=True
        )
    
    def test_network_api_log_creation(self):
        """Test NetworkAPILog creation"""
        self.assertEqual(self.api_log.network, self.ad_network)
        self.assertEqual(self.api_log.method, 'GET')
        self.assertEqual(self.api_log.endpoint, '/api/offers')
        self.assertEqual(self.api_log.status_code, 200)
        self.assertTrue(self.api_log.is_success)
        self.assertEqual(self.api_log.tenant_id, self.tenant_id)


class TestOfferTaggingModel(TestCase):
    """Test OfferTagging model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
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
    
    def test_offer_tagging_creation(self):
        """Test OfferTagging creation"""
        self.assertEqual(self.tagging.offer, self.offer)
        self.assertEqual(self.tagging.tag, self.tag)
        self.assertEqual(self.tagging.added_by, self.user)
        self.assertEqual(self.tagging.confidence_score, 90.0)
        self.assertEqual(self.tagging.tenant_id, self.tenant_id)


class TestUserOfferLimitModel(TestCase):
    """Test UserOfferLimit model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.limit = UserOfferLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=5,
            total_limit=50
        )
    
    def test_user_offer_limit_creation(self):
        """Test UserOfferLimit creation"""
        self.assertEqual(self.limit.user, self.user)
        self.assertEqual(self.limit.offer, self.offer)
        self.assertEqual(self.limit.daily_limit, 5)
        self.assertEqual(self.limit.total_limit, 50)
        self.assertEqual(self.limit.tenant_id, self.tenant_id)


class TestOfferSyncLogModel(TestCase):
    """Test OfferSyncLog model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.sync_log = OfferSyncLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            sync_type='manual',
            status='completed',
            offers_fetched=100,
            offers_created=50,
            offers_updated=25
        )
    
    def test_offer_sync_log_creation(self):
        """Test OfferSyncLog creation"""
        self.assertEqual(self.sync_log.ad_network, self.ad_network)
        self.assertEqual(self.sync_log.sync_type, 'manual')
        self.assertEqual(self.sync_log.status, 'completed')
        self.assertEqual(self.sync_log.offers_fetched, 100)
        self.assertEqual(self.sync_log.offers_created, 50)
        self.assertEqual(self.sync_log.tenant_id, self.tenant_id)


class TestAdNetworkWebhookLogModel(TestCase):
    """Test AdNetworkWebhookLog model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.webhook_log = AdNetworkWebhookLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            event_type='offer.created',
            payload={'offer_id': 123},
            processed=True
        )
    
    def test_webhook_log_creation(self):
        """Test AdNetworkWebhookLog creation"""
        self.assertEqual(self.webhook_log.ad_network, self.ad_network)
        self.assertEqual(self.webhook_log.event_type, 'offer.created')
        self.assertEqual(self.webhook_log.payload, {'offer_id': 123})
        self.assertTrue(self.webhook_log.processed)
        self.assertEqual(self.webhook_log.tenant_id, self.tenant_id)


class TestOfferDailyLimitModel(TestCase):
    """Test OfferDailyLimit model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
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
            reward_currency='USD'
        )
        self.daily_limit = OfferDailyLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=10,
            count_today=3
        )
    
    def test_offer_daily_limit_creation(self):
        """Test OfferDailyLimit creation"""
        self.assertEqual(self.daily_limit.user, self.user)
        self.assertEqual(self.daily_limit.offer, self.offer)
        self.assertEqual(self.daily_limit.daily_limit, 10)
        self.assertEqual(self.daily_limit.count_today, 3)
        self.assertEqual(self.daily_limit.tenant_id, self.tenant_id)


class TestNetworkStatisticModel(TestCase):
    """Test NetworkStatistic model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.ad_network = AdNetwork.objects.create(
            tenant_id=self.tenant_id,
            name='Test Network',
            network_type='cpa'
        )
        self.statistic = NetworkStatistic.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            date=timezone.now().date(),
            clicks=1000,
            conversions=100,
            payout=Decimal('1000.00'),
            commission=Decimal('100.00')
        )
    
    def test_network_statistic_creation(self):
        """Test NetworkStatistic creation"""
        self.assertEqual(self.statistic.network, self.ad_network)
        self.assertEqual(self.statistic.clicks, 1000)
        self.assertEqual(self.statistic.conversions, 100)
        self.assertEqual(self.statistic.payout, Decimal('1000.00'))
        self.assertEqual(self.statistic.commission, Decimal('100.00'))
        self.assertEqual(self.statistic.tenant_id, self.tenant_id)


class TestOfferAttachmentModel(TestCase):
    """Test OfferAttachment model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
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
        # Create a mock file for testing
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        self.attachment = OfferAttachment.objects.create(
            tenant_id=self.tenant_id,
            offer=self.offer,
            file=SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg"),
            filename='test.jpg',
            original_filename='original_test.jpg',
            file_type='image',
            mime_type='image/jpeg',
            file_size=1024,
            file_hash='abc123def456',
            width=800,
            height=600,
            description='Test attachment',
            is_primary=True,
            display_order=1
        )
    
    def test_offer_attachment_creation(self):
        """Test OfferAttachment creation"""
        self.assertEqual(self.attachment.offer, self.offer)
        self.assertEqual(self.attachment.filename, 'test.jpg')
        self.assertEqual(self.attachment.file_type, 'image')
        self.assertEqual(self.attachment.mime_type, 'image/jpeg')
        self.assertEqual(self.attachment.file_size, 1024)
        self.assertEqual(self.attachment.is_primary, True)
        self.assertEqual(self.attachment.display_order, 1)
        self.assertEqual(self.attachment.tenant_id, self.tenant_id)
    
    def test_offer_attachment_str(self):
        """Test OfferAttachment string representation"""
        expected = f"{self.offer.title} - {self.attachment.filename}"
        self.assertEqual(str(self.attachment), expected)


class TestUserWalletModel(TestCase):
    """Test UserWallet model"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
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
    
    def test_user_wallet_creation(self):
        """Test UserWallet creation"""
        self.assertEqual(self.wallet.user, self.user)
        self.assertEqual(self.wallet.current_balance, Decimal('1000.50'))
        self.assertEqual(self.wallet.total_earned, Decimal('1500.00'))
        self.assertEqual(self.wallet.total_withdrawn, Decimal('400.00'))
        self.assertEqual(self.wallet.pending_balance, Decimal('50.00'))
        self.assertEqual(self.wallet.currency, 'BDT')
        self.assertTrue(self.wallet.is_active)
        self.assertFalse(self.wallet.is_frozen)
        self.assertEqual(self.wallet.daily_limit, Decimal('5000.00'))
        self.assertEqual(self.wallet.monthly_limit, Decimal('100000.00'))
        self.assertEqual(self.wallet.tenant_id, self.tenant_id)
    
    def test_user_wallet_str(self):
        """Test UserWallet string representation"""
        expected = f"{self.user.username} - {self.wallet.current_balance} {self.wallet.currency}"
        self.assertEqual(str(self.wallet), expected)
    
    def test_available_balance_property(self):
        """Test available_balance property"""
        expected_available = self.wallet.current_balance - self.wallet.pending_balance
        self.assertEqual(self.wallet.available_balance, expected_available)
    
    def test_can_withdraw_method(self):
        """Test can_withdraw method"""
        # Test valid withdrawal
        self.assertTrue(self.wallet.can_withdraw(Decimal('500.00')))
        
        # Test withdrawal exceeding available balance
        self.assertFalse(self.wallet.can_withdraw(Decimal('2000.00')))
        
        # Test withdrawal when frozen
        self.wallet.is_frozen = True
        self.wallet.save()
        self.assertFalse(self.wallet.can_withdraw(Decimal('100.00')))
        
        # Test withdrawal when inactive
        self.wallet.is_frozen = False
        self.wallet.is_active = False
        self.wallet.save()
        self.assertFalse(self.wallet.can_withdraw(Decimal('100.00')))

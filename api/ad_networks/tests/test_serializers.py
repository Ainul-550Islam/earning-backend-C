"""
api/ad_networks/tests/test_serializers.py
Tests for all serializers in the ad_networks module
SaaS-ready with tenant support
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import serializers
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
from ..serializers import (
    AdNetworkSerializer, AdNetworkDetailSerializer,
    OfferCategorySerializer, OfferSerializer, OfferDetailSerializer, OfferListSerializer,
    UserOfferEngagementSerializer, UserOfferEngagementDetailSerializer,
    OfferConversionSerializer, OfferWallSerializer,
    FraudDetectionRuleSerializer, BlacklistedIPSerializer, KnownBadIPSerializer,
    NetworkHealthCheckSerializer, OfferPerformanceAnalyticsSerializer,
    OfferClickSerializer, OfferRewardSerializer, NetworkAPILogSerializer,
    OfferTagSerializer, OfferTaggingSerializer, SmartOfferRecommendationSerializer,
    NetworkStatisticSerializer, UserOfferLimitSerializer, OfferSyncLogSerializer,
    AdNetworkWebhookLogSerializer, OfferDailyLimitSerializer,
    OfferAttachmentSerializer, UserWalletSerializer
)

User = get_user_model()


class BaseSerializerTestCase(TestCase):
    """Base test case for serializers"""
    
    def setUp(self):
        self.tenant_id = 'test_tenant_123'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
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


class TestAdNetworkSerializer(BaseSerializerTestCase):
    """Test AdNetworkSerializer"""
    
    def test_ad_network_serialization(self):
        """Test AdNetwork serialization"""
        serializer = AdNetworkSerializer(self.ad_network)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Network')
        self.assertEqual(data['network_type'], 'cpa')
        self.assertEqual(data['is_active'], True)
        self.assertIn('active_offers_count', data)
        self.assertIn('total_conversions', data)
        self.assertIn('health_status', data)
    
    def test_ad_network_creation(self):
        """Test AdNetwork creation through serializer"""
        data = {
            'name': 'New Network',
            'network_type': 'cps',
            'api_key': 'new_api_key_123',
            'webhook_url': 'https://example.com/webhook'
        }
        serializer = AdNetworkSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        network = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(network.name, 'New Network')
        self.assertEqual(network.network_type, 'cps')
        self.assertEqual(network.tenant_id, self.tenant_id)
    
    def test_api_key_validation(self):
        """Test API key validation"""
        data = {
            'name': 'Test Network',
            'network_type': 'cpa',
            'api_key': 'short'  # Too short
        }
        serializer = AdNetworkSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('api_key', serializer.errors)
    
    def test_config_validation(self):
        """Test config JSON validation"""
        data = {
            'name': 'Test Network',
            'network_type': 'cpa',
            'api_key': 'test_api_key_123',
            'config': 'invalid json'  # Invalid JSON
        }
        serializer = AdNetworkSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('config', serializer.errors)


class TestOfferCategorySerializer(BaseSerializerTestCase):
    """Test OfferCategorySerializer"""
    
    def test_offer_category_serialization(self):
        """Test OfferCategory serialization"""
        serializer = OfferCategorySerializer(self.category)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Category')
        self.assertEqual(data['slug'], 'test-category')
        self.assertEqual(data['is_active'], True)
        self.assertIn('offers_count', data)
        self.assertIn('total_conversions', data)
        self.assertIn('avg_reward', data)
    
    def test_offer_category_creation(self):
        """Test OfferCategory creation through serializer"""
        data = {
            'name': 'New Category',
            'slug': 'new-category',
            'category_type': 'surveys',
            'color': '#FF0000'
        }
        serializer = OfferCategorySerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        category = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(category.name, 'New Category')
        self.assertEqual(category.category_type, 'surveys')
        self.assertEqual(category.tenant_id, self.tenant_id)
    
    def test_color_validation(self):
        """Test color validation"""
        data = {
            'name': 'Test Category',
            'slug': 'test-category',
            'color': 'invalid'  # Invalid hex color
        }
        serializer = OfferCategorySerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('color', serializer.errors)


class TestOfferSerializer(BaseSerializerTestCase):
    """Test OfferSerializer"""
    
    def test_offer_serialization(self):
        """Test Offer serialization"""
        serializer = OfferSerializer(self.offer)
        data = serializer.data
        
        self.assertEqual(data['title'], 'Test Offer')
        self.assertEqual(data['reward_amount'], '10.00')
        self.assertEqual(data['reward_currency'], 'USD')
        self.assertEqual(data['status'], 'active')
        self.assertIn('formatted_reward', data)
        self.assertIn('conversion_rate', data)
        self.assertIn('user_status', data)
    
    def test_offer_creation(self):
        """Test Offer creation through serializer"""
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
        serializer = OfferSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        offer = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(offer.title, 'New Offer')
        self.assertEqual(offer.reward_amount, Decimal('15.00'))
        self.assertEqual(offer.tenant_id, self.tenant_id)
    
    def test_reward_amount_validation(self):
        """Test reward amount validation"""
        data = {
            'title': 'Test Offer',
            'ad_network': self.ad_network.pk,
            'category': self.category.pk,
            'reward_amount': '-5.00',  # Negative amount
            'reward_currency': 'USD'
        }
        serializer = OfferSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('reward_amount', serializer.errors)
    
    def test_countries_validation(self):
        """Test countries validation"""
        data = {
            'title': 'Test Offer',
            'ad_network': self.ad_network.pk,
            'category': self.category.pk,
            'reward_amount': '10.00',
            'reward_currency': 'USD',
            'countries': ['INVALID']  # Invalid country code
        }
        serializer = OfferSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('countries', serializer.errors)


class TestUserOfferEngagementSerializer(BaseSerializerTestCase):
    """Test UserOfferEngagementSerializer"""
    
    def setUp(self):
        super().setUp()
        self.engagement = UserOfferEngagement.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            status='started',
            ip_address='127.0.0.1'
        )
    
    def test_engagement_serialization(self):
        """Test UserOfferEngagement serialization"""
        serializer = UserOfferEngagementSerializer(self.engagement)
        data = serializer.data
        
        self.assertEqual(data['status'], 'started')
        self.assertEqual(data['ip_address'], '127.0.0.1')
        self.assertIn('offer_title', data)
        self.assertIn('reward_formatted', data)
        self.assertIn('time_spent', data)
    
    def test_engagement_creation(self):
        """Test UserOfferEngagement creation through serializer"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'click_id': 'new_click_123',
            'status': 'clicked',
            'ip_address': '192.168.1.100'
        }
        serializer = UserOfferEngagementSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        engagement = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(engagement.user, self.user)
        self.assertEqual(engagement.offer, self.offer)
        self.assertEqual(engagement.status, 'clicked')
        self.assertEqual(engagement.tenant_id, self.tenant_id)
    
    def test_ip_address_validation(self):
        """Test IP address validation"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'ip_address': 'invalid_ip'  # Invalid IP
        }
        serializer = UserOfferEngagementSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip_address', serializer.errors)


class TestOfferConversionSerializer(BaseSerializerTestCase):
    """Test OfferConversionSerializer"""
    
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
    
    def test_conversion_serialization(self):
        """Test OfferConversion serialization"""
        serializer = OfferConversionSerializer(self.conversion)
        data = serializer.data
        
        self.assertEqual(data['conversion_id'], 'conv_123')
        self.assertEqual(data['conversion_status'], 'pending')
        self.assertEqual(data['payout'], '10.00')
        self.assertIn('engagement_details', data)
        self.assertIn('user_info', data)
        self.assertIn('offer_info', data)
    
    def test_conversion_creation(self):
        """Test OfferConversion creation through serializer"""
        data = {
            'engagement': self.engagement.pk,
            'conversion_id': 'new_conv_123',
            'conversion_status': 'pending',
            'payout': '15.00',
            'currency': 'USD'
        }
        serializer = OfferConversionSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        conversion = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(conversion.engagement, self.engagement)
        self.assertEqual(conversion.conversion_id, 'new_conv_123')
        self.assertEqual(conversion.payout, Decimal('15.00'))
        self.assertEqual(conversion.tenant_id, self.tenant_id)


class TestFraudDetectionRuleSerializer(BaseSerializerTestCase):
    """Test FraudDetectionRuleSerializer"""
    
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
    
    def test_fraud_rule_serialization(self):
        """Test FraudDetectionRule serialization"""
        serializer = FraudDetectionRuleSerializer(self.rule)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Rule')
        self.assertEqual(data['rule_type'], 'ip_based')
        self.assertEqual(data['action'], 'block')
        self.assertEqual(data['severity'], 'high')
        self.assertIn('rule_type_display', data)
        self.assertIn('action_display', data)
    
    def test_fraud_rule_creation(self):
        """Test FraudDetectionRule creation through serializer"""
        data = {
            'name': 'New Rule',
            'rule_type': 'frequency_based',
            'action': 'flag',
            'severity': 'medium',
            'priority': 60,
            'conditions': {'field': 'user_id', 'operator': 'count', 'value': 10}
        }
        serializer = FraudDetectionRuleSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        rule = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(rule.name, 'New Rule')
        self.assertEqual(rule.rule_type, 'frequency_based')
        self.assertEqual(rule.tenant_id, self.tenant_id)
    
    def test_priority_validation(self):
        """Test priority validation"""
        data = {
            'name': 'Test Rule',
            'rule_type': 'ip_based',
            'action': 'block',
            'priority': 150  # Too high
        }
        serializer = FraudDetectionRuleSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('priority', serializer.errors)


class TestBlacklistedIPSerializer(BaseSerializerTestCase):
    """Test BlacklistedIPSerializer"""
    
    def setUp(self):
        super().setUp()
        self.blacklisted_ip = BlacklistedIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.100',
            reason='fraud',
            description='Suspicious activity'
        )
    
    def test_blacklisted_ip_serialization(self):
        """Test BlacklistedIP serialization"""
        serializer = BlacklistedIPSerializer(self.blacklisted_ip)
        data = serializer.data
        
        self.assertEqual(data['ip_address'], '192.168.1.100')
        self.assertEqual(data['reason'], 'fraud')
        self.assertEqual(data['is_active'], True)
        self.assertIn('reason_display', data)
        self.assertIn('expiry_countdown', data)
        self.assertIn('threat_level', data)
    
    def test_blacklisted_ip_creation(self):
        """Test BlacklistedIP creation through serializer"""
        data = {
            'ip_address': '192.168.1.200',
            'reason': 'spam',
            'description': 'Spam activity detected'
        }
        serializer = BlacklistedIPSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        blacklisted_ip = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(blacklisted_ip.ip_address, '192.168.1.200')
        self.assertEqual(blacklisted_ip.reason, 'spam')
        self.assertEqual(blacklisted_ip.tenant_id, self.tenant_id)


class TestOfferClickSerializer(BaseSerializerTestCase):
    """Test OfferClickSerializer"""
    
    def setUp(self):
        super().setUp()
        self.click = OfferClick.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            click_id='click_123',
            ip_address='127.0.0.1',
            is_unique=True
        )
    
    def test_offer_click_serialization(self):
        """Test OfferClick serialization"""
        serializer = OfferClickSerializer(self.click)
        data = serializer.data
        
        self.assertEqual(data['click_id'], 'click_123')
        self.assertEqual(data['ip_address'], '127.0.0.1')
        self.assertTrue(data['is_unique'])
        self.assertIn('user_display', data)
        self.assertIn('offer_title', data)
        self.assertIn('fraud_level', data)
    
    def test_offer_click_creation(self):
        """Test OfferClick creation through serializer"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'click_id': 'new_click_123',
            'ip_address': '192.168.1.100',
            'is_unique': False
        }
        serializer = OfferClickSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        click = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(click.user, self.user)
        self.assertEqual(click.offer, self.offer)
        self.assertEqual(click.click_id, 'new_click_123')
        self.assertEqual(click.tenant_id, self.tenant_id)
    
    def test_ip_address_validation(self):
        """Test IP address validation"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'ip_address': 'invalid_ip'  # Invalid IP
        }
        serializer = OfferClickSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip_address', serializer.errors)


class TestOfferRewardSerializer(BaseSerializerTestCase):
    """Test OfferRewardSerializer"""
    
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
    
    def test_offer_reward_serialization(self):
        """Test OfferReward serialization"""
        serializer = OfferRewardSerializer(self.reward)
        data = serializer.data
        
        self.assertEqual(data['amount'], '10.00')
        self.assertEqual(data['currency'], 'USD')
        self.assertEqual(data['status'], 'pending')
        self.assertIn('user_display', data)
        self.assertIn('offer_title', data)
        self.assertIn('formatted_amount', data)
    
    def test_offer_reward_creation(self):
        """Test OfferReward creation through serializer"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'engagement': self.engagement.pk,
            'amount': '15.00',
            'currency': 'USD',
            'status': 'pending'
        }
        serializer = OfferRewardSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        reward = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(reward.user, self.user)
        self.assertEqual(reward.offer, self.offer)
        self.assertEqual(reward.amount, Decimal('15.00'))
        self.assertEqual(reward.tenant_id, self.tenant_id)
    
    def test_amount_validation(self):
        """Test amount validation"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'amount': '-5.00',  # Negative amount
            'currency': 'USD'
        }
        serializer = OfferRewardSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('amount', serializer.errors)


class TestOfferTagSerializer(BaseSerializerTestCase):
    """Test OfferTagSerializer"""
    
    def setUp(self):
        super().setUp()
        self.tag = OfferTag.objects.create(
            tenant_id=self.tenant_id,
            name='Test Tag',
            slug='test-tag',
            color='#FF0000',
            created_by=self.user
        )
    
    def test_offer_tag_serialization(self):
        """Test OfferTag serialization"""
        serializer = OfferTagSerializer(self.tag)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Tag')
        self.assertEqual(data['slug'], 'test-tag')
        self.assertEqual(data['color'], '#FF0000')
        self.assertEqual(data['is_active'], True)
        self.assertIn('usage_count', data)
        self.assertIn('created_by_display', data)
    
    def test_offer_tag_creation(self):
        """Test OfferTag creation through serializer"""
        data = {
            'name': 'New Tag',
            'slug': 'new-tag',
            'color': '#00FF00'
        }
        serializer = OfferTagSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        tag = serializer.save(tenant_id=self.tenant_id, created_by=self.user)
        
        self.assertEqual(tag.name, 'New Tag')
        self.assertEqual(tag.slug, 'new-tag')
        self.assertEqual(tag.tenant_id, self.tenant_id)
    
    def test_color_validation(self):
        """Test color validation"""
        data = {
            'name': 'Test Tag',
            'slug': 'test-tag',
            'color': 'invalid'  # Invalid hex color
        }
        serializer = OfferTagSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('color', serializer.errors)


class TestNetworkHealthCheckSerializer(BaseSerializerTestCase):
    """Test NetworkHealthCheckSerializer"""
    
    def setUp(self):
        super().setUp()
        self.health_check = NetworkHealthCheck.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            check_type='connection_test',
            endpoint_checked='https://example.com',
            is_healthy=True,
            status_code=200,
            response_time_ms=150
        )
    
    def test_health_check_serialization(self):
        """Test NetworkHealthCheck serialization"""
        serializer = NetworkHealthCheckSerializer(self.health_check)
        data = serializer.data
        
        self.assertEqual(data['check_type'], 'connection_test')
        self.assertEqual(data['endpoint_checked'], 'https://example.com')
        self.assertTrue(data['is_healthy'])
        self.assertEqual(data['status_code'], 200)
        self.assertIn('network_name', data)
        self.assertIn('check_type_display', data)
        self.assertIn('status_display', data)
        self.assertIn('response_time_display', data)
    
    def test_health_check_creation(self):
        """Test NetworkHealthCheck creation through serializer"""
        data = {
            'network': self.ad_network.pk,
            'check_type': 'api_test',
            'endpoint_checked': 'https://api.example.com',
            'is_healthy': False,
            'status_code': 500
        }
        serializer = NetworkHealthCheckSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        health_check = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(health_check.network, self.ad_network)
        self.assertEqual(health_check.check_type, 'api_test')
        self.assertEqual(health_check.tenant_id, self.tenant_id)


class TestOfferPerformanceAnalyticsSerializer(BaseSerializerTestCase):
    """Test OfferPerformanceAnalyticsSerializer"""
    
    def setUp(self):
        super().setUp()
        self.analytics = OfferPerformanceAnalytics.objects.create(
            tenant_id=self.tenant_id,
            offer=self.offer,
            date=timezone.now().date(),
            clicks=100,
            conversions=10,
            revenue=Decimal('100.00'),
            cost=Decimal('50.00')
        )
    
    def test_analytics_serialization(self):
        """Test OfferPerformanceAnalytics serialization"""
        serializer = OfferPerformanceAnalyticsSerializer(self.analytics)
        data = serializer.data
        
        self.assertEqual(data['clicks'], 100)
        self.assertEqual(data['conversions'], 10)
        self.assertEqual(data['revenue'], '100.00')
        self.assertEqual(data['cost'], '50.00')
        self.assertIn('offer_title', data)
        self.assertIn('performance_grade', data)
        self.assertIn('trend_indicator', data)
    
    def test_analytics_creation(self):
        """Test OfferPerformanceAnalytics creation through serializer"""
        data = {
            'offer': self.offer.pk,
            'date': timezone.now().date(),
            'clicks': 200,
            'conversions': 20,
            'revenue': '200.00',
            'cost': '100.00'
        }
        serializer = OfferPerformanceAnalyticsSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        analytics = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(analytics.offer, self.offer)
        self.assertEqual(analytics.clicks, 200)
        self.assertEqual(analytics.conversions, 20)
        self.assertEqual(analytics.tenant_id, self.tenant_id)


# Test remaining serializers...

class TestKnownBadIPSerializer(BaseSerializerTestCase):
    """Test KnownBadIPSerializer"""
    
    def setUp(self):
        super().setUp()
        self.bad_ip = KnownBadIP.objects.create(
            tenant_id=self.tenant_id,
            ip_address='192.168.1.200',
            threat_type='malware',
            source='external_feed',
            confidence_score=95.0
        )
    
    def test_known_bad_ip_serialization(self):
        """Test KnownBadIP serialization"""
        serializer = KnownBadIPSerializer(self.bad_ip)
        data = serializer.data
        
        self.assertEqual(data['ip_address'], '192.168.1.200')
        self.assertEqual(data['threat_type'], 'malware')
        self.assertEqual(data['source'], 'external_feed')
        self.assertEqual(data['confidence_score'], 95.0)
        self.assertIn('threat_level_display', data)
        self.assertIn('source_display', data)
    
    def test_confidence_score_validation(self):
        """Test confidence score validation"""
        data = {
            'ip_address': '192.168.1.201',
            'threat_type': 'spam',
            'source': 'manual',
            'confidence_score': 150.0  # Too high
        }
        serializer = KnownBadIPSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('confidence_score', serializer.errors)


class TestNetworkAPILogSerializer(BaseSerializerTestCase):
    """Test NetworkAPILogSerializer"""
    
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
    
    def test_api_log_serialization(self):
        """Test NetworkAPILog serialization"""
        serializer = NetworkAPILogSerializer(self.api_log)
        data = serializer.data
        
        self.assertEqual(data['method'], 'GET')
        self.assertEqual(data['endpoint'], '/api/offers')
        self.assertEqual(data['status_code'], 200)
        self.assertTrue(data['is_success'])
        self.assertIn('network_name', data)
        self.assertIn('duration_ms', data)
        self.assertIn('status_display', data)


class TestOfferTaggingSerializer(BaseSerializerTestCase):
    """Test OfferTaggingSerializer"""
    
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
    
    def test_tagging_serialization(self):
        """Test OfferTagging serialization"""
        serializer = OfferTaggingSerializer(self.tagging)
        data = serializer.data
        
        self.assertEqual(data['offer'], self.offer.pk)
        self.assertEqual(data['tag'], self.tag.pk)
        self.assertEqual(data['confidence_score'], 90.0)
        self.assertIn('offer_title', data)
        self.assertIn('tag_name', data)
        self.assertIn('added_by_display', data)
    
    def test_confidence_score_validation(self):
        """Test confidence score validation"""
        data = {
            'offer': self.offer.pk,
            'tag': self.tag.pk,
            'confidence_score': 150.0  # Too high
        }
        serializer = OfferTaggingSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('confidence_score', serializer.errors)


class TestSmartOfferRecommendationSerializer(BaseSerializerTestCase):
    """Test SmartOfferRecommendationSerializer"""
    
    def setUp(self):
        super().setUp()
        self.recommendation = SmartOfferRecommendation.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            score=85.5
        )
    
    def test_recommendation_serialization(self):
        """Test SmartOfferRecommendation serialization"""
        serializer = SmartOfferRecommendationSerializer(self.recommendation)
        data = serializer.data
        
        self.assertEqual(data['user'], self.user.pk)
        self.assertEqual(data['offer'], self.offer.pk)
        self.assertEqual(data['score'], 85.5)
        self.assertFalse(data['is_displayed'])
        self.assertIn('user_display', data)
        self.assertIn('offer_title', data)
        self.assertIn('reward_amount', data)
        self.assertIn('reward_currency', data)
    
    def test_score_validation(self):
        """Test score validation"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'score': 150.0  # Too high
        }
        serializer = SmartOfferRecommendationSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('score', serializer.errors)


class TestNetworkStatisticSerializer(BaseSerializerTestCase):
    """Test NetworkStatisticSerializer"""
    
    def setUp(self):
        super().setUp()
        self.statistic = NetworkStatistic.objects.create(
            tenant_id=self.tenant_id,
            network=self.ad_network,
            date=timezone.now().date(),
            clicks=1000,
            conversions=100,
            payout=Decimal('1000.00'),
            commission=Decimal('100.00')
        )
    
    def test_statistic_serialization(self):
        """Test NetworkStatistic serialization"""
        serializer = NetworkStatisticSerializer(self.statistic)
        data = serializer.data
        
        self.assertEqual(data['network'], self.ad_network.pk)
        self.assertEqual(data['clicks'], 1000)
        self.assertEqual(data['conversions'], 100)
        self.assertEqual(data['payout'], '1000.00')
        self.assertIn('network_name', data)
        self.assertIn('conversion_rate', data)
        self.assertIn('avg_payout', data)


class TestUserOfferLimitSerializer(BaseSerializerTestCase):
    """Test UserOfferLimitSerializer"""
    
    def setUp(self):
        super().setUp()
        self.limit = UserOfferLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=5,
            total_limit=50
        )
    
    def test_limit_serialization(self):
        """Test UserOfferLimit serialization"""
        serializer = UserOfferLimitSerializer(self.limit)
        data = serializer.data
        
        self.assertEqual(data['user'], self.user.pk)
        self.assertEqual(data['offer'], self.offer.pk)
        self.assertEqual(data['daily_limit'], 5)
        self.assertEqual(data['total_limit'], 50)
        self.assertIn('user_display', data)
        self.assertIn('offer_title', data)
        self.assertIn('is_limit_reached', data)
    
    def test_limit_creation(self):
        """Test UserOfferLimit creation through serializer"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'daily_limit': 10,
            'total_limit': 100
        }
        serializer = UserOfferLimitSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        limit = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(limit.user, self.user)
        self.assertEqual(limit.offer, self.offer)
        self.assertEqual(limit.daily_limit, 10)
        self.assertEqual(limit.tenant_id, self.tenant_id)


class TestOfferSyncLogSerializer(BaseSerializerTestCase):
    """Test OfferSyncLogSerializer"""
    
    def setUp(self):
        super().setUp()
        self.sync_log = OfferSyncLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            sync_type='manual',
            status='completed',
            offers_fetched=100,
            offers_created=50,
            offers_updated=25
        )
    
    def test_sync_log_serialization(self):
        """Test OfferSyncLog serialization"""
        serializer = OfferSyncLogSerializer(self.sync_log)
        data = serializer.data
        
        self.assertEqual(data['ad_network'], self.ad_network.pk)
        self.assertEqual(data['sync_type'], 'manual')
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(data['offers_fetched'], 100)
        self.assertIn('network_name', data)
        self.assertIn('status_display', data)
        self.assertIn('duration_display', data)
    
    def test_sync_log_creation(self):
        """Test OfferSyncLog creation through serializer"""
        data = {
            'ad_network': self.ad_network.pk,
            'sync_type': 'automatic',
            'status': 'started',
            'offers_fetched': 0
        }
        serializer = OfferSyncLogSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        sync_log = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(sync_log.ad_network, self.ad_network)
        self.assertEqual(sync_log.sync_type, 'automatic')
        self.assertEqual(sync_log.tenant_id, self.tenant_id)


class TestAdNetworkWebhookLogSerializer(BaseSerializerTestCase):
    """Test AdNetworkWebhookLogSerializer"""
    
    def setUp(self):
        super().setUp()
        self.webhook_log = AdNetworkWebhookLog.objects.create(
            tenant_id=self.tenant_id,
            ad_network=self.ad_network,
            event_type='offer.created',
            payload={'offer_id': 123},
            processed=True
        )
    
    def test_webhook_log_serialization(self):
        """Test AdNetworkWebhookLog serialization"""
        serializer = AdNetworkWebhookLogSerializer(self.webhook_log)
        data = serializer.data
        
        self.assertEqual(data['ad_network'], self.ad_network.pk)
        self.assertEqual(data['event_type'], 'offer.created')
        self.assertEqual(data['payload'], {'offer_id': 123})
        self.assertTrue(data['processed'])
        self.assertIn('network_name', data)
        self.assertIn('event_type_display', data)
        self.assertIn('processing_time', data)
    
    def test_webhook_log_creation(self):
        """Test AdNetworkWebhookLog creation through serializer"""
        data = {
            'ad_network': self.ad_network.pk,
            'event_type': 'offer.updated',
            'payload': {'offer_id': 456, 'changes': ['title']},
            'processed': False
        }
        serializer = AdNetworkWebhookLogSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        webhook_log = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(webhook_log.ad_network, self.ad_network)
        self.assertEqual(webhook_log.event_type, 'offer.updated')
        self.assertEqual(webhook_log.tenant_id, self.tenant_id)


class TestOfferDailyLimitSerializer(BaseSerializerTestCase):
    """Test OfferDailyLimitSerializer"""
    
    def setUp(self):
        super().setUp()
        self.daily_limit = OfferDailyLimit.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            offer=self.offer,
            daily_limit=10,
            count_today=3
        )
    
    def test_daily_limit_serialization(self):
        """Test OfferDailyLimit serialization"""
        serializer = OfferDailyLimitSerializer(self.daily_limit)
        data = serializer.data
        
        self.assertEqual(data['user'], self.user.pk)
        self.assertEqual(data['offer'], self.offer.pk)
        self.assertEqual(data['daily_limit'], 10)
        self.assertEqual(data['count_today'], 3)
        self.assertIn('user_display', data)
        self.assertIn('offer_title', data)
        self.assertIn('is_limit_reached', data)
        self.assertIn('remaining_count', data)
    
    def test_daily_limit_creation(self):
        """Test OfferDailyLimit creation through serializer"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'daily_limit': 15,
            'count_today': 0
        }
        serializer = OfferDailyLimitSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        daily_limit = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(daily_limit.user, self.user)
        self.assertEqual(daily_limit.offer, self.offer)
        self.assertEqual(daily_limit.daily_limit, 15)
        self.assertEqual(daily_limit.tenant_id, self.tenant_id)
    
    def test_daily_limit_validation(self):
        """Test daily limit validation"""
        data = {
            'user': self.user.pk,
            'offer': self.offer.pk,
            'daily_limit': -5  # Negative limit
        }
        serializer = OfferDailyLimitSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('daily_limit', serializer.errors)


class TestOfferWallSerializer(BaseSerializerTestCase):
    """Test OfferWallSerializer"""
    
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
    
    def test_offer_wall_serialization(self):
        """Test OfferWall serialization"""
        serializer = OfferWallSerializer(self.offer_wall)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Offer Wall')
        self.assertEqual(data['wall_type'], 'standard')
        self.assertEqual(data['min_payout'], '5.00')
        self.assertEqual(data['max_payout'], '100.00')
        self.assertIn('networks_info', data)
        self.assertIn('categories_info', data)
        self.assertIn('offers_count', data)
        self.assertIn('avg_reward', data)
    
    def test_offer_wall_creation(self):
        """Test OfferWall creation through serializer"""
        data = {
            'name': 'New Offer Wall',
            'wall_type': 'premium',
            'min_payout': '10.00',
            'max_payout': '200.00'
        }
        serializer = OfferWallSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        offer_wall = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(offer_wall.name, 'New Offer Wall')
        self.assertEqual(offer_wall.wall_type, 'premium')
        self.assertEqual(offer_wall.tenant_id, self.tenant_id)


class TestOfferAttachmentSerializer(BaseSerializerTestCase):
    """Test OfferAttachmentSerializer"""
    
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
            width=800,
            height=600,
            description='Test attachment',
            is_primary=True,
            display_order=1
        )
    
    def test_offer_attachment_serialization(self):
        """Test OfferAttachment serialization"""
        serializer = OfferAttachmentSerializer(self.attachment)
        data = serializer.data
        
        self.assertEqual(data['id'], self.attachment.id)
        self.assertEqual(data['offer'], self.offer.id)
        self.assertEqual(data['filename'], 'test.jpg')
        self.assertEqual(data['file_type'], 'image')
        self.assertEqual(data['mime_type'], 'image/jpeg')
        self.assertEqual(data['file_size'], 1024)
        self.assertEqual(data['is_primary'], True)
        self.assertEqual(data['display_order'], 1)
        self.assertIn('file_size_display', data)
        self.assertIn('download_url', data)
    
    def test_offer_attachment_creation(self):
        """Test OfferAttachment creation through serializer"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        data = {
            'offer': self.offer.id,
            'file': SimpleUploadedFile("new.jpg", b"new_content", content_type="image/jpeg"),
            'filename': 'new.jpg',
            'original_filename': 'original_new.jpg',
            'file_type': 'image',
            'mime_type': 'image/jpeg',
            'file_size': 2048,
            'file_hash': 'xyz789abc123',
            'description': 'New attachment',
            'is_primary': False,
            'display_order': 2
        }
        
        serializer = OfferAttachmentSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        attachment = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(attachment.offer, self.offer)
        self.assertEqual(attachment.filename, 'new.jpg')
        self.assertEqual(attachment.file_type, 'image')
        self.assertEqual(attachment.tenant_id, self.tenant_id)
    
    def test_offer_attachment_validation(self):
        """Test OfferAttachment validation"""
        # Test missing required fields
        data = {}
        serializer = OfferAttachmentSerializer(data=data)
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('offer', serializer.errors)
        self.assertIn('filename', serializer.errors)


class TestUserWalletSerializer(BaseSerializerTestCase):
    """Test UserWalletSerializer"""
    
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
    
    def test_user_wallet_serialization(self):
        """Test UserWallet serialization"""
        serializer = UserWalletSerializer(self.wallet)
        data = serializer.data
        
        self.assertEqual(data['id'], self.wallet.id)
        self.assertEqual(data['user'], self.user.id)
        self.assertEqual(data['current_balance'], '1000.50')
        self.assertEqual(data['total_earned'], '1500.00')
        self.assertEqual(data['total_withdrawn'], '400.00')
        self.assertEqual(data['pending_balance'], '50.00')
        self.assertEqual(data['currency'], 'BDT')
        self.assertTrue(data['is_active'])
        self.assertFalse(data['is_frozen'])
        self.assertEqual(data['daily_limit'], '5000.00')
        self.assertEqual(data['monthly_limit'], '100000.00')
        
        # Check custom fields
        self.assertIn('available_balance', data)
        self.assertIn('current_balance_display', data)
        self.assertIn('total_earned_display', data)
        self.assertIn('status_display', data)
        self.assertIn('user_display', data)
    
    def test_user_wallet_creation(self):
        """Test UserWallet creation through serializer"""
        data = {
            'user': self.user.id,
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
        
        serializer = UserWalletSerializer(data=data)
        
        self.assertTrue(serializer.is_valid())
        wallet = serializer.save(tenant_id=self.tenant_id)
        
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.current_balance, Decimal('2000.00'))
        self.assertEqual(wallet.currency, 'USD')
        self.assertEqual(wallet.tenant_id, self.tenant_id)
    
    def test_user_wallet_validation(self):
        """Test UserWallet validation"""
        # Test negative balance
        data = {
            'user': self.user.id,
            'current_balance': '-100.00',
            'total_earned': '0.00',
            'total_withdrawn': '0.00',
            'pending_balance': '0.00',
            'currency': 'BDT'
        }
        
        serializer = UserWalletSerializer(data=data)
        
        # Should be valid as validation is done at model level
        self.assertTrue(serializer.is_valid())
    
    def test_user_wallet_custom_fields(self):
        """Test UserWallet custom serializer fields"""
        serializer = UserWalletSerializer(self.wallet)
        data = serializer.data
        
        # Check available balance calculation
        expected_available = self.wallet.current_balance - self.wallet.pending_balance
        self.assertEqual(data['available_balance'], str(expected_available))
        
        # Check display fields
        self.assertEqual(data['current_balance_display'], 'BDT 1,000.50')
        self.assertEqual(data['total_earned_display'], 'BDT 1,500.00')
        self.assertEqual(data['status_display'], 'Active')
        self.assertEqual(data['user_display'], self.user.username)

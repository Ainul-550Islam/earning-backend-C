"""
api/ad_networks/tests/test_fraud_detection.py
Tests for FraudDetectionService
SaaS-ready with tenant support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from api.ad_networks.models import (
    OfferConversion, UserOfferEngagement, Offer, KnownBadIP,
    AdNetwork
)
from api.ad_networks.services.FraudDetectionService import FraudDetectionService
from api.ad_networks.choices import RiskLevel
from api.ad_networks.constants import FRAUD_SCORE_THRESHOLD, HIGH_RISK_THRESHOLD


class TestFraudDetectionService(TestCase):
    """
    Test cases for FraudDetectionService
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
            status='active',
            tenant_id=self.tenant_id
        )
        
        # Initialize service
        self.fraud_service = FraudDetectionService(tenant_id=self.tenant_id)
    
    def test_analyze_conversion_low_risk(self):
        """Test conversion analysis with low fraud score"""
        conversion_data = {
            'conversion_id': 'test_conv_123',
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'timestamp': timezone.now()
        }
        
        engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status='started',
            ip_address='192.168.1.100',
            started_at=timezone.now() - timedelta(minutes=5),
            created_at=timezone.now() - timedelta(minutes=10),
            tenant_id=self.tenant_id
        )
        
        result = self.fraud_service.analyze_conversion(conversion_data, engagement)
        
        self.assertTrue(result['success'])
        analysis = result['analysis']
        
        self.assertEqual(analysis['conversion_id'], 'test_conv_123')
        self.assertEqual(analysis['user_id'], self.user.id)
        self.assertEqual(analysis['offer_id'], self.offer.id)
        self.assertEqual(analysis['ip_address'], '192.168.1.100')
        self.assertLess(analysis['fraud_score'], FRAUD_SCORE_THRESHOLD)
        self.assertEqual(analysis['risk_level'], RiskLevel.LOW)
        self.assertFalse(analysis['is_fraudulent'])
        self.assertFalse(analysis['should_block'])
        self.assertFalse(analysis['should_review'])
    
    def test_analyze_conversion_high_risk(self):
        """Test conversion analysis with high fraud score"""
        # Create suspicious engagement
        suspicious_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status='started',
            ip_address='192.168.1.200',
            started_at=timezone.now() - timedelta(seconds=5),  # Very fast
            created_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'conversion_id': 'test_conv_456',
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 100.00,  # High amount
            'ip_address': '192.168.1.200',
            'user_agent': 'bot/1.0',  # Bot user agent
            'timestamp': timezone.now()
        }
        
        result = self.fraud_service.analyze_conversion(conversion_data, suspicious_engagement)
        
        self.assertTrue(result['success'])
        analysis = result['analysis']
        
        self.assertGreaterEqual(analysis['fraud_score'], FRAUD_SCORE_THRESHOLD)
        self.assertEqual(analysis['risk_level'], RiskLevel.HIGH)
        self.assertTrue(analysis['is_fraudulent'])
        self.assertFalse(analysis['should_block'])  # Not high enough for block
        self.assertTrue(analysis['should_review'])
        
        # Check indicators
        indicator_types = [ind['type'] for ind in analysis['indicators']]
        self.assertIn('suspiciously_fast_completion', indicator_types)
        self.assertIn('suspicious_user_agent', indicator_types)
    
    def test_analyze_conversion_critical_risk(self):
        """Test conversion analysis with critical fraud score"""
        # Create very suspicious engagement
        critical_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status='started',
            ip_address='10.0.0.1',  # Private IP
            started_at=timezone.now() - timedelta(seconds=2),
            created_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'conversion_id': 'test_conv_789',
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 500.00,  # Very high
            'ip_address': '10.0.0.1',
            'user_agent': 'curl/7.68.0',  # CLI tool
            'timestamp': timezone.now()
        }
        
        result = self.fraud_service.analyze_conversion(conversion_data, critical_engagement)
        
        self.assertTrue(result['success'])
        analysis = result['analysis']
        
        self.assertGreaterEqual(analysis['fraud_score'], HIGH_RISK_THRESHOLD)
        self.assertEqual(analysis['risk_level'], RiskLevel.HIGH)
        self.assertTrue(analysis['is_fraudulent'])
        self.assertTrue(analysis['should_block'])
        
        # Check for critical indicators
        indicator_types = [ind['type'] for ind in analysis['indicators']]
        self.assertIn('suspiciously_fast_completion', indicator_types)
        self.assertIn('suspicious_user_agent', indicator_types)
    
    def test_analyze_velocity_patterns(self):
        """Test velocity pattern analysis"""
        # Create multiple recent conversions for user
        base_time = timezone.now() - timedelta(minutes=30)
        
        for i in range(15):  # 15 conversions in 30 minutes
            UserOfferEngagement.objects.create(
                user=self.user,
                offer=self.offer,
                status='completed',
                ip_address='192.168.1.150',
                created_at=base_time + timedelta(minutes=i*2),
                tenant_id=self.tenant_id
            )
        
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 5.00,
            'ip_address': '192.168.1.150',
            'timestamp': timezone.now()
        }
        
        analysis = {'indicators': []}
        engagement = UserOfferEngagement.objects.filter(user=self.user).first()
        
        self.fraud_service._analyze_velocity_patterns(analysis, conversion_data, engagement)
        
        # Should detect user velocity
        velocity_indicators = [ind for ind in analysis['indicators'] if ind['type'] == 'user_velocity']
        self.assertGreater(len(velocity_indicators), 0)
        self.assertGreater(velocity_indicators[0]['score'], 40)  # Should be high
    
    def test_analyze_ip_patterns(self):
        """Test IP pattern analysis"""
        # Add known bad IP
        KnownBadIP.objects.create(
            ip_address='192.168.1.250',
            threat_type='malware',
            confidence_score=95,
            source='threat_intel',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'ip_address': '192.168.1.250',  # Known bad IP
            'timestamp': timezone.now()
        }
        
        analysis = {'indicators': []}
        
        self.fraud_service._analyze_ip_patterns(analysis, conversion_data, None)
        
        # Should detect known bad IP
        bad_ip_indicators = [ind for ind in analysis['indicators'] if ind['type'] == 'known_bad_ip']
        self.assertEqual(len(bad_ip_indicators), 1)
        self.assertEqual(bad_ip_indicators[0]['score'], 80)
        self.assertEqual(bad_ip_indicators[0]['severity'], 'critical')
    
    def test_analyze_device_patterns(self):
        """Test device pattern analysis"""
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'user_agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'timestamp': timezone.now()
        }
        
        analysis = {'indicators': []}
        
        self.fraud_service._analyze_device_patterns(analysis, conversion_data, None)
        
        # Should detect suspicious user agent
        ua_indicators = [ind for ind in analysis['indicators'] if ind['type'] == 'suspicious_user_agent']
        self.assertGreater(len(ua_indicators), 0)
        self.assertGreater(ua_indicators[0]['score'], 70)
        self.assertIn('Googlebot', ua_indicators[0]['description'])
    
    def test_analyze_time_patterns(self):
        """Test time pattern analysis"""
        # Create very fast completion
        fast_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status='completed',
            started_at=timezone.now() - timedelta(seconds=5),
            created_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'timestamp': timezone.now()
        }
        
        analysis = {'indicators': []}
        
        self.fraud_service._analyze_time_patterns(analysis, conversion_data, fast_engagement)
        
        # Should detect fast completion
        time_indicators = [ind for ind in analysis['indicators'] if ind['type'] == 'suspiciously_fast_completion']
        self.assertGreater(len(time_indicators), 0)
        self.assertGreater(time_indicators[0]['score'], 40)
    
    def test_analyze_user_patterns(self):
        """Test user pattern analysis"""
        # Create new user with high-value conversion
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123',
            date_joined=timezone.now() - timedelta(days=2)
        )
        
        conversion_data = {
            'user_id': new_user.id,
            'offer_id': self.offer.id,
            'payout': 100.00,  # High amount for new user
            'timestamp': timezone.now()
        }
        
        analysis = {'indicators': []}
        
        self.fraud_service._analyze_user_patterns(analysis, conversion_data, None)
        
        # Should detect new user high-value pattern
        user_indicators = [ind for ind in analysis['indicators'] if ind['type'] == 'new_user_high_value']
        self.assertGreater(len(user_indicators), 0)
        self.assertGreater(user_indicators[0]['score'], 35)
    
    def test_calculate_final_score(self):
        """Test final fraud score calculation"""
        indicators = [
            {'type': 'user_velocity', 'score': 25, 'severity': 'high'},
            {'type': 'ip_velocity', 'score': 40, 'severity': 'critical'},
            {'type': 'device_pattern', 'score': 15, 'severity': 'medium'},
            {'type': 'time_pattern', 'score': 10, 'severity': 'low'}
        ]
        
        score = self.fraud_service._calculate_final_score(indicators)
        
        # Should apply severity multipliers
        expected_score = (25 * 1.5) + (40 * 2.0) + (15 * 1.0) + (10 * 0.5)  # 37.5 + 80 + 15 + 5 = 137.5
        self.assertEqual(score, min(100.0, 137.5))
    
    def test_determine_risk_level(self):
        """Test risk level determination"""
        # Test different score ranges
        low_score = self.fraud_service._determine_risk_level(25)
        self.assertEqual(low_score, RiskLevel.LOW)
        
        medium_score = self.fraud_service._determine_risk_level(50)
        self.assertEqual(medium_score, RiskLevel.MEDIUM)
        
        high_score = self.fraud_service._determine_risk_level(75)
        self.assertEqual(high_score, RiskLevel.HIGH)
        
        critical_score = self.fraud_service._determine_risk_level(95)
        self.assertEqual(critical_score, RiskLevel.HIGH)
    
    def test_generate_recommendations(self):
        """Test recommendation generation"""
        analysis = {
            'fraud_score': 80,
            'indicators': [
                {'type': 'user_velocity', 'score': 50, 'severity': 'high'},
                {'type': 'known_bad_ip', 'score': 80, 'severity': 'critical'}
            ]
        }
        
        recommendations = self.fraud_service._generate_recommendations(analysis)
        
        self.assertIn('BLOCK: Immediate action required', recommendations)
        self.assertIn('REVIEW: Manual verification recommended', recommendations)
        self.assertIn('Block IP address immediately', recommendations)
    
    def test_batch_analyze_conversions(self):
        """Test batch conversion analysis"""
        # Create multiple conversions
        conversions = []
        for i in range(5):
            conv = OfferConversion.objects.create(
                engagement=UserOfferEngagement.objects.create(
                    user=self.user,
                    offer=self.offer,
                    status='completed',
                    tenant_id=self.tenant_id
                ),
                payout=Decimal(f'{i+1}.00'),
                fraud_score=float(i * 20),  # Varying fraud scores
                tenant_id=self.tenant_id
            )
            conversions.append(conv.id)
        
        result = self.fraud_service.batch_analyze_conversions(conversions)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_conversions'], 5)
        self.assertEqual(len(result['results']), 5)
        
        # Check fraud detection
        fraudulent_count = sum(1 for r in result['results'] if r['analysis']['is_fraudulent'])
        self.assertGreater(fraudulent_count, 0)
    
    def test_get_fraud_statistics(self):
        """Test fraud statistics calculation"""
        # Create conversions with varying fraud scores
        for i in range(20):
            OfferConversion.objects.create(
                engagement=UserOfferEngagement.objects.create(
                    user=self.user,
                    offer=self.offer,
                    status='completed',
                    created_at=timezone.now() - timedelta(days=i),
                    tenant_id=self.tenant_id
                ),
                payout=Decimal('5.00'),
                fraud_score=float(i * 5),  # 0, 5, 10, 15, ...
                tenant_id=self.tenant_id
            )
        
        result = self.fraud_service.get_fraud_statistics(days=30)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['period_days'], 30)
        self.assertEqual(result['total_conversions'], 20)
        
        # Check statistics
        self.assertGreater(result['avg_fraud_score'], 0)
        self.assertGreaterEqual(result['fraudulent_conversions'], 0)
        self.assertGreaterEqual(result['high_risk_conversions'], 0)
    
    def test_update_fraud_indicators(self):
        """Test updating fraud indicators"""
        conversion = OfferConversion.objects.create(
            engagement=UserOfferEngagement.objects.create(
                user=self.user,
                offer=self.offer,
                status='completed',
                tenant_id=self.tenant_id
            ),
            payout=Decimal('10.00'),
            fraud_score=25.0,
            tenant_id=self.tenant_id
        )
        
        indicators = [
            {'type': 'velocity', 'score': 30, 'description': 'High velocity'},
            {'type': 'ip_pattern', 'score': 20, 'description': 'Suspicious IP'}
        ]
        
        result = self.fraud_service.update_fraud_indicators(conversion, indicators)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['indicators_count'], 2)
        
        # Verify indicators were updated
        conversion.refresh_from_db()
        self.assertEqual(len(conversion.fraud_indicators), 2)
    
    def test_is_vpn_or_proxy(self):
        """Test VPN/proxy detection"""
        # Test private IP
        private_ip_result = self.fraud_service._is_vpn_or_proxy('10.0.0.1')
        self.assertTrue(private_ip_result)
        
        # Test public IP
        public_ip_result = self.fraud_service._is_vpn_or_proxy('8.8.8.8')
        self.assertFalse(public_ip_result)
        
        # Test suspicious patterns
        vpn_result = self.fraud_service._is_vpn_or_proxy('192.168.1.1')
        self.assertFalse(vpn_result)  # Would need actual VPN detection service
    
    def test_generate_device_fingerprint(self):
        """Test device fingerprint generation"""
        device_info = {
            'screen_resolution': '1920x1080',
            'browser': 'Chrome',
            'os': 'Windows',
            'timezone': 'America/New_York'
        }
        
        fingerprint = self.fraud_service._generate_device_fingerprint(device_info)
        
        self.assertEqual(fingerprint['screen'], '1920x1080')
        self.assertEqual(fingerprint['browser'], 'Chrome')
        self.assertEqual(fingerprint['os'], 'Windows')
        self.assertEqual(fingerprint['timezone'], 'America/New_York')
    
    def test_classify_activity_pattern(self):
        """Test activity pattern classification"""
        # Test business hours
        business_hours = {9: 15, 10: 25, 11: 30, 14: 20, 15: 18}
        business_result = self.fraud_service._classify_activity_pattern(business_hours)
        self.assertEqual(business_result, 'business_hours')
        
        # Test evening hours
        evening_hours = {19: 25, 20: 30, 21: 35, 22: 40}
        evening_result = self.fraud_service._classify_activity_pattern(evening_hours)
        self.assertEqual(evening_result, 'evening')
        
        # Test night owl
        night_hours = {0: 10, 1: 15, 2: 20, 3: 25}
        night_result = self.fraud_service._classify_activity_pattern(night_hours)
        self.assertEqual(night_result, 'night_owl')
        
        # Test mixed pattern
        mixed_hours = {6: 10, 12: 20, 18: 30, 23: 15}
        mixed_result = self.fraud_service._classify_activity_pattern(mixed_hours)
        self.assertEqual(mixed_result, 'mixed')


class TestFraudDetectionIntegration(TestCase):
    """
    Integration tests for FraudDetectionService
    """
    
    def setUp(self):
        """Set up integration test data"""
        self.tenant_id = 'integration_test_tenant'
        
        self.user = User.objects.create_user(
            username='frauduser',
            email='fraud@example.com',
            password='fraudpass123'
        )
        
        self.network = AdNetwork.objects.create(
            name='Fraud Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.offer = Offer.objects.create(
            ad_network=self.network,
            external_id='fraud_offer',
            title='Fraud Test Offer',
            reward_amount=Decimal('50.00'),
            status='active',
            tenant_id=self.tenant_id
        )
        
        self.fraud_service = FraudDetectionService(tenant_id=self.tenant_id)
    
    def test_complex_fraud_scenario(self):
        """Test complex fraud detection scenario"""
        # Add known bad IP
        KnownBadIP.objects.create(
            ip_address='203.0.113.1',  # Known malicious IP
            threat_type='botnet',
            confidence_score=98,
            source='threat_intel',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        # Create multiple suspicious conversions from same IP
        conversions = []
        for i in range(10):
            engagement = UserOfferEngagement.objects.create(
                user=self.user,
                offer=self.offer,
                status='completed',
                ip_address='203.0.113.1',
                created_at=timezone.now() - timedelta(minutes=i),
                started_at=timezone.now() - timedelta(seconds=5),
                tenant_id=self.tenant_id
            )
            
            conversion = OfferConversion.objects.create(
                engagement=engagement,
                payout=Decimal(f'{i+1}.00'),
                fraud_score=0.0,  # Initially 0
                tenant_id=self.tenant_id
            )
            conversions.append(conversion.id)
        
        # Analyze all conversions
        result = self.fraud_service.batch_analyze_conversions(conversions)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_conversions'], 10)
        
        # Should detect multiple fraud indicators
        total_indicators = 0
        for analysis in result['results']:
            total_indicators += len(analysis['analysis']['indicators'])
        
        self.assertGreater(total_indicators, 0)
        
        # Check for known bad IP detection
        known_bad_ip_count = 0
        for analysis in result['results']:
            for indicator in analysis['analysis']['indicators']:
                if indicator['type'] == 'known_bad_ip':
                    known_bad_ip_count += 1
        
        self.assertGreater(known_bad_ip_count, 0)
    
    def test_fraud_model_update(self):
        """Test fraud model update"""
        training_data = [
            {
                'conversion_id': 'train_1',
                'features': {'velocity_score': 0.8, 'ip_score': 0.2, 'device_score': 0.1},
                'is_fraud': False,
                'label': 0
            },
            {
                'conversion_id': 'train_2',
                'features': {'velocity_score': 0.9, 'ip_score': 0.8, 'device_score': 0.7},
                'is_fraud': True,
                'label': 1
            }
        ]
        
        result = self.fraud_service.update_fraud_models(training_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['models_updated'], True)
        self.assertEqual(result['training_samples'], 2)


if __name__ == '__main__':
    pytest.main([__file__])

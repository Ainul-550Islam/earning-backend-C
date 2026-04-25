"""
api/ad_networks/tests/test_conversion_service.py
Tests for ConversionService
SaaS-ready with tenant support
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User

from api.ad_networks.models import (
    OfferConversion, UserOfferEngagement, Offer, OfferReward,
    UserWallet, AdNetwork
)
from api.ad_networks.services.ConversionService import ConversionService
from api.ad_networks.choices import (
    ConversionStatus, EngagementStatus, RewardStatus, RiskLevel
)
from api.ad_networks.constants import FRAUD_SCORE_THRESHOLD


class TestConversionService(TestCase):
    """
    Test cases for ConversionService
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
        
        # Create test engagement
        self.engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.1',
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
        
        # Initialize service
        self.conversion_service = ConversionService(tenant_id=self.tenant_id)
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()
    
    def test_process_conversion_success_low_fraud(self):
        """Test successful conversion processing with low fraud score"""
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'ip_address': '192.168.1.1',
            'timestamp': timezone.now()
        }
        
        result = self.conversion_service.process_conversion(conversion_data, self.engagement)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], ConversionStatus.APPROVED)
        self.assertTrue(result['auto_approved'])
        self.assertEqual(result['fraud_score'], 0.0)
        self.assertEqual(result['conversion_id'], self.engagement.conversion.id)
    
    def test_process_conversion_high_fraud(self):
        """Test conversion processing with high fraud score"""
        # Create engagement with suspicious data
        suspicious_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.1',
            started_at=timezone.now() - timedelta(seconds=5),  # Very fast
            created_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 100.00,  # High amount
            'ip_address': '192.168.1.1',
            'timestamp': timezone.now()
        }
        
        result = self.conversion_service.process_conversion(conversion_data, suspicious_engagement)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], ConversionStatus.REJECTED)
        self.assertFalse(result['auto_approved'])
        self.assertGreaterEqual(result['fraud_score'], FRAUD_SCORE_THRESHOLD)
        self.assertTrue(result['should_review'])
    
    def test_process_conversion_missing_fields(self):
        """Test conversion processing with missing required fields"""
        conversion_data = {
            'user_id': self.user.id,
            # Missing offer_id, payout
        }
        
        result = self.conversion_service.process_conversion(conversion_data)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'validation_failed')
        self.assertIn('Missing required field', result['error'])
    
    def test_process_conversion_duplicate(self):
        """Test processing duplicate conversion"""
        # Create existing conversion
        OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('5.00'),
            conversion_status=ConversionStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 10.00,
            'ip_address': '192.168.1.1',
            'timestamp': timezone.now()
        }
        
        result = self.conversion_service.process_conversion(conversion_data, self.engagement)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'duplicate_conversion')
        self.assertIn('already exists', result['error'])
    
    def test_verify_conversion_approval(self):
        """Test manual conversion verification with approval"""
        # Create pending conversion
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('15.00'),
            conversion_status=ConversionStatus.PENDING,
            fraud_score=25.0,  # Medium risk
            tenant_id=self.tenant_id
        )
        
        result = self.conversion_service.verify_conversion(
            conversion.id,
            verifier_user=self.user,
            approved=True,
            notes='Manual verification passed'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'approved')
        
        # Verify conversion status changed
        conversion.refresh_from_db()
        self.assertEqual(conversion.conversion_status, ConversionStatus.APPROVED)
        self.assertIsNotNone(conversion.approved_at)
        self.assertEqual(conversion.verification_notes, 'Approved: Manual verification passed')
        
        # Verify reward was created
        reward = OfferReward.objects.filter(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement
        ).first()
        self.assertIsNotNone(reward)
        self.assertEqual(reward.amount, Decimal('15.00'))
        self.assertEqual(reward.status, RewardStatus.APPROVED)
    
    def test_verify_conversion_rejection(self):
        """Test manual conversion verification with rejection"""
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('20.00'),
            conversion_status=ConversionStatus.PENDING,
            fraud_score=80.0,  # High fraud score
            tenant_id=self.tenant_id
        )
        
        result = self.conversion_service.verify_conversion(
            conversion.id,
            verifier_user=self.user,
            approved=False,
            notes='Manual verification failed - suspicious activity'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'rejected')
        
        # Verify conversion status changed
        conversion.refresh_from_db()
        self.assertEqual(conversion.conversion_status, ConversionStatus.REJECTED)
        self.assertEqual(conversion.rejection_reason, 'Manual verification failed - suspicious activity')
    
    def test_reverse_conversion_success(self):
        """Test successful conversion reversal"""
        # Create approved conversion with reward
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('25.00'),
            conversion_status=ConversionStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement,
            amount=Decimal('25.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        initial_wallet_balance = self.wallet.balance
        
        result = self.conversion_service.reverse_conversion(
            conversion.id,
            reason='User requested refund'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['reversed_amount'], Decimal('25.00'))
        self.assertEqual(result['reason'], 'User requested refund')
        
        # Verify conversion status
        conversion.refresh_from_db()
        self.assertEqual(conversion.conversion_status, ConversionStatus.CHARGEBACK)
        self.assertIsNotNone(conversion.chargeback_at)
        
        # Verify reward was reversed
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardStatus.CANCELLED)
        
        # Verify wallet balance
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.balance,
            initial_wallet_balance - Decimal('25.00')
        )
    
    def test_get_user_conversions(self):
        """Test getting user conversions"""
        # Create multiple conversions
        for i in range(5):
            OfferConversion.objects.create(
                engagement=UserOfferEngagement.objects.create(
                    user=self.user,
                    offer=self.offer,
                    status=EngagementStatus.COMPLETED,
                    tenant_id=self.tenant_id
                ),
                payout=Decimal(f'{i+1}.00'),
                conversion_status=ConversionStatus.APPROVED,
                tenant_id=self.tenant_id
            )
        
        result = self.conversion_service.get_user_conversions(self.user.id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_count'], 5)
        self.assertEqual(len(result['conversions']), 5)
        
        # Verify conversion data structure
        first_conversion = result['conversions'][0]
        self.assertIn('id', first_conversion)
        self.assertIn('offer_title', first_conversion)
        self.assertIn('payout', first_conversion)
        self.assertIn('status', first_conversion)
    
    def test_get_user_conversions_with_filters(self):
        """Test getting user conversions with filters"""
        # Create conversions with different statuses
        OfferConversion.objects.create(
            engagement=UserOfferEngagement.objects.create(
                user=self.user,
                offer=self.offer,
                status=EngagementStatus.COMPLETED,
                tenant_id=self.tenant_id
            ),
            payout=Decimal('10.00'),
            conversion_status=ConversionStatus.PENDING,
            tenant_id=self.tenant_id
        )
        
        # Test filtering by status
        result = self.conversion_service.get_user_conversions(
            self.user.id,
            status='pending'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_count'], 1)
        self.assertEqual(result['conversions'][0]['status'], 'pending')
        
        # Test pagination
        result_paginated = self.conversion_service.get_user_conversions(
            self.user.id,
            limit=2,
            offset=0
        )
        
        self.assertTrue(result_paginated['success'])
        self.assertEqual(len(result_paginated['conversions']), 2)
        self.assertTrue(result_paginated['has_more'])
    
    def test_get_conversion_stats(self):
        """Test getting conversion statistics"""
        # Create conversions over different time periods
        base_time = timezone.now() - timedelta(days=15)
        
        for i in range(10):
            OfferConversion.objects.create(
                engagement=UserOfferEngagement.objects.create(
                    user=self.user,
                    offer=self.offer,
                    status=EngagementStatus.COMPLETED,
                    created_at=base_time + timedelta(days=i),
                    tenant_id=self.tenant_id
                ),
                payout=Decimal(f'{i+1}.00'),
                conversion_status=ConversionStatus.APPROVED if i % 2 == 0 else ConversionStatus.REJECTED,
                fraud_score=float(i * 10),  # Varying fraud scores
                tenant_id=self.tenant_id
            )
        
        result = self.conversion_service.get_conversion_stats(self.user.id, days=30)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['period_days'], 30)
        self.assertEqual(result['total_conversions'], 10)
        self.assertEqual(result['approved_conversions'], 5)
        self.assertEqual(result['rejected_conversions'], 5)
        self.assertGreater(result['avg_fraud_score'], 0)
        self.assertGreater(result['approval_rate'], 0)
        self.assertGreater(result['fraud_rate'], 0)
    
    def test_calculate_fraud_score(self):
        """Test fraud score calculation"""
        # Test with normal engagement
        normal_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.100',
            created_at=timezone.now() - timedelta(minutes=30),
            started_at=timezone.now() - timedelta(minutes=5),
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'payout': 5.00,
            'ip_address': '192.168.1.100'
        }
        
        score = self.conversion_service._calculate_fraud_score(
            normal_engagement, conversion_data
        )
        
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_calculate_fraud_score_suspicious(self):
        """Test fraud score calculation with suspicious data"""
        # Create suspicious engagement
        suspicious_engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.200',
            created_at=timezone.now() - timedelta(minutes=1),
            started_at=timezone.now() - timedelta(seconds=10),  # Very fast
            tenant_id=self.tenant_id
        )
        
        conversion_data = {
            'payout': 100.00,  # High amount
            'ip_address': '192.168.1.200'
        }
        
        score = self.conversion_service._calculate_fraud_score(
            suspicious_engagement, conversion_data
        )
        
        self.assertGreater(score, 50)  # Should be high due to fast completion and high amount
    
    def test_create_reward(self):
        """Test reward creation"""
        conversion = OfferConversion.objects.create(
            engagement=self.engagement,
            payout=Decimal('30.00'),
            conversion_status=ConversionStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        initial_wallet_balance = self.wallet.balance
        
        self.conversion_service._create_reward(self.engagement, conversion)
        
        # Verify reward was created
        reward = OfferReward.objects.filter(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement
        ).first()
        self.assertIsNotNone(reward)
        self.assertEqual(reward.amount, Decimal('30.00'))
        self.assertEqual(reward.status, RewardStatus.APPROVED)
        
        # Verify wallet was updated
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.balance,
            initial_wallet_balance + Decimal('30.00')
        )
    
    def test_reverse_reward(self):
        """Test reward reversal"""
        # Create approved reward
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement,
            amount=Decimal('50.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        initial_wallet_balance = self.wallet.balance
        
        self.conversion_service._reverse_reward(reward)
        
        # Verify reward status
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardStatus.CANCELLED)
        
        # Verify wallet was updated
        self.wallet.refresh_from_db()
        self.assertEqual(
            self.wallet.balance,
            initial_wallet_balance - Decimal('50.00')
        )
    
    def test_update_offer_stats(self):
        """Test offer statistics update"""
        # Create multiple engagements for the offer
        for i in range(5):
            UserOfferEngagement.objects.create(
                user=self.user,
                offer=self.offer,
                status=EngagementStatus.COMPLETED if i % 2 == 0 else EngagementStatus.STARTED,
                tenant_id=self.tenant_id
            )
        
        initial_click_count = self.offer.click_count
        initial_conversions = self.offer.total_conversions
        
        self.conversion_service._update_offer_stats(self.offer)
        
        # Verify stats were updated
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.click_count, initial_click_count + 5)
        self.assertEqual(self.offer.total_conversions, initial_conversions + 3)  # 3 completed
        
        # Verify conversion rate
        expected_rate = (self.offer.total_conversions / self.offer.click_count * 100) if self.offer.click_count > 0 else 0
        self.assertEqual(self.offer.conversion_rate, expected_rate)
    
    def test_clear_user_caches(self):
        """Test user cache clearing"""
        # Set some cache values
        cache.set(f'user_{self.user.id}_stats', 'test_value')
        cache.set(f'user_{self.user.id}_rewards', 'test_value')
        cache.set(f'user_{self.user.id}_engagements', 'test_value')
        
        self.conversion_service._clear_user_caches(self.user)
        
        # Verify caches were cleared
        self.assertIsNone(cache.get(f'user_{self.user.id}_stats'))
        self.assertIsNone(cache.get(f'user_{self.user.id}_rewards'))
        self.assertIsNone(cache.get(f'user_{self.user.id}_engagements'))
    
    def test_send_reward_notification(self):
        """Test reward notification sending"""
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('10.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        # This would test the actual notification sending
        # For now, we'll just verify the method doesn't raise exceptions
        try:
            self.conversion_service._send_reward_notification(self.user, reward)
        except Exception as e:
            self.fail(f"Reward notification failed: {e}")
    
    def test_send_reversal_notification(self):
        """Test reward reversal notification sending"""
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('15.00'),
            status=RewardStatus.CANCELLED,
            cancellation_reason='Test reversal',
            tenant_id=self.tenant_id
        )
        
        # This would test the actual notification sending
        # For now, we'll just verify the method doesn't raise exceptions
        try:
            self.conversion_service._send_reversal_notification(self.user, reward, 'Test reversal')
        except Exception as e:
            self.fail(f"Reversal notification failed: {e}")


class TestConversionServiceIntegration(TestCase):
    """
    Integration tests for ConversionService
    """
    
    def setUp(self):
        """Set up integration test data"""
        self.tenant_id = 'integration_test_tenant'
        
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='integrationpass123'
        )
        
        self.network = AdNetwork.objects.create(
            name='Integration Test Network',
            network_type='adscend',
            is_active=True,
            tenant_id=self.tenant_id
        )
        
        self.offer = Offer.objects.create(
            ad_network=self.network,
            external_id='integration_offer',
            title='Integration Test Offer',
            reward_amount=Decimal('25.00'),
            status='active',
            tenant_id=self.tenant_id
        )
        
        self.conversion_service = ConversionService(tenant_id=self.tenant_id)
    
    def test_full_conversion_workflow(self):
        """Test complete conversion workflow"""
        # Start engagement
        engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.50',
            tenant_id=self.tenant_id
        )
        
        # Process conversion
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 25.00,
            'ip_address': '192.168.1.50',
            'timestamp': timezone.now()
        }
        
        conversion_result = self.conversion_service.process_conversion(
            conversion_data, engagement
        )
        
        self.assertTrue(conversion_result['success'])
        self.assertEqual(conversion_result['status'], ConversionStatus.APPROVED)
        self.assertTrue(conversion_result['auto_approved'])
        
        # Verify all components were created
        conversion = OfferConversion.objects.get(
            engagement=engagement
        )
        self.assertEqual(conversion.payout, Decimal('25.00'))
        
        reward = OfferReward.objects.get(
            user=self.user,
            offer=self.offer,
            engagement=engagement
        )
        self.assertEqual(reward.amount, Decimal('25.00'))
        self.assertEqual(reward.status, RewardStatus.APPROVED)
        
        # Verify engagement was updated
        engagement.refresh_from_db()
        self.assertEqual(engagement.status, EngagementStatus.COMPLETED)
    
    def test_high_risk_conversion_workflow(self):
        """Test high-risk conversion workflow"""
        # Start suspicious engagement
        engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.STARTED,
            ip_address='192.168.1.100',
            started_at=timezone.now() - timedelta(seconds=5),
            created_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        # Process conversion with high fraud score
        conversion_data = {
            'user_id': self.user.id,
            'offer_id': self.offer.id,
            'payout': 200.00,  # Very high amount
            'ip_address': '192.168.1.100',
            'timestamp': timezone.now()
        }
        
        conversion_result = self.conversion_service.process_conversion(
            conversion_data, engagement
        )
        
        self.assertTrue(conversion_result['success'])
        self.assertEqual(conversion_result['status'], ConversionStatus.REJECTED)
        self.assertGreaterEqual(conversion_result['fraud_score'], FRAUD_SCORE_THRESHOLD)
        self.assertTrue(conversion_result['should_review'])
        
        # Verify conversion was rejected
        conversion = OfferConversion.objects.get(
            engagement=engagement
        )
        self.assertEqual(conversion.conversion_status, ConversionStatus.REJECTED)
        self.assertGreaterEqual(conversion.fraud_score, FRAUD_SCORE_THRESHOLD)
        
        # Verify no reward was created
        reward_exists = OfferReward.objects.filter(
            user=self.user,
            offer=self.offer,
            engagement=engagement
        ).exists()
        self.assertFalse(reward_exists)


if __name__ == '__main__':
    pytest.main([__file__])

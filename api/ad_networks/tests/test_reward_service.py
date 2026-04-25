"""
api/ad_networks/tests/test_reward_service.py
Tests for RewardService
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
    OfferReward, UserOfferEngagement, Offer, UserWallet,
    OfferDailyLimit, AdNetwork
)
from api.ad_networks.services.RewardService import RewardService
from api.ad_networks.choices import RewardStatus, EngagementStatus
from api.ad_networks.constants import MAX_DAILY_OFFER_LIMIT


class TestRewardService(TestCase):
    """
    Test cases for RewardService
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
            status=EngagementStatus.COMPLETED,
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
        self.reward_service = RewardService(tenant_id=self.tenant_id)
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()
    
    def test_calculate_reward_basic(self):
        """Test basic reward calculation"""
        result = self.reward_service.calculate_reward(self.engagement)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['base_reward'], Decimal('10.00'))
        self.assertGreater(result['multiplier'], 0)
        self.assertGreaterEqual(result['bonus_amount'], 0)
        self.assertGreaterEqual(result['gross_reward'], result['base_reward'])
        self.assertLessEqual(result['net_reward'], result['gross_reward'])
        self.assertEqual(result['currency'], 'USD')
    
    def test_calculate_reward_with_bonus(self):
        """Test reward calculation with bonus"""
        # Make offer new and hot
        self.offer.is_new = True
        self.offer.is_hot = True
        self.offer.save()
        
        result = self.reward_service.calculate_reward(self.engagement)
        
        self.assertTrue(result['success'])
        self.assertGreater(result['bonus_amount'], 0)
        self.assertGreater(result['gross_reward'], result['base_reward'])
        
        # Check bonus breakdown
        taxes_applied = result['taxes_applied']
        self.assertIn('gross_amount', taxes_applied)
        self.assertIn('net_amount', taxes_applied)
        self.assertIn('total_fees', taxes_applied)
    
    def test_calculate_reward_daily_limit_exceeded(self):
        """Test reward calculation when daily limit exceeded"""
        # Create daily limit record
        OfferDailyLimit.objects.create(
            user=self.user,
            offer=self.offer,
            count_today=MAX_DAILY_OFFER_LIMIT,
            daily_limit=MAX_DAILY_OFFER_LIMIT,
            last_reset_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        result = self.reward_service.calculate_reward(self.engagement)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'daily_limit_exceeded')
        self.assertIn('Daily limit exceeded', result['error'])
    
    def test_calculate_reward_wallet_limit_exceeded(self):
        """Test reward calculation when wallet limit exceeded"""
        # Set wallet to maximum balance
        self.wallet.balance = Decimal('10000.00')  # Max balance
        self.wallet.save()
        
        result = self.reward_service.calculate_reward(self.engagement)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'wallet_limit_exceeded')
        self.assertIn('Maximum wallet balance', result['error'])
    
    def test_credit_reward_success(self):
        """Test successful reward crediting"""
        initial_balance = self.wallet.balance
        initial_earned = self.wallet.total_earned
        
        result = self.reward_service.credit_reward(
            self.engagement,
            Decimal('15.00'),
            'USD',
            'Test reward'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['reward_id'], OfferReward.objects.first().id)
        self.assertEqual(result['amount'], Decimal('15.00'))
        self.assertEqual(result['currency'], 'USD')
        
        # Verify wallet was updated
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, initial_balance + Decimal('15.00'))
        self.assertEqual(self.wallet.total_earned, initial_earned + Decimal('15.00'))
        
        # Verify reward was created
        reward = OfferReward.objects.first()
        self.assertEqual(reward.user, self.user)
        self.assertEqual(reward.offer, self.offer)
        self.assertEqual(reward.engagement, self.engagement)
        self.assertEqual(reward.amount, Decimal('15.00'))
        self.assertEqual(reward.status, RewardStatus.APPROVED)
    
    def test_credit_reward_insufficient_balance(self):
        """Test reward crediting with insufficient wallet balance"""
        # Set wallet to negative balance scenario
        self.wallet.balance = Decimal('-5.00')
        self.wallet.save()
        
        result = self.reward_service.credit_reward(
            self.engagement,
            Decimal('10.00'),
            'USD',
            'Test reward'
        )
        
        # Should still succeed (allow negative for chargebacks)
        self.assertTrue(result['success'])
        
        # Verify wallet went more negative
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('-15.00'))
    
    def test_reverse_reward_success(self):
        """Test successful reward reversal"""
        # Create approved reward
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement,
            amount=Decimal('20.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        initial_balance = self.wallet.balance
        
        result = self.reward_service.reverse_reward(
            reward.id,
            'User requested refund'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['reward_id'], reward.id)
        self.assertEqual(result['reversed_amount'], Decimal('20.00'))
        self.assertEqual(result['reason'], 'User requested refund')
        
        # Verify reward status
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardStatus.CANCELLED)
        self.assertIsNotNone(reward.cancelled_at)
        self.assertEqual(reward.cancellation_reason, 'User requested refund')
        
        # Verify wallet was updated
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, initial_balance - Decimal('20.00'))
    
    def test_reverse_reward_already_cancelled(self):
        """Test reward reversal when already cancelled"""
        # Create cancelled reward
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            engagement=self.engagement,
            amount=Decimal('25.00'),
            status=RewardStatus.CANCELLED,
            tenant_id=self.tenant_id
        )
        
        result = self.reward_service.reverse_reward(reward.id)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['code'], 'already_cancelled')
        self.assertIn('already cancelled', result['error'])
    
    def test_get_user_rewards(self):
        """Test getting user rewards"""
        # Create multiple rewards
        for i in range(5):
            OfferReward.objects.create(
                user=self.user,
                offer=self.offer,
                amount=Decimal(f'{i+1}.00'),
                status=RewardStatus.APPROVED,
                tenant_id=self.tenant_id
            )
        
        result = self.reward_service.get_user_rewards(self.user.id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_count'], 5)
        self.assertEqual(len(result['rewards']), 5)
        
        # Verify reward data structure
        first_reward = result['rewards'][0]
        self.assertIn('id', first_reward)
        self.assertIn('amount', first_reward)
        self.assertIn('currency', first_reward)
        self.assertIn('status', first_reward)
        self.assertIn('created_at', first_reward)
    
    def test_get_user_rewards_with_filters(self):
        """Test getting user rewards with filters"""
        # Create rewards with different statuses
        OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('10.00'),
            status=RewardStatus.PENDING,
            tenant_id=self.tenant_id
        )
        
        OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('20.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        # Test status filter
        result = self.reward_service.get_user_rewards(
            self.user.id,
            status='approved'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_count'], 1)
        self.assertEqual(result['rewards'][0]['status'], 'approved')
        
        # Test pagination
        result_paginated = self.reward_service.get_user_rewards(
            self.user.id,
            limit=1,
            offset=0
        )
        
        self.assertTrue(result_paginated['success'])
        self.assertEqual(len(result_paginated['rewards']), 1)
        self.assertTrue(result_paginated['has_more'])
    
    def test_get_user_wallet(self):
        """Test getting user wallet"""
        result = self.reward_service.get_user_wallet(self.user.id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['wallet']['balance'], Decimal('100.00'))
        self.assertEqual(result['wallet']['total_earned'], Decimal('500.00'))
        self.assertEqual(result['wallet']['currency'], 'USD')
        self.assertIn('last_activity', result['wallet'])
        self.assertIn('created_at', result['wallet'])
    
    def test_get_user_wallet_nonexistent(self):
        """Test getting wallet for non-existent user"""
        result = self.reward_service.get_user_wallet(99999)
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])
    
    def test_get_reward_stats(self):
        """Test getting reward statistics"""
        # Create rewards over different time periods
        base_time = timezone.now() - timedelta(days=15)
        
        for i in range(10):
            OfferReward.objects.create(
                user=self.user,
                offer=self.offer,
                amount=Decimal(f'{i+1}.00'),
                status=RewardStatus.APPROVED if i % 2 == 0 else RewardStatus.PENDING,
                created_at=base_time + timedelta(days=i),
                tenant_id=self.tenant_id
            )
        
        result = self.reward_service.get_reward_stats(self.user.id, days=30)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['period_days'], 30)
        self.assertEqual(result['total_rewards'], 10)
        self.assertEqual(result['approved_rewards'], 5)
        self.assertEqual(result['pending_rewards'], 5)
        self.assertGreater(result['total_amount'], 0)
        self.assertGreater(result['approved_amount'], 0)
        self.assertGreater(result['avg_reward'], 0)
        self.assertGreater(result['approval_rate'], 0)
    
    def test_calculate_reward_multiplier(self):
        """Test reward multiplier calculation"""
        # Test with user profile
        with patch.object(self.user, 'profile') as mock_profile:
            mock_profile.level = 'gold'
            mock_profile.configure_mock(**{'level': 'gold'})
            
            multiplier = self.reward_service._calculate_reward_multiplier(self.user, self.offer)
            
            self.assertGreater(multiplier, Decimal('1.0'))
            self.assertLessEqual(multiplier, Decimal('2.0'))
    
    def test_calculate_bonus_amount(self):
        """Test bonus amount calculation"""
        # Test first-time user bonus
        with patch.object(self.user, 'profile') as mock_profile:
            mock_profile.referred_by = Mock()
            
            bonus = self.reward_service._calculate_bonus_amount(
                self.user, self.offer, Decimal('10.00')
            )
            
            self.assertGreater(bonus, 0)
            # Should include first-time bonus and referral bonus
    
    def test_apply_taxes_and_fees(self):
        """Test taxes and fees application"""
        gross_amount = Decimal('10.00')
        
        net_amount = self.reward_service._apply_taxes_and_fees(gross_amount, self.offer)
        
        self.assertLess(net_amount, gross_amount)
        self.assertGreaterEqual(net_amount, Decimal('0.0'))
    
    def test_check_daily_limit(self):
        """Test daily limit checking"""
        # Test no limit reached
        result = self.reward_service._check_daily_limit(self.user, self.offer)
        
        self.assertTrue(result['allowed'])
        self.assertIsNone(result['reason'])
        self.assertGreater(result['remaining'], 0)
        
        # Test limit reached
        OfferDailyLimit.objects.create(
            user=self.user,
            offer=self.offer,
            count_today=MAX_DAILY_OFFER_LIMIT,
            daily_limit=MAX_DAILY_OFFER_LIMIT,
            last_reset_at=timezone.now(),
            tenant_id=self.tenant_id
        )
        
        result = self.reward_service._check_daily_limit(self.user, self.offer)
        
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'Daily limit exceeded')
        self.assertEqual(result['remaining'], 0)
    
    def test_check_user_wallet(self):
        """Test user wallet checking"""
        # Test normal balance
        result = self.reward_service._check_user_wallet(self.user, Decimal('10.00'))
        
        self.assertTrue(result['allowed'])
        self.assertIsNone(result['reason'])
        
        # Test exceeding max balance
        self.wallet.balance = Decimal('9999.00')
        self.wallet.save()
        
        result = self.reward_service._check_user_wallet(self.user, Decimal('100.00'))
        
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'Maximum wallet balance exceeded')
    
    def test_get_or_create_wallet(self):
        """Test getting or creating wallet"""
        # Delete existing wallet
        self.wallet.delete()
        
        # Should create new wallet
        wallet = self.reward_service._get_or_create_wallet(self.user)
        
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('0.00'))
        self.assertEqual(wallet.total_earned, Decimal('0.00'))
        self.assertEqual(wallet.currency, 'USD')
    
    def test_clear_user_caches(self):
        """Test user cache clearing"""
        # Set some cache values
        cache.set(f'user_{self.user.id}_wallet', 'test_value')
        cache.set(f'user_{self.user.id}_rewards', 'test_value')
        cache.set(f'user_{self.user.id}_stats', 'test_value')
        
        self.reward_service._clear_user_caches(self.user)
        
        # Verify caches were cleared
        self.assertIsNone(cache.get(f'user_{self.user.id}_wallet'))
        self.assertIsNone(cache.get(f'user_{self.user.id}_rewards'))
        self.assertIsNone(cache.get(f'user_{self.user.id}_stats'))
    
    def test_send_reward_notification(self):
        """Test reward notification sending"""
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('30.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        # This would test actual notification sending
        # For now, we'll just verify to method doesn't raise exceptions
        try:
            self.reward_service._send_reward_notification(self.user, reward)
        except Exception as e:
            self.fail(f"Reward notification failed: {e}")
    
    def test_send_reversal_notification(self):
        """Test reward reversal notification sending"""
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            amount=Decimal('40.00'),
            status=RewardStatus.CANCELLED,
            cancellation_reason='Test reversal',
            tenant_id=self.tenant_id
        )
        
        # This would test actual notification sending
        # For now, we'll just verify to method doesn't raise exceptions
        try:
            self.reward_service._send_reversal_notification(self.user, reward, 'Test reversal')
        except Exception as e:
            self.fail(f"Reversal notification failed: {e}")
    
    def test_process_pending_rewards(self):
        """Test processing pending rewards"""
        # Create pending rewards
        for i in range(5):
            OfferReward.objects.create(
                user=self.user,
                offer=self.offer,
                amount=Decimal(f'{i+1}.00'),
                status=RewardStatus.PENDING,
                tenant_id=self.tenant_id
            )
        
        initial_balance = self.wallet.balance
        
        result = self.reward_service.process_pending_rewards()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['processed_count'], 5)
        
        # Verify wallet was updated
        self.wallet.refresh_from_db()
        expected_increase = Decimal('15.00')  # 1+2+3+4+5
        self.assertEqual(self.wallet.balance, initial_balance + expected_increase)
        
        # Verify rewards were approved
        pending_rewards = OfferReward.objects.filter(status=RewardStatus.PENDING)
        self.assertEqual(pending_rewards.count(), 0)
        
        approved_rewards = OfferReward.objects.filter(status=RewardStatus.APPROVED)
        self.assertEqual(approved_rewards.count(), 5)


class TestRewardServiceIntegration(TestCase):
    """
    Integration tests for RewardService
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
            reward_amount=Decimal('50.00'),
            status='active',
            tenant_id=self.tenant_id
        )
        
        self.reward_service = RewardService(tenant_id=self.tenant_id)
    
    def test_full_reward_workflow(self):
        """Test complete reward workflow"""
        # Create engagement
        engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.COMPLETED,
            tenant_id=self.tenant_id
        )
        
        # Calculate reward
        calc_result = self.reward_service.calculate_reward(engagement)
        
        self.assertTrue(calc_result['success'])
        net_reward = calc_result['net_reward']
        
        # Credit reward
        credit_result = self.reward_service.credit_reward(
            engagement,
            net_reward,
            'USD',
            'Integration test reward'
        )
        
        self.assertTrue(credit_result['success'])
        
        # Verify reward was created
        reward = OfferReward.objects.get(
            user=self.user,
            offer=self.offer,
            engagement=engagement
        )
        self.assertEqual(reward.amount, net_reward)
        self.assertEqual(reward.status, RewardStatus.APPROVED)
        
        # Verify wallet was updated
        wallet = reward_service._get_or_create_wallet(self.user)
        self.assertEqual(wallet.balance, net_reward)
    
    def test_reward_reversal_workflow(self):
        """Test reward reversal workflow"""
        # Create engagement and reward
        engagement = UserOfferEngagement.objects.create(
            user=self.user,
            offer=self.offer,
            status=EngagementStatus.COMPLETED,
            tenant_id=self.tenant_id
        )
        
        reward = OfferReward.objects.create(
            user=self.user,
            offer=self.offer,
            engagement=engagement,
            amount=Decimal('75.00'),
            status=RewardStatus.APPROVED,
            tenant_id=self.tenant_id
        )
        
        # Get initial wallet
        wallet = self.reward_service._get_or_create_wallet(self.user)
        initial_balance = wallet.balance
        
        # Reverse reward
        reverse_result = self.reward_service.reverse_reward(
            reward.id,
            'Integration test reversal'
        )
        
        self.assertTrue(reverse_result['success'])
        
        # Verify reward status
        reward.refresh_from_db()
        self.assertEqual(reward.status, RewardStatus.CANCELLED)
        
        # Verify wallet was updated
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, initial_balance - Decimal('75.00'))
    
    def test_multiple_user_rewards(self):
        """Test multiple users with rewards"""
        # Create second user
        user2 = User.objects.create_user(
            username='integrationuser2',
            email='integration2@example.com',
            password='integrationpass456'
        )
        
        # Create rewards for both users
        for user in [self.user, user2]:
            engagement = UserOfferEngagement.objects.create(
                user=user,
                offer=self.offer,
                status=EngagementStatus.COMPLETED,
                tenant_id=self.tenant_id
            )
            
            self.reward_service.credit_reward(
                engagement,
                Decimal('25.00'),
                'USD',
                'Multi-user test'
            )
        
        # Get rewards for both users
        user1_rewards = self.reward_service.get_user_rewards(self.user.id)
        user2_rewards = self.reward_service.get_user_rewards(user2.id)
        
        self.assertTrue(user1_rewards['success'])
        self.assertTrue(user2_rewards['success'])
        self.assertEqual(user1_rewards['total_count'], 1)
        self.assertEqual(user2_rewards['total_count'], 1)
        
        # Verify wallet balances
        wallet1 = self.reward_service.get_user_wallet(self.user.id)
        wallet2 = self.reward_service.get_user_wallet(user2.id)
        
        self.assertTrue(wallet1['success'])
        self.assertTrue(wallet2['success'])
        self.assertEqual(wallet1['wallet']['balance'], Decimal('25.00'))
        self.assertEqual(wallet2['wallet']['balance'], Decimal('25.00'))


if __name__ == '__main__':
    pytest.main([__file__])

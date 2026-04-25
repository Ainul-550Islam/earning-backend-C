"""
Test Campaign Bid Service

Comprehensive tests for campaign bidding functionality
including bid management, optimization, and performance tracking.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign, CampaignBid
from ..models.advertiser import Advertiser
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
from ..serializers import CampaignBidSerializer

User = get_user_model()


class CampaignBidServiceTestCase(APITestCase):
    """Test cases for campaign bid service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        self.optimizer = CampaignOptimizer()
    
    def test_create_campaign_bid(self):
        """Test creating a campaign bid."""
        bid_data = {
            'campaign': self.campaign,
            'bid_type': 'cpm',
            'bid_amount': Decimal('2.50'),
            'max_bid': Decimal('5.00'),
            'min_bid': Decimal('0.50'),
            'bid_strategy': 'auto',
            'target_cpa': Decimal('10.00'),
            'target_roas': Decimal('3.00')
        }
        
        bid = CampaignBid.objects.create(**bid_data)
        
        self.assertEqual(bid.campaign, self.campaign)
        self.assertEqual(bid.bid_type, 'cpm')
        self.assertEqual(bid.bid_amount, Decimal('2.50'))
        self.assertEqual(bid.max_bid, Decimal('5.00'))
        self.assertEqual(bid.min_bid, Decimal('0.50'))
        self.assertEqual(bid.bid_strategy, 'auto')
        self.assertEqual(bid.target_cpa, Decimal('10.00'))
        self.assertEqual(bid.target_roas, Decimal('3.00'))
    
    def test_update_campaign_bid(self):
        """Test updating a campaign bid."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
        
        # Update bid
        bid.bid_amount = Decimal('1.50')
        bid.max_bid = Decimal('3.00')
        bid.target_cpa = Decimal('12.00')
        bid.save()
        
        bid.refresh_from_db()
        self.assertEqual(bid.bid_amount, Decimal('1.50'))
        self.assertEqual(bid.max_bid, Decimal('3.00'))
        self.assertEqual(bid.target_cpa, Decimal('12.00'))
    
    def test_bid_validation(self):
        """Test bid validation."""
        # Test negative bid amount
        with self.assertRaises(Exception):
            CampaignBid.objects.create(
                campaign=self.campaign,
                bid_type='cpc',
                bid_amount=Decimal('-1.00')
            )
        
        # Test max bid less than min bid
        with self.assertRaises(Exception):
            CampaignBid.objects.create(
                campaign=self.campaign,
                bid_type='cpc',
                bid_amount=Decimal('1.00'),
                max_bid=Decimal('0.50'),
                min_bid=Decimal('1.00')
            )
    
    def test_bid_optimization(self):
        """Test bid optimization."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # Simulate performance data
        performance_data = {
            'ctr': 0.02,
            'conversion_rate': 0.05,
            'cpc': Decimal('1.20'),
            'cpa': Decimal('24.00'),
            'roas': Decimal('2.50')
        }
        
        # Optimize bid
        optimized_bid = self.optimizer.optimize_bid(bid, performance_data)
        
        self.assertIsNotNone(optimized_bid)
        self.assertGreaterEqual(optimized_bid, bid.min_bid)
        self.assertLessEqual(optimized_bid, bid.max_bid)
    
    def test_bid_performance_tracking(self):
        """Test bid performance tracking."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
        
        # Track performance
        performance = bid.get_performance_metrics()
        
        self.assertIn('impressions', performance)
        self.assertIn('clicks', performance)
        self.assertIn('conversions', performance)
        self.assertIn('cost', performance)
        self.assertIn('ctr', performance)
        self.assertIn('cpc', performance)
        self.assertIn('cpa', performance)
    
    def test_bid_strategy_auto(self):
        """Test automatic bid strategy."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # Simulate auto optimization
        current_performance = {
            'ctr': 0.015,  # Below target
            'conversion_rate': 0.03,
            'cpc': Decimal('1.20'),
            'cpa': Decimal('40.00')
        }
        
        new_bid = self.optimizer.auto_optimize_bid(bid, current_performance)
        
        # Should adjust bid based on performance
        self.assertIsNotNone(new_bid)
        self.assertGreaterEqual(new_bid, bid.min_bid)
        self.assertLessEqual(new_bid, bid.max_bid)
    
    def test_bid_strategy_manual(self):
        """Test manual bid strategy."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='manual'
        )
        
        # Manual strategy should not auto-optimize
        current_performance = {
            'ctr': 0.015,
            'conversion_rate': 0.03,
            'cpc': Decimal('1.20'),
            'cpa': Decimal('40.00')
        }
        
        new_bid = self.optimizer.auto_optimize_bid(bid, current_performance)
        
        # Should return original bid for manual strategy
        self.assertEqual(new_bid, bid.bid_amount)
    
    def test_bid_budget_constraints(self):
        """Test bid budget constraints."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
        
        # Test bid adjustment based on budget
        remaining_budget = self.campaign.daily_budget - Decimal('50.00')
        
        adjusted_bid = self.optimizer.adjust_bid_for_budget(bid, remaining_budget)
        
        # Should adjust bid if budget is limited
        if remaining_budget < bid.bid_amount * 100:  # Assuming 100 clicks
            self.assertLessEqual(adjusted_bid, bid.bid_amount)
    
    def test_bid_competition_analysis(self):
        """Test bid competition analysis."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
        
        # Simulate competition data
        competition_data = {
            'avg_bid': Decimal('1.20'),
            'min_bid': Decimal('0.50'),
            'max_bid': Decimal('3.00'),
            'competition_level': 'high'
        }
        
        competitive_bid = self.optimizer.adjust_for_competition(bid, competition_data)
        
        # Should adjust bid based on competition
        self.assertIsNotNone(competitive_bid)
    
    def test_bid_a_b_testing(self):
        """Test bid A/B testing."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # Create A/B test variants
        variant_a = bid.bid_amount
        variant_b = Decimal('1.20')
        
        # Simulate A/B test results
        test_results = {
            'variant_a': {
                'impressions': 1000,
                'clicks': 20,
                'conversions': 1,
                'cost': Decimal('20.00')
            },
            'variant_b': {
                'impressions': 1000,
                'clicks': 25,
                'conversions': 2,
                'cost': Decimal('30.00')
            }
        }
        
        winning_variant = self.optimizer.analyze_ab_test(test_results)
        
        # Should determine winning variant
        self.assertIn(winning_variant, ['variant_a', 'variant_b'])
    
    def test_bid_seasonal_adjustment(self):
        """Test bid seasonal adjustment."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # Simulate seasonal data
        seasonal_data = {
            'season': 'holiday',
            'demand_multiplier': 1.5,
            'competition_multiplier': 1.3
        }
        
        seasonal_bid = self.optimizer.adjust_for_seasonality(bid, seasonal_data)
        
        # Should adjust bid for seasonality
        self.assertIsNotNone(seasonal_bid)
    
    def test_bid_performance_prediction(self):
        """Test bid performance prediction."""
        bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
        
        # Predict performance
        predicted_performance = self.optimizer.predict_performance(bid)
        
        self.assertIn('predicted_ctr', predicted_performance)
        self.assertIn('predicted_cvr', predicted_performance)
        self.assertIn('predicted_cpa', predicted_performance)
        self.assertIn('confidence_score', predicted_performance)


class CampaignBidSerializerTestCase(APITestCase):
    """Test cases for CampaignBidSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            status='active'
        )
        
        self.bid = CampaignBid.objects.create(
            campaign=self.campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25')
        )
    
    def test_bid_serialization(self):
        """Test bid serialization."""
        serializer = CampaignBidSerializer(self.bid)
        
        data = serializer.data
        
        self.assertEqual(data['campaign'], self.campaign.id)
        self.assertEqual(data['bid_type'], 'cpc')
        self.assertEqual(data['bid_amount'], '1.00')
        self.assertEqual(data['max_bid'], '2.00')
        self.assertEqual(data['min_bid'], '0.25')
    
    def test_bid_deserialization(self):
        """Test bid deserialization."""
        data = {
            'campaign': self.campaign.id,
            'bid_type': 'cpm',
            'bid_amount': '2.50',
            'max_bid': '5.00',
            'min_bid': '0.50',
            'bid_strategy': 'auto',
            'target_cpa': '10.00'
        }
        
        serializer = CampaignBidSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        bid = serializer.save()
        
        self.assertEqual(bid.bid_type, 'cpm')
        self.assertEqual(bid.bid_amount, Decimal('2.50'))
        self.assertEqual(bid.max_bid, Decimal('5.00'))
        self.assertEqual(bid.min_bid, Decimal('0.50'))
        self.assertEqual(bid.bid_strategy, 'auto')
        self.assertEqual(bid.target_cpa, Decimal('10.00'))
    
    def test_bid_validation(self):
        """Test bid validation in serializer."""
        # Test invalid bid type
        data = {
            'campaign': self.campaign.id,
            'bid_type': 'invalid',
            'bid_amount': '1.00'
        }
        
        serializer = CampaignBidSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('bid_type', serializer.errors)
        
        # Test negative bid amount
        data = {
            'campaign': self.campaign.id,
            'bid_type': 'cpc',
            'bid_amount': '-1.00'
        }
        
        serializer = CampaignBidSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('bid_amount', serializer.errors)
    
    def test_bid_update_serialization(self):
        """Test bid update serialization."""
        data = {
            'bid_amount': '1.50',
            'max_bid': '3.00',
            'target_cpa': '12.00'
        }
        
        serializer = CampaignBidSerializer(instance=self.bid, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_bid = serializer.save()
        
        self.assertEqual(updated_bid.bid_amount, Decimal('1.50'))
        self.assertEqual(updated_bid.max_bid, Decimal('3.00'))
        self.assertEqual(updated_bid.target_cpa, Decimal('12.00'))


class CampaignBidIntegrationTestCase(APITestCase):
    """Integration tests for campaign bidding."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.optimizer = CampaignOptimizer()
    
    def test_complete_bid_lifecycle(self):
        """Test complete bid lifecycle."""
        # 1. Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Bid Lifecycle Campaign',
            description='Testing bid lifecycle',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        # 2. Create bid
        bid = CampaignBid.objects.create(
            campaign=campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # 3. Simulate performance
        performance_data = {
            'impressions': 1000,
            'clicks': 20,
            'conversions': 1,
            'cost': Decimal('20.00'),
            'ctr': 0.02,
            'conversion_rate': 0.05,
            'cpc': Decimal('1.00'),
            'cpa': Decimal('20.00'),
            'roas': Decimal('5.00')
        }
        
        # 4. Optimize bid
        optimized_bid = self.optimizer.optimize_bid(bid, performance_data)
        
        # 5. Update bid
        bid.bid_amount = optimized_bid
        bid.save()
        
        # Verify results
        bid.refresh_from_db()
        self.assertEqual(bid.bid_amount, optimized_bid)
        self.assertGreaterEqual(optimized_bid, bid.min_bid)
        self.assertLessEqual(optimized_bid, bid.max_bid)
    
    def test_multiple_campaign_bidding(self):
        """Test bidding across multiple campaigns."""
        campaigns = []
        bids = []
        
        # Create multiple campaigns with bids
        for i in range(3):
            campaign = AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Multi Bid Campaign {i}',
                description=f'Testing multiple campaigns {i}',
                daily_budget=Decimal('100.00'),
                status='active'
            )
            campaigns.append(campaign)
            
            bid = CampaignBid.objects.create(
                campaign=campaign,
                bid_type='cpc',
                bid_amount=Decimal('1.00'),
                max_bid=Decimal('2.00'),
                min_bid=Decimal('0.25'),
                bid_strategy='auto'
            )
            bids.append(bid)
        
        # Optimize all bids
        for bid in bids:
            performance_data = {
                'ctr': 0.02,
                'conversion_rate': 0.05,
                'cpc': Decimal('1.00'),
                'cpa': Decimal('20.00')
            }
            
            optimized_bid = self.optimizer.optimize_bid(bid, performance_data)
            bid.bid_amount = optimized_bid
            bid.save()
        
        # Verify all bids were optimized
        for bid in bids:
            bid.refresh_from_db()
            self.assertIsNotNone(bid.bid_amount)
            self.assertGreaterEqual(bid.bid_amount, bid.min_bid)
            self.assertLessEqual(bid.bid_amount, bid.max_bid)
    
    def test_bid_budget_integration(self):
        """Test bid integration with budget management."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Integration Campaign',
            description='Testing budget integration',
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('500.00'),
            status='active'
        )
        
        bid = CampaignBid.objects.create(
            campaign=campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            max_bid=Decimal('2.00'),
            min_bid=Decimal('0.25'),
            bid_strategy='auto'
        )
        
        # Test bid adjustment based on remaining budget
        remaining_budget = Decimal('25.00')  # Half of daily budget
        
        adjusted_bid = self.optimizer.adjust_bid_for_budget(bid, remaining_budget)
        
        # Should adjust bid to stay within budget
        self.assertIsNotNone(adjusted_bid)
        self.assertLessEqual(adjusted_bid, bid.bid_amount)
    
    @patch('advertiser_portal.services.campaign.CampaignOptimizer.optimize_bid')
    def test_bid_optimization_integration(self, mock_optimize):
        """Test bid optimization integration."""
        mock_optimize.return_value = Decimal('1.25')
        
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Optimization Integration Campaign',
            description='Testing optimization integration',
            status='active'
        )
        
        bid = CampaignBid.objects.create(
            campaign=campaign,
            bid_type='cpc',
            bid_amount=Decimal('1.00'),
            bid_strategy='auto'
        )
        
        performance_data = {
            'ctr': 0.02,
            'conversion_rate': 0.05,
            'cpc': Decimal('1.00'),
            'cpa': Decimal('20.00')
        }
        
        # Optimize bid
        optimized_bid = self.optimizer.optimize_bid(bid, performance_data)
        
        # Verify optimization was called
        mock_optimize.assert_called_once_with(bid, performance_data)
        self.assertEqual(optimized_bid, Decimal('1.25'))

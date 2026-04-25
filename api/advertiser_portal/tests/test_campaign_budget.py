"""
Test Campaign Budget Service

Comprehensive tests for campaign budget functionality
including budget management, enforcement, and optimization.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign
from ..models.billing import AdvertiserWallet, CampaignSpend
from ..models.advertiser import Advertiser
try:
    from ..services import CampaignBudgetService
except ImportError:
    CampaignBudgetService = None
try:
    from ..services import BudgetEnforcementService
except ImportError:
    BudgetEnforcementService = None

User = get_user_model()


class CampaignBudgetServiceTestCase(APITestCase):
    """Test cases for campaign budget service."""
    
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
        
        # Create advertiser wallet
        self.wallet = AdvertiserWallet.objects.create(
            advertiser=self.advertiser,
            balance=Decimal('1000.00'),
            currency='USD'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        self.budget_service = CampaignBudgetService()
        self.enforcement_service = BudgetEnforcementService()
    
    def test_create_campaign_budget(self):
        """Test creating campaign with budget."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Test Campaign',
            description='Testing budget functionality',
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('500.00'),
            status='active'
        )
        
        self.assertEqual(campaign.daily_budget, Decimal('50.00'))
        self.assertEqual(campaign.total_budget, Decimal('500.00'))
        self.assertEqual(campaign.status, 'active')
    
    def test_update_campaign_budget(self):
        """Test updating campaign budget."""
        # Update daily budget
        self.campaign.daily_budget = Decimal('150.00')
        self.campaign.save()
        
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.daily_budget, Decimal('150.00'))
        
        # Update total budget
        self.campaign.total_budget = Decimal('1500.00')
        self.campaign.save()
        
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.total_budget, Decimal('1500.00'))
    
    def test_budget_validation(self):
        """Test budget validation."""
        # Test negative budget
        with self.assertRaises(Exception):
            AdCampaign.objects.create(
                advertiser=self.advertiser,
                name='Invalid Budget Campaign',
                description='Testing negative budget',
                daily_budget=Decimal('-50.00'),
                total_budget=Decimal('500.00'),
                status='active'
            )
        
        # Test total budget less than daily budget
        with self.assertRaises(Exception):
            AdCampaign.objects.create(
                advertiser=self.advertiser,
                name='Invalid Budget Campaign',
                description='Testing budget mismatch',
                daily_budget=Decimal('1000.00'),
                total_budget=Decimal('500.00'),
                status='active'
            )
    
    def test_daily_budget_check(self):
        """Test daily budget checking."""
        # Check if campaign is within daily budget
        is_within_budget = self.budget_service.check_daily_budget(self.campaign)
        self.assertTrue(is_within_budget)
        
        # Simulate daily spend
        CampaignSpend.objects.create(
            campaign=self.campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('80.00'),
            total_spend=Decimal('800.00')
        )
        
        # Check again
        is_within_budget = self.budget_service.check_daily_budget(self.campaign)
        self.assertTrue(is_within_budget)  # 80 < 100
        
        # Exceed daily budget
        CampaignSpend.objects.filter(campaign=self.campaign).update(
            daily_spend=Decimal('120.00')
        )
        
        is_within_budget = self.budget_service.check_daily_budget(self.campaign)
        self.assertFalse(is_within_budget)  # 120 > 100
    
    def test_total_budget_check(self):
        """Test total budget checking."""
        # Check if campaign is within total budget
        is_within_budget = self.budget_service.check_total_budget(self.campaign)
        self.assertTrue(is_within_budget)
        
        # Simulate total spend
        CampaignSpend.objects.create(
            campaign=self.campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('50.00'),
            total_spend=Decimal('800.00')
        )
        
        # Check again
        is_within_budget = self.budget_service.check_total_budget(self.campaign)
        self.assertTrue(is_within_budget)  # 800 < 1000
        
        # Exceed total budget
        CampaignSpend.objects.filter(campaign=self.campaign).update(
            total_spend=Decimal('1200.00')
        )
        
        is_within_budget = self.budget_service.check_total_budget(self.campaign)
        self.assertFalse(is_within_budget)  # 1200 > 1000
    
    def test_budget_spend_tracking(self):
        """Test budget spend tracking."""
        # Record spend
        spend_data = {
            'campaign': self.campaign,
            'spend_date': timezone.now().date(),
            'daily_spend': Decimal('25.00'),
            'total_spend': Decimal('250.00'),
            'impressions': 1000,
            'clicks': 50,
            'conversions': 2
        }
        
        spend = CampaignSpend.objects.create(**spend_data)
        
        self.assertEqual(spend.campaign, self.campaign)
        self.assertEqual(spend.daily_spend, Decimal('25.00'))
        self.assertEqual(spend.total_spend, Decimal('250.00'))
        self.assertEqual(spend.impressions, 1000)
        self.assertEqual(spend.clicks, 50)
        self.assertEqual(spend.conversions, 2)
    
    def test_budget_optimization(self):
        """Test budget optimization."""
        # Simulate performance data
        performance_data = {
            'daily_spend': Decimal('80.00'),
            'total_spend': Decimal('800.00'),
            'impressions': 1000,
            'clicks': 50,
            'conversions': 2,
            'ctr': 0.05,
            'cpc': Decimal('1.60'),
            'cpa': Decimal('40.00'),
            'roas': Decimal('2.50')
        }
        
        # Optimize budget
        optimization_result = self.budget_service.optimize_budget(self.campaign, performance_data)
        
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommendations', optimization_result)
        self.assertIn('budget_adjustments', optimization_result)
        self.assertIn('performance_analysis', optimization_result)
    
    def test_budget_allocation(self):
        """Test budget allocation across campaigns."""
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            campaign = AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Budget Campaign {i}',
                description=f'Testing budget allocation {i}',
                daily_budget=Decimal('50.00'),
                total_budget=Decimal('500.00'),
                status='active'
            )
            campaigns.append(campaign)
        
        # Allocate budget
        total_budget = Decimal('300.00')
        allocation_result = self.budget_service.allocate_budget_to_campaigns(
            campaigns, total_budget
        )
        
        self.assertIsNotNone(allocation_result)
        self.assertIn('allocations', allocation_result)
        self.assertIn('remaining_budget', allocation_result)
        
        # Verify allocations
        allocations = allocation_result['allocations']
        self.assertEqual(len(allocations), 3)
        
        # Check total allocated
        total_allocated = sum(alloc[c.id] for c in campaigns)
        self.assertLessEqual(total_allocated, total_budget)
    
    def test_budget_pacing(self):
        """Test budget pacing."""
        # Create campaign with start date
        start_date = timezone.now() - timezone.timedelta(days=5)
        end_date = timezone.now() + timezone.timedelta(days=25)
        
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Pacing Test Campaign',
            description='Testing budget pacing',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('3000.00'),
            start_date=start_date,
            end_date=end_date,
            status='active'
        )
        
        # Simulate spend
        CampaignSpend.objects.create(
            campaign=campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('80.00'),
            total_spend=Decimal('400.00')
        )
        
        # Check pacing
        pacing_result = self.budget_service.check_budget_pacing(campaign)
        
        self.assertIsNotNone(pacing_result)
        self.assertIn('daily_pacing', pacing_result)
        self.assertIn('total_pacing', pacing_result)
        self.assertIn('recommendations', pacing_result)
    
    def test_budget_alerts(self):
        """Test budget alerts."""
        # Create campaign and spend
        CampaignSpend.objects.create(
            campaign=self.campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('95.00'),  # Near daily limit
            total_spend=Decimal('950.00')  # Near total limit
        )
        
        # Check for alerts
        alerts = self.budget_service.check_budget_alerts(self.campaign)
        
        self.assertIsNotNone(alerts)
        self.assertIn('daily_budget_alerts', alerts)
        self.assertIn('total_budget_alerts', alerts)
        self.assertIn('recommendations', alerts)
    
    def test_budget_enforcement(self):
        """Test budget enforcement."""
        # Create campaign and exceed budget
        CampaignSpend.objects.create(
            campaign=self.campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('120.00'),  # Exceed daily budget
            total_spend=Decimal('800.00')
        )
        
        # Enforce budget
        enforcement_result = self.enforcement_service.enforce_budget(self.campaign)
        
        self.assertIsNotNone(enforcement_result)
        self.assertIn('action_taken', enforcement_result)
        self.assertIn('campaign_status', enforcement_result)
        
        # Check if campaign was paused
        if enforcement_result['action_taken'] == 'paused':
            self.campaign.refresh_from_db()
            self.assertEqual(self.campaign.status, 'paused')
    
    def test_budget_reallocation(self):
        """Test budget reallocation."""
        # Create campaigns with different performance
        high_performer = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='High Performer',
            description='High performing campaign',
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('500.00'),
            status='active'
        )
        
        low_performer = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Low Performer',
            description='Low performing campaign',
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('500.00'),
            status='active'
        )
        
        # Simulate performance data
        performance_data = {
            high_performer.id: {
                'daily_spend': Decimal('40.00'),
                'impressions': 1000,
                'clicks': 100,
                'conversions': 10,
                'cpa': Decimal('4.00'),
                'roas': Decimal('5.00')
            },
            low_performer.id: {
                'daily_spend': Decimal('40.00'),
                'impressions': 1000,
                'clicks': 20,
                'conversions': 1,
                'cpa': Decimal('40.00'),
                'roas': Decimal('0.50')
            }
        }
        
        # Reallocate budget
        reallocation_result = self.budget_service.reallocate_budget(
            [high_performer, low_performer],
            performance_data
        )
        
        self.assertIsNotNone(reallocation_result)
        self.assertIn('reallocations', reallocation_result)
        self.assertIn('performance_improvement', reallocation_result)
    
    def test_budget_forecasting(self):
        """Test budget forecasting."""
        # Create campaign with historical data
        for i in range(7):
            spend_date = timezone.now().date() - timezone.timedelta(days=i)
            daily_spend = Decimal('80.00') + Decimal(str(i * 5))
            total_spend = Decimal('800.00') + Decimal(str(i * 50))
            
            CampaignSpend.objects.create(
                campaign=self.campaign,
                spend_date=spend_date,
                daily_spend=daily_spend,
                total_spend=total_spend
            )
        
        # Forecast budget
        forecast_result = self.budget_service.forecast_budget_spend(self.campaign, days=30)
        
        self.assertIsNotNone(forecast_result)
        self.assertIn('forecasted_daily_spend', forecast_result)
        self.assertIn('forecasted_total_spend', forecast_result)
        self.assertIn('budget_exhaustion_date', forecast_result)
        self.assertIn('confidence_level', forecast_result)
    
    def test_budget_analytics(self):
        """Test budget analytics."""
        # Create campaign with spend data
        CampaignSpend.objects.create(
            campaign=self.campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('80.00'),
            total_spend=Decimal('800.00'),
            impressions=1000,
            clicks=50,
            conversions=2
        )
        
        # Get analytics
        analytics = self.budget_service.get_budget_analytics(self.campaign)
        
        self.assertIsNotNone(analytics)
        self.assertIn('budget_utilization', analytics)
        self.assertIn('spend_efficiency', analytics)
        self.assertIn('performance_metrics', analytics)
        self.assertIn('recommendations', analytics)


class CampaignBudgetIntegrationTestCase(APITestCase):
    """Integration tests for campaign budget management."""
    
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
        
        # Create advertiser wallet
        self.wallet = AdvertiserWallet.objects.create(
            advertiser=self.advertiser,
            balance=Decimal('2000.00'),
            currency='USD'
        )
        
        self.budget_service = CampaignBudgetService()
        self.enforcement_service = BudgetEnforcementService()
    
    def test_complete_budget_lifecycle(self):
        """Test complete budget lifecycle."""
        # 1. Create campaign with budget
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Lifecycle Campaign',
            description='Testing budget lifecycle',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        # 2. Track spend
        spend_data = {
            'campaign': campaign,
            'spend_date': timezone.now().date(),
            'daily_spend': Decimal('50.00'),
            'total_spend': Decimal('200.00'),
            'impressions': 500,
            'clicks': 25,
            'conversions': 1
        }
        
        CampaignSpend.objects.create(**spend_data)
        
        # 3. Check budget status
        is_within_daily_budget = self.budget_service.check_daily_budget(campaign)
        is_within_total_budget = self.budget_service.check_total_budget(campaign)
        
        self.assertTrue(is_within_daily_budget)
        self.assertTrue(is_within_total_budget)
        
        # 4. Get analytics
        analytics = self.budget_service.get_budget_analytics(campaign)
        
        self.assertIsNotNone(analytics)
        self.assertIn('budget_utilization', analytics)
        
        # 5. Optimize budget
        performance_data = {
            'daily_spend': Decimal('50.00'),
            'total_spend': Decimal('200.00'),
            'impressions': 500,
            'clicks': 25,
            'conversions': 1,
            'ctr': 0.05,
            'cpc': Decimal('2.00'),
            'cpa': Decimal('50.00'),
            'roas': Decimal('2.00')
        }
        
        optimization_result = self.budget_service.optimize_budget(campaign, performance_data)
        
        # Verify results
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommendations', optimization_result)
    
    def test_multi_campaign_budget_management(self):
        """Test budget management across multiple campaigns."""
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            campaign = AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Multi Budget Campaign {i}',
                description=f'Testing multi-campaign budget {i}',
                daily_budget=Decimal('50.00'),
                total_budget=Decimal('500.00'),
                status='active'
            )
            campaigns.append(campaign)
            
            # Create spend data for each campaign
            CampaignSpend.objects.create(
                campaign=campaign,
                spend_date=timezone.now().date(),
                daily_spend=Decimal('30.00') + Decimal(str(i * 10)),
                total_spend=Decimal('150.00') + Decimal(str(i * 50)),
                impressions=500 + i * 100,
                clicks=25 + i * 5,
                conversions=1 + i
            )
        
        # Check overall budget status
        total_daily_budget = sum(c.daily_budget for c in campaigns)
        total_daily_spend = sum(
            CampaignSpend.objects.filter(campaign=c).first().daily_spend
            for c in campaigns
        )
        
        self.assertLess(total_daily_spend, total_daily_budget)
        
        # Allocate additional budget
        additional_budget = Decimal('100.00')
        allocation_result = self.budget_service.allocate_budget_to_campaigns(
            campaigns, additional_budget
        )
        
        self.assertIsNotNone(allocation_result)
        self.assertIn('allocations', allocation_result)
        
        # Check for budget alerts
        all_alerts = []
        for campaign in campaigns:
            alerts = self.budget_service.check_budget_alerts(campaign)
            if alerts['daily_budget_alerts'] or alerts['total_budget_alerts']:
                all_alerts.extend(alerts['daily_budget_alerts'])
                all_alerts.extend(alerts['total_budget_alerts'])
        
        # Verify alerts
        self.assertIsInstance(all_alerts, list)
    
    def test_budget_enforcement_integration(self):
        """Test budget enforcement integration."""
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Enforcement Test Campaign',
            description='Testing budget enforcement',
            daily_budget=Decimal('50.00'),
            total_budget=Decimal('500.00'),
            status='active'
        )
        
        # Exceed daily budget
        CampaignSpend.objects.create(
            campaign=campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('60.00'),  # Exceed daily budget
            total_spend=Decimal('300.00')
        )
        
        # Enforce budget
        enforcement_result = self.enforcement_service.enforce_budget(campaign)
        
        # Verify enforcement
        self.assertIsNotNone(enforcement_result)
        
        if enforcement_result['action_taken'] == 'paused':
            campaign.refresh_from_db()
            self.assertEqual(campaign.status, 'paused')
        
        # Check enforcement history
        enforcement_history = self.enforcement_service.get_enforcement_history(campaign)
        
        self.assertIsNotNone(enforcement_history)
        self.assertIsInstance(enforcement_history, list)
    
    def test_budget_wallet_integration(self):
        """Test budget integration with wallet management."""
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Wallet Integration Campaign',
            description='Testing wallet integration',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        # Check wallet balance
        wallet_balance = self.wallet.balance
        campaign_budget = campaign.total_budget
        
        self.assertGreaterEqual(wallet_balance, campaign_budget)
        
        # Simulate spend
        CampaignSpend.objects.create(
            campaign=campaign,
            spend_date=timezone.now().date(),
            daily_spend=Decimal('50.00'),
            total_spend=Decimal('500.00')
        )
        
        # Check if wallet can support campaign
        can_support = self.budget_service.check_wallet_support(campaign, self.wallet)
        self.assertTrue(can_support)
        
        # Update wallet balance (simulate deduction)
        self.wallet.balance -= Decimal('500.00')
        self.wallet.save()
        
        # Check again
        can_support = self.budget_service.check_wallet_support(campaign, self.wallet)
        self.assertTrue(can_support)  # Still should support
    
    @patch('advertiser_portal.services.campaign.CampaignBudgetService.check_daily_budget')
    def test_budget_service_integration(self, mock_check):
        """Test budget service integration."""
        mock_check.return_value = True
        
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Integration Test Campaign',
            description='Testing budget service integration',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        # Check budget
        is_within_budget = self.budget_service.check_daily_budget(campaign)
        
        # Verify integration
        mock_check.assert_called_once_with(campaign)
        self.assertTrue(is_within_budget)
    
    def test_budget_performance_correlation(self):
        """Test budget-performance correlation analysis."""
        # Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Performance Correlation Campaign',
            description='Testing budget-performance correlation',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='active'
        )
        
        # Create spend data with performance metrics
        for i in range(7):
            spend_date = timezone.now().date() - timezone.timedelta(days=i)
            daily_spend = Decimal('80.00') + Decimal(str(i * 5))
            total_spend = Decimal('800.00') + Decimal(str(i * 50))
            impressions = 1000 + i * 100
            clicks = 50 + i * 10
            conversions = 2 + i
            
            CampaignSpend.objects.create(
                campaign=campaign,
                spend_date=spend_date,
                daily_spend=daily_spend,
                total_spend=total_spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions
            )
        
        # Analyze correlation
        correlation_result = self.budget_service.analyze_budget_performance_correlation(campaign)
        
        self.assertIsNotNone(correlation_result)
        self.assertIn('spend_vs_performance', correlation_result)
        self.assertIn('correlation_coefficient', correlation_result)
        self.assertIn('recommendations', correlation_result)
        
        # Verify correlation analysis
        self.assertIsInstance(correlation_result['correlation_coefficient'], (int, float, Decimal))
        self.assertGreaterEqual(abs(correlation_result['correlation_coefficient']), 0)
        self.assertLessEqual(abs(correlation_result['correlation_coefficient']), 1)

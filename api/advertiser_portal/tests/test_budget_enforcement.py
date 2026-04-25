"""
Test Budget Enforcement

Comprehensive tests for budget enforcement service
including automatic campaign pausing and wallet monitoring.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign
from ..models.billing import AdvertiserWallet, AdvertiserTransaction
try:
    from ..services import BudgetEnforcementService
except ImportError:
    BudgetEnforcementService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class BudgetEnforcementServiceTestCase(TestCase):
    """Test cases for BudgetEnforcementService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.billing_service = AdvertiserBillingService()
        self.budget_service = BudgetEnforcementService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('1000.00')
        wallet.save()
        
        self.valid_campaign_data = {
            'name': 'Test Campaign',
            'description': 'Test campaign description',
            'campaign_type': 'display',
            'budget_limit': 500.00,
            'daily_budget': 50.00,
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            'target_ctr': 2.0,
            'target_cpa': 5.0,
            'target_conversion_rate': 1.0,
        }
    
    def test_enforce_budget_limit_success(self):
        """Test successful budget limit enforcement."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Simulate spend that exceeds budget limit
        campaign_spend = Decimal('550.00')  # Exceeds budget limit of 500.00
        
        enforcement_result = self.budget_service.enforce_budget_limit(campaign, campaign_spend)
        
        self.assertTrue(enforcement_result.get('success', False))
        self.assertEqual(enforcement_result.get('action'), 'paused')
        self.assertEqual(enforcement_result.get('reason'), 'Budget limit exceeded')
        self.assertEqual(enforcement_result.get('current_spend'), campaign_spend)
        self.assertEqual(enforcement_result.get('budget_limit'), Decimal('500.00'))
    
    def test_enforce_daily_budget_success(self):
        """Test successful daily budget enforcement."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Simulate daily spend that exceeds daily budget
        daily_spend = Decimal('60.00')  # Exceeds daily budget of 50.00
        
        enforcement_result = self.budget_service.enforce_daily_budget(campaign, daily_spend)
        
        self.assertTrue(enforcement_result.get('success', False))
        self.assertEqual(enforcement_result.get('action'), 'paused')
        self.assertEqual(enforcement_result.get('reason'), 'Daily budget exceeded')
        self.assertEqual(enforcement_result.get('current_daily_spend'), daily_spend)
        self.assertEqual(enforcement_result.get('daily_budget'), Decimal('50.00'))
    
    def test_enforce_wallet_exhaustion_success(self):
        """Test successful wallet exhaustion enforcement."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        enforcement_result = self.budget_service.enforce_wallet_exhaustion(campaign)
        
        self.assertTrue(enforcement_result.get('success', False))
        self.assertEqual(enforcement_result.get('action'), 'paused')
        self.assertEqual(enforcement_result.get('reason'), 'Wallet balance exhausted')
        self.assertEqual(enforcement_result.get('wallet_balance'), Decimal('0.00'))
    
    def test_check_campaign_budget_status(self):
        """Test checking campaign budget status."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Get budget status
        budget_status = self.budget_service.check_campaign_budget_status(campaign)
        
        self.assertIn('budget_limit', budget_status)
        self.assertIn('daily_budget', budget_status)
        self.assertIn('total_spend', budget_status)
        self.assertIn('daily_spend', budget_status)
        self.assertIn('remaining_budget', budget_status)
        self.assertIn('remaining_daily_budget', budget_status)
        self.assertIn('budget_utilization', budget_status)
        self.assertIn('daily_budget_utilization', budget_status)
    
    def test_check_wallet_budget_status(self):
        """Test checking wallet budget status."""
        # Get wallet status
        wallet_status = self.budget_service.check_wallet_budget_status(self.advertiser)
        
        self.assertIn('total_balance', wallet_status)
        self.assertIn('available_balance', wallet_status)
        self.assertIn('credit_limit', wallet_status)
        self.assertIn('total_campaigns', wallet_status)
        self.assertIn('active_campaigns', wallet_status)
        self.assertIn('total_daily_budget', wallet_status)
    
    def test_auto_pause_campaigns_budget_limit(self):
        """Test auto-pause campaigns based on budget limit."""
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            data['budget_limit'] = 200.00 + (i * 100)
            campaign = self.billing_service.create_campaign(self.advertiser, data)
            self.billing_service.start_campaign(campaign)
            campaigns.append(campaign)
        
        # Simulate spend for first campaign
        campaigns[0].spend_amount = Decimal('250.00')  # Exceeds budget limit of 200.00
        
        # Auto-pause campaigns
        paused_campaigns = self.budget_service.auto_pause_campaigns_budget_limit()
        
        self.assertGreater(len(paused_campaigns), 0)
        
        # Check that first campaign was paused
        campaigns[0].refresh_from_db()
        self.assertEqual(campaigns[0].status, 'paused')
    
    def test_auto_pause_campaigns_daily_budget(self):
        """Test auto-pause campaigns based on daily budget."""
        # Create campaigns
        campaigns = []
        for i in range(3):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            data['daily_budget'] = 20.00 + (i * 10)
            campaign = self.billing_service.create_campaign(self.advertiser, data)
            self.billing_service.start_campaign(campaign)
            campaigns.append(campaign)
        
        # Simulate daily spend for first campaign
        campaigns[0].daily_spend = Decimal('30.00')  # Exceeds daily budget of 20.00
        
        # Auto-pause campaigns
        paused_campaigns = self.budget_service.auto_pause_campaigns_daily_budget()
        
        self.assertGreater(len(paused_campaigns), 0)
        
        # Check that first campaign was paused
        campaigns[0].refresh_from_db()
        self.assertEqual(campaigns[0].status, 'paused')
    
    def test_auto_pause_campaigns_wallet_exhaustion(self):
        """Test auto-pause campaigns based on wallet exhaustion."""
        # Create campaigns
        campaigns = []
        for i in range(3):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            campaign = self.billing_service.create_campaign(self.advertiser, data)
            self.billing_service.start_campaign(campaign)
            campaigns.append(campaign)
        
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        # Auto-pause campaigns
        paused_campaigns = self.budget_service.auto_pause_campaigns_wallet_exhaustion()
        
        self.assertEqual(len(paused_campaigns), 3)
        
        # Check that all campaigns were paused
        for campaign in campaigns:
            campaign.refresh_from_db()
            self.assertEqual(campaign.status, 'paused')
    
    def test_send_budget_exhaustion_notification(self):
        """Test sending budget exhaustion notifications."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        with patch(
            'api.advertiser_portal.services.billing.BudgetEnforcementService.send_notification'
        ) as mock_send_notification:
            
            # Send budget exhaustion notification
            self.budget_service.send_budget_exhaustion_notification(
                campaign,
                'Budget limit exceeded',
                Decimal('500.00'),
                Decimal('550.00')
            )
            
            mock_send_notification.assert_called_once()
            
            # Check notification data
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'budget_exhaustion')
                self.assertIn('Budget limit exceeded', notification_data['message'])
    
    def test_send_wallet_exhaustion_notification(self):
        """Test sending wallet exhaustion notifications."""
        with patch(
            'api.advertiser_portal.services.billing.BudgetEnforcementService.send_notification'
        ) as mock_send_notification:
            
            # Send wallet exhaustion notification
            self.budget_service.send_wallet_exhaustion_notification(
                self.advertiser,
                Decimal('0.00'),
                3  # Number of affected campaigns
            )
            
            mock_send_notification.assert_called_once()
            
            # Check notification data
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'wallet_exhaustion')
                self.assertIn('Wallet balance exhausted', notification_data['message'])
    
    def test_get_budget_enforcement_statistics(self):
        """Test getting budget enforcement statistics."""
        # Create some campaigns with different statuses
        campaigns = []
        
        # Active campaign
        campaign1 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        self.billing_service.start_campaign(campaign1)
        campaigns.append(campaign1)
        
        # Paused campaign
        campaign2 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        self.billing_service.start_campaign(campaign2)
        self.budget_service.pause_campaign(campaign2)
        campaigns.append(campaign2)
        
        # Get statistics
        stats = self.budget_service.get_budget_enforcement_statistics()
        
        self.assertIn('total_campaigns', stats)
        self.assertIn('active_campaigns', stats)
        self.assertIn('paused_campaigns', stats)
        self.assertIn('total_budget_limit', stats)
        self.assertIn('total_spend', stats)
        self.assertIn('budget_utilization', stats)
    
    def test_validate_budget_configuration(self):
        """Test budget configuration validation."""
        config = {
            'budget_limit': 1000.00,
            'daily_budget': 100.00,
            'auto_pause_enabled': True,
            'pause_threshold': 0.9,
        }
        
        validation_result = self.budget_service.validate_budget_configuration(config)
        
        self.assertTrue(validation_result.get('valid', True))
        self.assertEqual(len(validation_result.get('errors', [])), 0)
    
    def test_validate_budget_configuration_invalid(self):
        """Test budget configuration validation with invalid data."""
        config = {
            'budget_limit': 1000.00,
            'daily_budget': 2000.00,  # Higher than budget limit
            'auto_pause_enabled': True,
            'pause_threshold': 1.5,  # Invalid threshold
        }
        
        validation_result = self.budget_service.validate_budget_configuration(config)
        
        self.assertFalse(validation_result.get('valid', True))
        self.assertIn('daily_budget', validation_result.get('errors', {}))
        self.assertIn('pause_threshold', validation_result.get('errors', {}))
    
    def test_get_budget_alerts(self):
        """Test getting budget alerts."""
        # Create campaigns with different budget utilization
        campaigns = []
        
        # Campaign at 80% budget utilization
        campaign1 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        campaign1.budget_limit = Decimal('1000.00')
        campaign1.spend_amount = Decimal('800.00')
        campaign1.save()
        campaigns.append(campaign1)
        
        # Campaign at 105% budget utilization
        campaign2 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        campaign2.budget_limit = Decimal('1000.00')
        campaign2.spend_amount = Decimal('1050.00')
        campaign2.save()
        campaigns.append(campaign2)
        
        alerts = self.budget_service.get_budget_alerts(self.advertiser)
        
        self.assertIn('warning_alerts', alerts)
        self.assertIn('critical_alerts', alerts)
        
        # Should have one warning (80%) and one critical (105%)
        self.assertEqual(len(alerts['warning_alerts']), 1)
        self.assertEqual(len(alerts['critical_alerts']), 1)
    
    def test_get_daily_budget_alerts(self):
        """Test getting daily budget alerts."""
        # Create campaigns with different daily budget utilization
        campaigns = []
        
        # Campaign at 80% daily budget utilization
        campaign1 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        campaign1.daily_budget = Decimal('100.00')
        campaign1.daily_spend = Decimal('80.00')
        campaign1.save()
        campaigns.append(campaign1)
        
        # Campaign at 110% daily budget utilization
        campaign2 = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        campaign2.daily_budget = Decimal('100.00')
        campaign2.daily_spend = Decimal('110.00')
        campaign2.save()
        campaigns.append(campaign2)
        
        alerts = self.budget_service.get_daily_budget_alerts(self.advertiser)
        
        self.assertIn('warning_alerts', alerts)
        self.assertIn('critical_alerts', alerts)
        
        # Should have one warning (80%) and one critical (110%)
        self.assertEqual(len(alerts['warning_alerts']), 1)
        self.assertEqual(len(alerts['critical_alerts']), 1)
    
    def test_get_wallet_alerts(self):
        """Test getting wallet alerts."""
        # Set wallet balance to different levels
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')  # Low balance
        wallet.credit_limit = Decimal('1000.00')
        wallet.save()
        
        alerts = self.budget_service.get_wallet_alerts(self.advertiser)
        
        self.assertIn('low_balance_alerts', alerts)
        self.assertEqual(len(alerts['low_balance_alerts']), 1)
        
        # Check alert details
        alert = alerts['low_balance_alerts'][0]
        self.assertEqual(alert['current_balance'], Decimal('50.00'))
        self.assertEqual(alert['credit_limit'], Decimal('1000.00'))
        self.assertIn('percentage', alert)
    
    def test_calculate_budget_utilization(self):
        """Test budget utilization calculation."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        campaign.budget_limit = Decimal('1000.00')
        campaign.spend_amount = Decimal('750.00')
        campaign.save()
        
        utilization = self.budget_service.calculate_budget_utilization(campaign)
        
        self.assertEqual(utilization, 75.0)  # 750 / 1000 * 100
    
    def test_calculate_daily_budget_utilization(self):
        """Test daily budget utilization calculation."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        campaign.daily_budget = Decimal('100.00')
        campaign.daily_spend = Decimal('85.00')
        campaign.save()
        
        utilization = self.budget_service.calculate_daily_budget_utilization(campaign)
        
        self.assertEqual(utilization, 85.0)  # 85 / 100 * 100
    
    def test_check_campaign_budget_health(self):
        """Test campaign budget health check."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Set budget utilization to 60%
        campaign.budget_limit = Decimal('1000.00')
        campaign.spend_amount = Decimal('600.00')
        campaign.save()
        
        health = self.budget_service.check_campaign_budget_health(campaign)
        
        self.assertIn('status', health)
        self.assertIn('budget_health', health)
        self.assertIn('daily_budget_health', health)
        self.assertIn('recommendations', health)
        
        # Should be healthy at 60%
        self.assertEqual(health['status'], 'healthy')
    
    def test_check_wallet_budget_health(self):
        """Test wallet budget health check."""
        # Set wallet to 60% of credit limit
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('600.00')
        wallet.credit_limit = Decimal('1000.00')
        wallet.save()
        
        health = self.budget_service.check_wallet_budget_health(self.advertiser)
        
        self.assertIn('status', health)
        self.assertIn('balance_health', health)
        self.assertIn('recommendations', health)
        
        # Should be healthy at 60%
        self.assertEqual(health['status'], 'healthy')
    
    def test_get_budget_forecast(self):
        """Test budget forecasting."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.billing_service.start_campaign(campaign)
        
        # Get forecast for next 7 days
        forecast = self.budget_service.get_budget_forecast(
            campaign,
            days=7
        )
        
        self.assertIn('daily_forecast', forecast)
        self.assertIn('total_forecast', forecast)
        self.assertIn('budget_exhaustion_date', forecast)
        self.assertIn('confidence_level', forecast)
    
    def test_recommend_budget_adjustments(self):
        """Test budget adjustment recommendations."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Set performance data
        performance_data = {
            'daily_spend': Decimal('25.00'),
            'daily_conversions': 5,
            'cpa': Decimal('5.00'),
            'ctr': 2.0,
        }
        
        recommendations = self.budget_service.recommend_budget_adjustments(
            campaign,
            performance_data
        )
        
        self.assertIn('daily_budget_adjustment', recommendations)
        self.assertIn('budget_limit_adjustment', recommendations)
        self.assertIn('optimization_suggestions', recommendations)
        self.assertIn('expected_impact', recommendations)
    
    def test_enforce_budget_rules(self):
        """Test budget rule enforcement."""
        rules = [
            {
                'name': 'Auto-pause at 90%',
                'condition': 'budget_utilization >= 90',
                'action': 'pause_campaign',
                'enabled': True
            },
            {
                'name': 'Warning at 80%',
                'condition': 'budget_utilization >= 80',
                'action': 'send_warning',
                'enabled': True
            }
        ]
        
        # Set campaign to 85% utilization
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        campaign.budget_limit = Decimal('1000.00')
        campaign.spend_amount = Decimal('850.00')
        campaign.save()
        
        enforcement_results = self.budget_service.enforce_budget_rules(
            campaign,
            rules
        )
        
        self.assertEqual(len(enforcement_results), 2)
        
        # Check that warning rule was triggered
        warning_result = next(
            (r for r in enforcement_results if r['rule_name'] == 'Warning at 80%'),
            None
        )
        self.assertIsNotNone(warning_result)
        self.assertTrue(warning_result['triggered'])
        self.assertEqual(warning_result['action'], 'send_warning')
    
    def test_get_budget_enforcement_history(self):
        """Test budget enforcement history."""
        campaign = self.billing_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Create some enforcement actions
        for i in range(5):
            self.budget_service.record_enforcement_action(
                campaign,
                'budget_exhaustion',
                {'budget_limit': Decimal('1000.00'), 'current_spend': Decimal('1050.00')}
            )
        
        history = self.budget_service.get_budget_enforcement_history(campaign)
        
        self.assertEqual(len(history), 5)
        
        for record in history:
            self.assertEqual(record['campaign_id'], campaign.id)
            self.assertIn('action_type', record)
            self.assertIn('timestamp', record)
            self.assertIn('details', record)
    
    def test_export_budget_enforcement_report(self):
        """Test budget enforcement report export."""
        # Create some campaigns and enforcement actions
        campaigns = []
        for i in range(3):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            campaign = self.billing_service.create_campaign(self.advertiser, data)
            campaigns.append(campaign)
            
            # Create enforcement action
            self.budget_service.record_enforcement_action(
                campaign,
                'budget_exhaustion',
                {'budget_limit': Decimal('1000.00'), 'current_spend': Decimal('1050.00')}
            )
        
        # Export report
        report = self.budget_service.export_budget_enforcement_report(
            self.advertiser,
            days=30
        )
        
        self.assertIn('advertiser', report)
        self.assertIn('campaigns', report)
        self.assertIn('enforcement_actions', report)
        self.assertIn('statistics', report)
        self.assertIn('export_date', report)

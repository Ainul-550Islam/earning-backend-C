"""
Test Campaign Service

Comprehensive tests for campaign service functionality
including CRUD operations, lifecycle management, and optimization.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid
from ..models.advertiser import Advertiser, AdvertiserWallet
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class CampaignServiceTestCase(TestCase):
    """Test cases for CampaignService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.campaign_service = CampaignService()
        
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
        
        self.valid_campaign_data = {
            'name': 'Test Campaign',
            'description': 'Test campaign description',
            'campaign_type': 'display',
            'budget_limit': 1000.00,
            'daily_budget': 100.00,
            'start_date': timezone.now().date(),
            'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
            'target_ctr': 2.0,
            'target_cpa': 5.0,
            'target_conversion_rate': 1.0,
        }
    
    def test_create_campaign_success(self):
        """Test successful campaign creation."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        self.assertIsInstance(campaign, AdCampaign)
        self.assertEqual(campaign.advertiser, self.advertiser)
        self.assertEqual(campaign.name, 'Test Campaign')
        self.assertEqual(campaign.status, 'draft')
        self.assertEqual(campaign.budget_limit, Decimal('1000.00'))
        self.assertEqual(campaign.daily_budget, Decimal('100.00'))
    
    def test_create_campaign_invalid_data(self):
        """Test campaign creation with invalid data."""
        invalid_data = self.valid_campaign_data.copy()
        invalid_data['name'] = ''  # Empty name
        
        with self.assertRaises(ValueError) as context:
            self.campaign_service.create_campaign(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Campaign name is required', str(context.exception))
    
    def test_create_campaign_insufficient_budget(self):
        """Test campaign creation with insufficient wallet balance."""
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.campaign_service.create_campaign(
                self.advertiser,
                self.valid_campaign_data
            )
        
        self.assertIn('Insufficient wallet balance', str(context.exception))
    
    def test_update_campaign_success(self):
        """Test successful campaign update."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        update_data = {
            'name': 'Updated Campaign',
            'budget_limit': 2000.00,
            'description': 'Updated description',
        }
        
        updated_campaign = self.campaign_service.update_campaign(
            campaign,
            update_data
        )
        
        self.assertEqual(updated_campaign.name, 'Updated Campaign')
        self.assertEqual(updated_campaign.budget_limit, Decimal('2000.00'))
        self.assertEqual(updated_campaign.description, 'Updated description')
        self.assertEqual(campaign.status, 'draft')  # Unchanged
    
    def test_start_campaign_success(self):
        """Test successful campaign start."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        started_campaign = self.campaign_service.start_campaign(campaign)
        
        self.assertEqual(started_campaign.status, 'active')
        self.assertIsNotNone(started_campaign.started_at)
        
        # Check that bid config was created
        self.assertTrue(hasattr(started_campaign, 'bid_config'))
    
    def test_start_campaign_insufficient_balance(self):
        """Test starting campaign with insufficient balance."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Set wallet balance to 0
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('0.00')
        wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.campaign_service.start_campaign(campaign)
        
        self.assertIn('Insufficient wallet balance', str(context.exception))
    
    def test_pause_campaign_success(self):
        """Test successful campaign pause."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign first
        self.campaign_service.start_campaign(campaign)
        
        # Pause campaign
        paused_campaign = self.campaign_service.pause_campaign(campaign)
        
        self.assertEqual(paused_campaign.status, 'paused')
        self.assertIsNotNone(paused_campaign.paused_at)
    
    def test_pause_already_paused_campaign(self):
        """Test pausing already paused campaign."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        campaign.status = 'paused'
        campaign.save()
        
        with self.assertRaises(ValueError) as context:
            self.campaign_service.pause_campaign(campaign)
        
        self.assertIn('Campaign is already paused', str(context.exception))
    
    def test_resume_campaign_success(self):
        """Test successful campaign resume."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start and pause campaign first
        self.campaign_service.start_campaign(campaign)
        self.campaign_service.pause_campaign(campaign)
        
        # Resume campaign
        resumed_campaign = self.campaign_service.resume_campaign(campaign)
        
        self.assertEqual(resumed_campaign.status, 'active')
        self.assertIsNotNone(resumed_campaign.resumed_at)
    
    def test_end_campaign_success(self):
        """Test successful campaign end."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign first
        self.campaign_service.start_campaign(campaign)
        
        # End campaign
        ended_campaign = self.campaign_service.end_campaign(campaign)
        
        self.assertEqual(ended_campaign.status, 'ended')
        self.assertIsNotNone(ended_campaign.ended_at)
    
    def test_cancel_campaign_success(self):
        """Test successful campaign cancellation."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign first
        self.campaign_service.start_campaign(campaign)
        
        # Cancel campaign
        cancelled_campaign = self.campaign_service.cancel_campaign(campaign)
        
        self.assertEqual(cancelled_campaign.status, 'cancelled')
        self.assertIsNotNone(cancelled_campaign.cancelled_at)
    
    def test_clone_campaign_success(self):
        """Test successful campaign cloning."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Add some creatives and targeting
        self._add_test_creatives(campaign)
        self._add_test_targeting(campaign)
        
        # Clone campaign
        cloned_campaign = self.campaign_service.clone_campaign(campaign)
        
        self.assertEqual(cloned_campaign.name, 'Test Campaign (Clone)')
        self.assertEqual(cloned_campaign.status, 'draft')
        self.assertEqual(cloned_campaign.budget_limit, campaign.budget_limit)
        
        # Check that creatives were cloned
        self.assertEqual(cloned_campaign.creatives.count(), campaign.creatives.count())
        
        # Check that targeting was cloned
        self.assertEqual(cloned_campaign.targeting_rules.count(), campaign.targeting_rules.count())
    
    def test_get_campaign_statistics(self):
        """Test getting campaign statistics."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.campaign_service.start_campaign(campaign)
        
        stats = self.campaign_service.get_campaign_statistics(campaign)
        
        self.assertIn('total_impressions', stats)
        self.assertIn('total_clicks', stats)
        self.assertIn('total_conversions', stats)
        self.assertIn('total_spend', stats)
        self.assertIn('ctr', stats)
        self.assertIn('cpc', stats)
        self.assertIn('cpa', stats)
    
    def test_get_campaign_performance(self):
        """Test getting campaign performance metrics."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Get performance for last 7 days
        performance = self.campaign_service.get_campaign_performance(
            campaign,
            days=7
        )
        
        self.assertIn('daily_breakdown', performance)
        self.assertIn('summary', performance)
        self.assertIn('trends', performance)
    
    def test_search_campaigns(self):
        """Test campaign search functionality."""
        # Create multiple campaigns
        for i in range(5):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            self.campaign_service.create_campaign(self.advertiser, data)
        
        # Search by name
        results = self.campaign_service.search_campaigns(
            self.advertiser,
            'Campaign 1'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'Campaign 1')
    
    def test_get_active_campaigns(self):
        """Test getting active campaigns."""
        # Create campaigns
        for i in range(3):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i}'
            campaign = self.campaign_service.create_campaign(self.advertiser, data)
            
            if i < 2:
                self.campaign_service.start_campaign(campaign)
        
        active_campaigns = self.campaign_service.get_active_campaigns(self.advertiser)
        
        self.assertEqual(len(active_campaigns), 2)
        
        for campaign in active_campaigns:
            self.assertEqual(campaign.status, 'active')
    
    def test_validate_campaign_data_success(self):
        """Test successful campaign data validation."""
        is_valid, errors = self.campaign_service.validate_campaign_data(
            self.valid_campaign_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_campaign_data_invalid_dates(self):
        """Test campaign data validation with invalid dates."""
        invalid_data = self.valid_campaign_data.copy()
        invalid_data['start_date'] = timezone.now().date()
        invalid_data['end_date'] = (timezone.now() - timezone.timedelta(days=1)).date()
        
        is_valid, errors = self.campaign_service.validate_campaign_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('end_date', errors)
    
    def test_validate_campaign_data_invalid_budgets(self):
        """Test campaign data validation with invalid budgets."""
        invalid_data = self.valid_campaign_data.copy()
        invalid_data['daily_budget'] = 2000.00  # Higher than budget limit
        invalid_data['budget_limit'] = 1000.00
        
        is_valid, errors = self.campaign_service.validate_campaign_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('daily_budget', errors)
    
    def test_get_campaign_budget_status(self):
        """Test getting campaign budget status."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.campaign_service.start_campaign(campaign)
        
        budget_status = self.campaign_service.get_campaign_budget_status(campaign)
        
        self.assertIn('budget_limit', budget_status)
        self.assertIn('daily_budget', budget_status)
        self.assertIn('total_spend', budget_status)
        self.assertIn('remaining_budget', budget_status)
        self.assertIn('budget_utilization', budget_status)
    
    def test_get_campaign_recommendations(self):
        """Test getting campaign recommendations."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.campaign_service.start_campaign(campaign)
        
        recommendations = self.campaign_service.get_campaign_recommendations(campaign)
        
        self.assertIn('optimization_suggestions', recommendations)
        self.assertIn('budget_adjustments', recommendations)
        self.assertIn('targeting_improvements', recommendations)
    
    def test_export_campaign_data(self):
        """Test exporting campaign data."""
        campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Add some data
        self._add_test_creatives(campaign)
        self._add_test_targeting(campaign)
        
        export_data = self.campaign_service.export_campaign_data(campaign)
        
        self.assertIn('campaign', export_data)
        self.assertIn('creatives', export_data)
        self.assertIn('targeting', export_data)
        self.assertIn('statistics', export_data)
    
    def _add_test_creatives(self, campaign):
        """Add test creatives to campaign."""
        from ..models.campaign import CampaignCreative
        
        for i in range(3):
            CampaignCreative.objects.create(
                campaign=campaign,
                name=f'Creative {i}',
                creative_type='image',
                file_path=f'creative_{i}.jpg',
                status='active'
            )
    
    def _add_test_targeting(self, campaign):
        """Add test targeting rules to campaign."""
        from ..models.campaign import CampaignTargeting
        
        targeting_rules = [
            {
                'target_type': 'geo',
                'operator': 'in',
                'values': ['US', 'CA', 'UK'],
                'is_active': True
            },
            {
                'target_type': 'device',
                'operator': 'in',
                'values': ['desktop', 'mobile'],
                'is_active': True
            }
        ]
        
        for rule in targeting_rules:
            CampaignTargeting.objects.create(
                campaign=campaign,
                **rule
            )


class CampaignOptimizerTestCase(TestCase):
    """Test cases for CampaignOptimizer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.campaign_service = CampaignService()
        self.optimizer = CampaignOptimizer()
        
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
        
        self.campaign = self.campaign_service.create_campaign(
            self.advertiser,
            {
                'name': 'Test Campaign',
                'description': 'Test campaign description',
                'campaign_type': 'display',
                'budget_limit': 1000.00,
                'daily_budget': 100.00,
                'start_date': timezone.now().date(),
                'end_date': (timezone.now() + timezone.timedelta(days=30)).date(),
                'target_ctr': 2.0,
                'target_cpa': 5.0,
                'target_conversion_rate': 1.0,
                'auto_optimize_enabled': True,
            }
        )
        
        # Start campaign
        self.campaign_service.start_campaign(self.campaign)
    
    def test_optimize_bids_success(self):
        """Test successful bid optimization."""
        performance_data = {
            'impressions': 10000,
            'clicks': 200,
            'conversions': 20,
            'spend': 100.00,
            'ctr': 2.0,
            'cpc': 0.50,
            'cpa': 5.0,
            'conversion_rate': 10.0,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('optimizations_applied', optimization_result)
        self.assertIn('new_bid_config', optimization_result)
    
    def test_optimize_bids_low_performance(self):
        """Test bid optimization with low performance."""
        performance_data = {
            'impressions': 10000,
            'clicks': 50,  # Low clicks
            'conversions': 2,  # Low conversions
            'spend': 100.00,
            'ctr': 0.5,  # Low CTR
            'cpc': 2.0,  # High CPC
            'cpa': 50.0,  # High CPA
            'conversion_rate': 4.0,  # Low conversion rate
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('recommendations', optimization_result)
    
    def test_optimize_targeting_success(self):
        """Test successful targeting optimization."""
        performance_data = {
            'geo_performance': {
                'US': {'ctr': 2.5, 'cpa': 4.0},
                'CA': {'ctr': 1.5, 'cpa': 8.0},
                'UK': {'ctr': 3.0, 'cpa': 3.5},
            },
            'device_performance': {
                'desktop': {'ctr': 2.2, 'cpa': 4.5},
                'mobile': {'ctr': 1.8, 'cpa': 6.0},
            }
        }
        
        optimization_result = self.optimizer.optimize_targeting(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('targeting_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
    
    def test_optimize_targeting_underperforming_segments(self):
        """Test targeting optimization with underperforming segments."""
        performance_data = {
            'underperforming_segments': [
                {
                    'target_type': 'geo',
                    'value': 'CA',
                    'ctr': 0.5,
                    'cpa': 15.0,
                    'recommendation': 'exclude'
                },
                {
                    'target_type': 'device',
                    'value': 'mobile',
                    'ctr': 0.8,
                    'cpa': 12.0,
                    'recommendation': 'reduce_bid'
                }
            ]
        }
        
        optimization_result = self.optimizer.optimize_targeting(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('segments_optimized', optimization_result)
    
    def test_auto_optimization_enabled(self):
        """Test auto-optimization enabled campaign."""
        self.campaign.auto_optimize_enabled = True
        self.campaign.save()
        
        # Check if campaign is eligible for optimization
        is_eligible = self.optimizer.is_eligible_for_optimization(self.campaign)
        
        self.assertTrue(is_eligible)
    
    def test_auto_optimization_disabled(self):
        """Test auto-optimization disabled campaign."""
        self.campaign.auto_optimize_enabled = False
        self.campaign.save()
        
        # Check if campaign is eligible for optimization
        is_eligible = self.optimizer.is_eligible_for_optimization(self.campaign)
        
        self.assertFalse(is_eligible)
    
    def test_get_optimization_recommendations(self):
        """Test getting optimization recommendations."""
        recommendations = self.optimizer.get_optimization_recommendations(
            self.campaign
        )
        
        self.assertIn('bid_adjustments', recommendations)
        self.assertIn('targeting_improvements', recommendations)
        self.assertIn('creative_suggestions', recommendations)
        self.assertIn('budget_optimization', recommendations)
    
    def test_validate_optimization_rules(self):
        """Test optimization rule validation."""
        rules = [
            {
                'name': 'Low CTR Rule',
                'condition': 'ctr < 1.0',
                'action': 'increase_bid',
                'bid_adjustment': 0.2
            },
            {
                'name': 'High CPA Rule',
                'condition': 'cpa > 10.0',
                'action': 'decrease_bid',
                'bid_adjustment': -0.15
            }
        ]
        
        validation_result = self.optimizer.validate_optimization_rules(rules)
        
        self.assertTrue(validation_result.get('valid', True))
        self.assertEqual(len(validation_result.get('errors', [])), 0)
    
    def test_validate_optimization_rules_invalid(self):
        """Test optimization rule validation with invalid rules."""
        rules = [
            {
                'name': '',
                'condition': 'ctr < 1.0',
                'action': 'invalid_action',
                'bid_adjustment': 2.0  # Too high
            }
        ]
        
        validation_result = self.optimizer.validate_optimization_rules(rules)
        
        self.assertFalse(validation_result.get('valid', False))
        self.assertIn('name', validation_result.get('errors', {}))
        self.assertIn('action', validation_result.get('errors', {}))
        self.assertIn('bid_adjustment', validation_result.get('errors', {}))
    
    def test_apply_optimization_rules(self):
        """Test applying optimization rules."""
        rules = [
            {
                'name': 'Low CTR Rule',
                'condition': 'ctr < 1.0',
                'action': 'increase_bid',
                'bid_adjustment': 0.2
            }
        ]
        
        performance_data = {
            'ctr': 0.5,  # Triggers rule
            'cpc': 0.50,
            'cpa': 5.0,
        }
        
        applied_rules = self.optimizer.apply_optimization_rules(
            self.campaign,
            rules,
            performance_data
        )
        
        self.assertEqual(len(applied_rules), 1)
        self.assertEqual(applied_rules[0]['name'], 'Low CTR Rule')
        self.assertEqual(applied_rules[0]['triggered'], True)
    
    def test_get_optimization_history(self):
        """Test getting optimization history."""
        # Simulate some optimizations
        for i in range(5):
            self.optimizer.record_optimization(
                self.campaign,
                'bid_optimization',
                {'bid_adjustment': 0.1},
                {'improvement': 5.0}
            )
        
        history = self.optimizer.get_optimization_history(self.campaign)
        
        self.assertEqual(len(history), 5)
        
        for record in history:
            self.assertEqual(record['campaign_id'], self.campaign.id)
            self.assertIn('optimization_type', record)
            self.assertIn('timestamp', record)
    
    def test_optimization_performance_analysis(self):
        """Test optimization performance analysis."""
        # Create optimization history
        for i in range(10):
            self.optimizer.record_optimization(
                self.campaign,
                'bid_optimization',
                {'bid_adjustment': 0.1},
                {'improvement': 5.0 + i}
            )
        
        analysis = self.optimizer.analyze_optimization_performance(
            self.campaign
        )
        
        self.assertIn('total_optimizations', analysis)
        self.assertIn('average_improvement', analysis)
        self.assertIn('success_rate', analysis)
        self.assertIn('best_performing_optimization', analysis)
    
    def test_optimization_a_b_testing(self):
        """Test A/B testing of optimization strategies."""
        strategies = [
            {
                'name': 'Aggressive',
                'bid_adjustment': 0.3,
                'targeting_adjustment': 'expand'
            },
            {
                'name': 'Conservative',
                'bid_adjustment': 0.1,
                'targeting_adjustment': 'maintain'
            }
        ]
        
        ab_test_result = self.optimizer.run_optimization_ab_test(
            self.campaign,
            strategies,
            duration_days=7
        )
        
        self.assertIn('test_id', ab_test_result)
        self.assertIn('strategies', ab_test_result)
        self.assertIn('duration_days', ab_test_result)
    
    def test_optimization_rollback(self):
        """Test optimization rollback functionality."""
        # Create bid config
        original_bid = self.campaign.bid_config.base_bid
        
        # Apply optimization
        self.optimizer.apply_bid_optimization(
            self.campaign,
            {'base_bid': original_bid * 1.2}
        )
        
        # Rollback optimization
        rollback_result = self.optimizer.rollback_optimization(
            self.campaign,
            'bid_optimization'
        )
        
        self.assertTrue(rollback_result.get('success', False))
        
        # Check that bid was rolled back
        self.campaign.bid_config.refresh_from_db()
        self.assertEqual(self.campaign.bid_config.base_bid, original_bid)
    
    def test_optimization_scheduling(self):
        """Test optimization scheduling."""
        schedule = {
            'frequency': 'hourly',
            'optimization_types': ['bid_optimization', 'targeting_optimization'],
            'conditions': {
                'min_impressions': 1000,
                'min_clicks': 10
            }
        }
        
        scheduled_optimization = self.optimizer.schedule_optimization(
            self.campaign,
            schedule
        )
        
        self.assertIn('schedule_id', scheduled_optimization)
        self.assertEqual(scheduled_optimization['frequency'], 'hourly')
        self.assertIn('next_run', scheduled_optimization)
    
    def test_optimization_notifications(self):
        """Test optimization notifications."""
        with patch(
            'api.advertiser_portal.services.campaign.CampaignOptimizer.send_notification'
        ) as mock_send_notification:
            
            # Send optimization notification
            self.optimizer.send_optimization_notification(
                self.campaign,
                'optimization_completed',
                {
                    'optimization_type': 'bid_optimization',
                    'improvement': 15.5,
                    'changes_applied': 3
                }
            )
            
            mock_send_notification.assert_called_once()
            
            # Check notification data
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'optimization_completed')
                self.assertIn('improvement', notification_data['message'])

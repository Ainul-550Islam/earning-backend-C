"""
Test Campaign Optimizer

Comprehensive tests for campaign optimization
including bid optimization, targeting optimization, and ML integration.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign, CampaignBid, CampaignTargeting
from ..models.advertiser import Advertiser, AdvertiserWallet
try:
    from ..services import CampaignOptimizer
except ImportError:
    CampaignOptimizer = None
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


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
            'auto_optimize_enabled': True,
        }
        
        self.campaign = self.campaign_service.create_campaign(
            self.advertiser,
            self.valid_campaign_data
        )
        
        # Start campaign
        self.campaign_service.start_campaign(self.campaign)
    
    def test_optimize_bids_low_ctr(self):
        """Test bid optimization for low CTR."""
        performance_data = {
            'impressions': 10000,
            'clicks': 100,  # Low CTR: 1.0%
            'conversions': 10,
            'spend': 100.00,
            'ctr': 1.0,
            'cpc': 1.00,
            'cpa': 10.00,
            'conversion_rate': 10.0,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('optimizations_applied', optimization_result)
        self.assertIn('bid_adjustments', optimization_result)
        
        # Should increase bids to improve CTR
        bid_adjustments = optimization_result.get('bid_adjustments', [])
        self.assertGreater(len(bid_adjustments), 0)
        
        for adjustment in bid_adjustments:
            self.assertGreater(adjustment.get('new_bid', 0), adjustment.get('old_bid', 0))
    
    def test_optimize_bids_high_cpa(self):
        """Test bid optimization for high CPA."""
        performance_data = {
            'impressions': 10000,
            'clicks': 200,
            'conversions': 5,  # High CPA: 20.00
            'spend': 100.00,
            'ctr': 2.0,
            'cpc': 0.50,
            'cpa': 20.00,
            'conversion_rate': 2.5,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('optimizations_applied', optimization_result)
        self.assertIn('bid_adjustments', optimization_result)
        
        # Should decrease bids to reduce CPA
        bid_adjustments = optimization_result.get('bid_adjustments', [])
        self.assertGreater(len(bid_adjustments), 0)
        
        for adjustment in bid_adjustments:
            self.assertLess(adjustment.get('new_bid', 0), adjustment.get('old_bid', 0))
    
    def test_optimize_bids_good_performance(self):
        """Test bid optimization for good performance (no changes needed)."""
        performance_data = {
            'impressions': 10000,
            'clicks': 200,
            'conversions': 20,
            'spend': 100.00,
            'ctr': 2.0,  # Target CTR
            'cpc': 0.50,
            'cpa': 5.00,  # Target CPA
            'conversion_rate': 10.0,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertEqual(optimization_result.get('optimizations_applied', 0))
        self.assertIn('recommendations', optimization_result)
        
        # Should recommend maintaining current bids
        recommendations = optimization_result.get('recommendations', [])
        self.assertIn('maintain_current_bids', str(recommendations))
    
    def test_optimize_targeting_underperforming_geo(self):
        """Test targeting optimization for underperforming geo segments."""
        performance_data = {
            'geo_performance': {
                'US': {'ctr': 2.5, 'cpa': 4.0, 'conversions': 50},
                'CA': {'ctr': 0.8, 'cpa': 15.0, 'conversions': 5},
                'UK': {'ctr': 3.0, 'cpa': 3.5, 'conversions': 30},
            },
            'device_performance': {
                'desktop': {'ctr': 2.2, 'cpa': 4.5, 'conversions': 40},
                'mobile': {'ctr': 1.8, 'cpa': 6.0, 'conversions': 20},
            }
        }
        
        optimization_result = self.optimizer.optimize_targeting(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('targeting_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
        
        # Should exclude CA (high CPA) and adjust mobile bids
        targeting_changes = optimization_result.get('targeting_changes', [])
        
        geo_changes = [change for change in targeting_changes if change.get('target_type') == 'geo']
        device_changes = [change for change in targeting_changes if change.get('target_type') == 'device']
        
        # Should recommend excluding CA
        ca_change = next((change for change in geo_changes if change.get('value') == 'CA'), None)
        self.assertIsNotNone(ca_change)
        self.assertEqual(ca_change.get('action'), 'exclude')
    
    def test_optimize_targeting_expand_high_performing_segments(self):
        """Test targeting optimization to expand high-performing segments."""
        performance_data = {
            'geo_performance': {
                'US': {'ctr': 3.5, 'cpa': 2.5, 'conversions': 100},
                'CA': {'ctr': 0.8, 'cpa': 15.0, 'conversions': 5},
                'UK': {'ctr': 3.0, 'cpa': 3.5, 'conversions': 30},
            },
            'expansion_opportunities': {
                'geo': ['DE', 'FR'],  # Similar markets to UK
                'device': ['tablet']  # Similar to mobile
            }
        }
        
        optimization_result = self.optimizer.optimize_targeting(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('targeting_changes', optimization_result)
        self.assertIn('expansion_recommendations', optimization_result)
        
        # Should recommend expanding to similar markets
        expansions = optimization_result.get('expansion_recommendations', [])
        self.assertGreater(len(expansions), 0)
    
    def test_optimize_targeting_no_data(self):
        """Test targeting optimization with insufficient data."""
        performance_data = {
            'impressions': 100,  # Too low for targeting optimization
            'clicks': 2,
            'conversions': 0,
        }
        
        optimization_result = self.optimizer.optimize_targeting(
            self.campaign,
            performance_data
        )
        
        self.assertFalse(optimization_result.get('success', False))
        self.assertIn('error', optimization_result)
        self.assertIn('insufficient_data', optimization_result.get('error', ''))
    
    def test_auto_optimization_eligibility(self):
        """Test campaign eligibility for auto-optimization."""
        # Campaign should be eligible
        is_eligible = self.optimizer.is_eligible_for_optimization(self.campaign)
        self.assertTrue(is_eligible)
        
        # Disable auto-optimization
        self.campaign.auto_optimize_enabled = False
        self.campaign.save()
        
        # Campaign should not be eligible
        is_eligible = self.optimizer.is_eligible_for_optimization(self.campaign)
        self.assertFalse(is_eligible)
        
        # Re-enable auto-optimization
        self.campaign.auto_optimize_enabled = True
        self.campaign.save()
        
        # Pause campaign
        self.campaign.status = 'paused'
        self.campaign.save()
        
        # Campaign should not be eligible when paused
        is_eligible = self.optimizer.is_eligible_for_optimization(self.campaign)
        self.assertFalse(is_eligible)
    
    def test_optimization_rules_validation(self):
        """Test optimization rules validation."""
        valid_rules = [
            {
                'name': 'Low CTR Rule',
                'condition': 'ctr < 1.0',
                'action': 'increase_bid',
                'bid_adjustment': 0.2,
                'enabled': True
            },
            {
                'name': 'High CPA Rule',
                'condition': 'cpa > 10.0',
                'action': 'decrease_bid',
                'bid_adjustment': -0.15,
                'enabled': True
            }
        ]
        
        validation_result = self.optimizer.validate_optimization_rules(valid_rules)
        
        self.assertTrue(validation_result.get('valid', True))
        self.assertEqual(len(validation_result.get('errors', [])), 0)
    
    def test_optimization_rules_validation_invalid(self):
        """Test optimization rules validation with invalid rules."""
        invalid_rules = [
            {
                'name': '',  # Missing name
                'condition': 'ctr < 1.0',
                'action': 'increase_bid',
                'bid_adjustment': 2.0,  # Too high
                'enabled': True
            },
            {
                'name': 'Invalid Action Rule',
                'condition': 'cpa > 10.0',
                'action': 'invalid_action',  # Invalid action
                'bid_adjustment': -0.15,
                'enabled': True
            }
        ]
        
        validation_result = self.optimizer.validate_optimization_rules(invalid_rules)
        
        self.assertFalse(validation_result.get('valid', False))
        errors = validation_result.get('errors', {})
        
        self.assertIn('name', errors)
        self.assertIn('bid_adjustment', errors)
        self.assertIn('action', errors)
    
    def test_apply_optimization_rules(self):
        """Test applying optimization rules."""
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
        
        performance_data = {
            'ctr': 0.8,  # Triggers Low CTR Rule
            'cpa': 12.0,  # Triggers High CPA Rule
            'cpc': 0.50,
        }
        
        applied_rules = self.optimizer.apply_optimization_rules(
            self.campaign,
            rules,
            performance_data
        )
        
        self.assertEqual(len(applied_rules), 2)
        
        # Check Low CTR Rule
        low_ctr_rule = next((rule for rule in applied_rules if rule['name'] == 'Low CTR Rule'), None)
        self.assertIsNotNone(low_ctr_rule)
        self.assertTrue(low_ctr_rule['triggered'])
        self.assertEqual(low_ctr_rule['action'], 'increase_bid')
        
        # Check High CPA Rule
        high_cpa_rule = next((rule for rule in applied_rules if rule['name'] == 'High CPA Rule'), None)
        self.assertIsNotNone(high_cpa_rule)
        self.assertTrue(high_cpa_rule['triggered'])
        self.assertEqual(high_cpa_rule['action'], 'decrease_bid')
    
    def test_optimization_performance_tracking(self):
        """Test optimization performance tracking."""
        # Record some optimizations
        optimizations = [
            {
                'type': 'bid_optimization',
                'changes': {'base_bid': 0.50, 'new_bid': 0.60},
                'performance_before': {'ctr': 1.5, 'cpa': 8.0},
                'performance_after': {'ctr': 2.0, 'cpa': 6.0},
                'timestamp': timezone.now()
            },
            {
                'type': 'targeting_optimization',
                'changes': {'excluded_geo': 'CA'},
                'performance_before': {'ctr': 1.5, 'cpa': 8.0},
                'performance_after': {'ctr': 2.2, 'cpa': 5.5},
                'timestamp': timezone.now()
            }
        ]
        
        for opt in optimizations:
            self.optimizer.record_optimization(
                self.campaign,
                opt['type'],
                opt['changes'],
                opt['performance_before'],
                opt['performance_after']
            )
        
        # Get optimization history
        history = self.optimizer.get_optimization_history(self.campaign)
        
        self.assertEqual(len(history), 2)
        
        # Get performance analysis
        analysis = self.optimizer.analyze_optimization_performance(self.campaign)
        
        self.assertIn('total_optimizations', analysis)
        self.assertIn('average_improvement', analysis)
        self.assertIn('success_rate', analysis)
        self.assertIn('best_performing_type', analysis)
    
    def test_optimization_ab_testing(self):
        """Test A/B testing of optimization strategies."""
        strategies = [
            {
                'name': 'Aggressive',
                'bid_adjustment': 0.3,
                'targeting_expansion': True,
                'budget_allocation': 0.6
            },
            {
                'name': 'Conservative',
                'bid_adjustment': 0.1,
                'targeting_expansion': False,
                'budget_allocation': 0.4
            }
        ]
        
        # Start A/B test
        ab_test = self.optimizer.start_optimization_ab_test(
            self.campaign,
            strategies,
            duration_days=7
        )
        
        self.assertIn('test_id', ab_test)
        self.assertIn('strategies', ab_test)
        self.assertEqual(len(ab_test['strategies']), 2)
        self.assertIn('duration_days', ab_test)
        
        # Simulate test results
        test_results = {
            'Aggressive': {
                'impressions': 5000,
                'clicks': 150,
                'conversions': 15,
                'spend': 75.00,
                'ctr': 3.0,
                'cpa': 5.0
            },
            'Conservative': {
                'impressions': 5000,
                'clicks': 100,
                'conversions': 12,
                'spend': 50.00,
                'ctr': 2.0,
                'cpa': 4.17
            }
        }
        
        # Complete A/B test
        results = self.optimizer.complete_optimization_ab_test(
            ab_test['test_id'],
            test_results
        )
        
        self.assertIn('winner', results)
        self.assertIn('confidence', results)
        self.assertIn('recommendations', results)
    
    def test_optimization_rollback(self):
        """Test optimization rollback functionality."""
        # Get original bid configuration
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
                'min_clicks': 10,
                'min_conversions': 2
            },
            'enabled': True
        }
        
        scheduled_optimization = self.optimizer.schedule_optimization(
            self.campaign,
            schedule
        )
        
        self.assertIn('schedule_id', scheduled_optimization)
        self.assertEqual(scheduled_optimization['frequency'], 'hourly')
        self.assertIn('next_run', scheduled_optimization)
        self.assertIn('conditions', scheduled_optimization)
    
    def test_ml_optimization_integration(self):
        """Test ML optimization integration."""
        # Enable ML optimization
        self.campaign.ml_optimization_enabled = True
        self.campaign.save()
        
        # Get ML recommendations
        ml_recommendations = self.optimizer.get_ml_recommendations(self.campaign)
        
        self.assertIn('bid_recommendations', ml_recommendations)
        self.assertIn('targeting_recommendations', ml_recommendations)
        self.assertIn('budget_recommendations', ml_recommendations)
        self.assertIn('confidence_scores', ml_recommendations)
        
        # Apply ML recommendations
        ml_result = self.optimizer.apply_ml_recommendations(
            self.campaign,
            ml_recommendations
        )
        
        self.assertTrue(ml_result.get('success', False))
        self.assertIn('applied_recommendations', ml_result)
        self.assertIn('expected_improvement', ml_result)
    
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
    
    def test_optimization_budget_constraints(self):
        """Test optimization with budget constraints."""
        # Set low budget
        self.campaign.budget_limit = Decimal('100.00')
        self.campaign.daily_budget = Decimal('10.00')
        self.campaign.save()
        
        performance_data = {
            'impressions': 10000,
            'clicks': 50,  # Low CTR
            'conversions': 5,
            'spend': 50.00,  # 50% of budget used
            'ctr': 0.5,
            'cpc': 1.00,
            'cpa': 10.00,
            'conversion_rate': 10.0,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        
        # Should consider budget constraints
        self.assertIn('budget_constraints', optimization_result)
        self.assertIn('recommended_daily_budget', optimization_result)
    
    def test_optimization_performance_thresholds(self):
        """Test optimization performance thresholds."""
        # Set performance thresholds
        thresholds = {
            'min_improvement': 5.0,  # Minimum 5% improvement
            'max_bid_adjustment': 0.5,  # Maximum 50% bid adjustment
            'min_confidence': 0.8  # Minimum 80% confidence
        }
        
        performance_data = {
            'impressions': 10000,
            'clicks': 100,  # Low CTR
            'conversions': 10,
            'spend': 100.00,
            'ctr': 1.0,
            'cpc': 1.00,
            'cpa': 10.00,
            'conversion_rate': 10.0,
        }
        
        optimization_result = self.optimizer.optimize_bids(
            self.campaign,
            performance_data,
            thresholds=thresholds
        )
        
        self.assertTrue(optimization_result.get('success', False))
        
        # Should respect thresholds
        bid_adjustments = optimization_result.get('bid_adjustments', [])
        for adjustment in bid_adjustments:
            adjustment_ratio = (adjustment.get('new_bid', 0) - adjustment.get('old_bid', 0)) / adjustment.get('old_bid', 1)
            self.assertLessEqual(abs(adjustment_ratio), thresholds['max_bid_adjustment'])
    
    def test_optimization_multi_campaign(self):
        """Test optimization across multiple campaigns."""
        # Create additional campaigns
        campaigns = [self.campaign]
        
        for i in range(2):
            data = self.valid_campaign_data.copy()
            data['name'] = f'Campaign {i+1}'
            campaign = self.campaign_service.create_campaign(self.advertiser, data)
            self.campaign_service.start_campaign(campaign)
            campaigns.append(campaign)
        
        # Optimize all campaigns
        optimization_results = self.optimizer.optimize_multiple_campaigns(
            campaigns,
            optimization_type='bid_optimization'
        )
        
        self.assertEqual(len(optimization_results), 3)
        
        for result in optimization_results:
            self.assertIn('campaign_id', result)
            self.assertIn('success', result)
            self.assertIn('optimizations_applied', result)
    
    def test_optimization_real_time_updates(self):
        """Test real-time optimization updates."""
        # Enable real-time optimization
        self.campaign.real_time_optimization = True
        self.campaign.save()
        
        # Simulate real-time performance data
        real_time_data = {
            'current_hour': {
                'impressions': 1000,
                'clicks': 15,
                'conversions': 2,
                'spend': 15.00
            },
            'trend': 'declining',  # Performance declining
            'urgency': 'high'
        }
        
        optimization_result = self.optimizer.optimize_real_time(
            self.campaign,
            real_time_data
        )
        
        self.assertTrue(optimization_result.get('success', False))
        self.assertIn('real_time_adjustments', optimization_result)
        self.assertIn('urgency_level', optimization_result)
    
    def test_optimization_export_import(self):
        """Test optimization configuration export/import."""
        # Create optimization configuration
        config = {
            'bid_optimization': {
                'enabled': True,
                'rules': [
                    {
                        'name': 'Low CTR Rule',
                        'condition': 'ctr < 1.0',
                        'action': 'increase_bid',
                        'bid_adjustment': 0.2
                    }
                ],
                'thresholds': {
                    'min_improvement': 5.0,
                    'max_bid_adjustment': 0.5
                }
            },
            'targeting_optimization': {
                'enabled': True,
                'auto_expand': True,
                'exclude_underperforming': True
            }
        }
        
        # Export configuration
        exported_config = self.optimizer.export_optimization_config(
            self.campaign
        )
        
        self.assertIn('bid_optimization', exported_config)
        self.assertIn('targeting_optimization', exported_config)
        
        # Import configuration
        import_result = self.optimizer.import_optimization_config(
            self.campaign,
            config
        )
        
        self.assertTrue(import_result.get('success', False))
        self.assertIn('imported_rules', import_result)
        self.assertIn('updated_settings', import_result)

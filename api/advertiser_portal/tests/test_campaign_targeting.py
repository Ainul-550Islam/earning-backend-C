"""
Test Campaign Targeting Service

Comprehensive tests for campaign targeting functionality
including audience targeting, geographic targeting, and optimization.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign, CampaignTargeting
from ..models.advertiser import Advertiser
try:
    from ..services import CampaignService
except ImportError:
    CampaignService = None
from ..serializers import CampaignTargetingSerializer

User = get_user_model()


class CampaignTargetingServiceTestCase(APITestCase):
    """Test cases for campaign targeting service."""
    
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
        
        self.campaign_service = CampaignService()
    
    def test_create_campaign_targeting(self):
        """Test creating campaign targeting."""
        targeting_data = {
            'campaign': self.campaign,
            'targeting_type': 'geographic',
            'targeting_criteria': {
                'countries': ['US', 'CA', 'UK'],
                'regions': ['California', 'New York', 'Ontario'],
                'cities': ['Los Angeles', 'New York City', 'Toronto'],
                'zip_codes': ['90210', '10001', 'M5V 2T6'],
                'radius_targeting': {
                    'latitude': 40.7128,
                    'longitude': -74.0060,
                    'radius': 50,
                    'radius_unit': 'miles'
                }
            },
            'is_active': True
        }
        
        targeting = CampaignTargeting.objects.create(**targeting_data)
        
        self.assertEqual(targeting.campaign, self.campaign)
        self.assertEqual(targeting.targeting_type, 'geographic')
        self.assertIn('US', targeting.targeting_criteria['countries'])
        self.assertIn('California', targeting.targeting_criteria['regions'])
        self.assertTrue(targeting.is_active)
    
    def test_update_campaign_targeting(self):
        """Test updating campaign targeting."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='demographic',
            targeting_criteria={
                'age_range': {'min': 18, 'max': 65},
                'gender': ['male', 'female'],
                'income': ['medium', 'high'],
                'education': ['college', 'graduate']
            },
            is_active=True
        )
        
        # Update targeting
        targeting.targeting_criteria['age_range'] = {'min': 25, 'max': 55}
        targeting.targeting_criteria['income'] = ['high']
        targeting.is_active = False
        targeting.save()
        
        targeting.refresh_from_db()
        self.assertEqual(targeting.targeting_criteria['age_range']['min'], 25)
        self.assertEqual(targeting.targeting_criteria['age_range']['max'], 55)
        self.assertEqual(targeting.targeting_criteria['income'], ['high'])
        self.assertFalse(targeting.is_active)
    
    def test_targeting_validation(self):
        """Test targeting validation."""
        # Test invalid targeting type
        with self.assertRaises(Exception):
            CampaignTargeting.objects.create(
                campaign=self.campaign,
                targeting_type='invalid',
                targeting_criteria={}
            )
        
        # Test invalid age range
        with self.assertRaises(Exception):
            CampaignTargeting.objects.create(
                campaign=self.campaign,
                targeting_type='demographic',
                targeting_criteria={
                    'age_range': {'min': 65, 'max': 18}  # min > max
                }
            )
    
    def test_geographic_targeting(self):
        """Test geographic targeting functionality."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='geographic',
            targeting_criteria={
                'countries': ['US', 'CA'],
                'regions': ['California', 'New York'],
                'cities': ['Los Angeles', 'New York City'],
                'exclude_regions': ['Alaska', 'Hawaii']
            },
            is_active=True
        )
        
        # Test targeting logic
        test_location = {
            'country': 'US',
            'region': 'California',
            'city': 'Los Angeles'
        }
        
        is_targeted = self.campaign_service.check_geographic_targeting(targeting, test_location)
        self.assertTrue(is_targeted)
        
        # Test excluded location
        excluded_location = {
            'country': 'US',
            'region': 'Alaska',
            'city': 'Anchorage'
        }
        
        is_targeted = self.campaign_service.check_geographic_targeting(targeting, excluded_location)
        self.assertFalse(is_targeted)
    
    def test_demographic_targeting(self):
        """Test demographic targeting functionality."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='demographic',
            targeting_criteria={
                'age_range': {'min': 25, 'max': 45},
                'gender': ['male', 'female'],
                'income': ['medium', 'high'],
                'education': ['college', 'graduate'],
                'interests': ['technology', 'finance', 'travel']
            },
            is_active=True
        )
        
        # Test targeting logic
        test_user = {
            'age': 30,
            'gender': 'male',
            'income': 'high',
            'education': 'college',
            'interests': ['technology', 'sports']
        }
        
        is_targeted = self.campaign_service.check_demographic_targeting(targeting, test_user)
        self.assertTrue(is_targeted)
        
        # Test non-targeted user
        non_targeted_user = {
            'age': 20,  # Outside age range
            'gender': 'male',
            'income': 'medium',
            'education': 'high_school',
            'interests': ['gaming']
        }
        
        is_targeted = self.campaign_service.check_demographic_targeting(targeting, non_targeted_user)
        self.assertFalse(is_targeted)
    
    def test_device_targeting(self):
        """Test device targeting functionality."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='device',
            targeting_criteria={
                'device_types': ['desktop', 'mobile'],
                'operating_systems': ['Windows', 'iOS', 'Android'],
                'browsers': ['Chrome', 'Safari', 'Firefox'],
                'screen_resolutions': ['1920x1080', '1366x768', '375x667']
            },
            is_active=True
        )
        
        # Test targeting logic
        test_device = {
            'device_type': 'desktop',
            'os': 'Windows',
            'browser': 'Chrome',
            'screen_resolution': '1920x1080'
        }
        
        is_targeted = self.campaign_service.check_device_targeting(targeting, test_device)
        self.assertTrue(is_targeted)
        
        # Test non-targeted device
        non_targeted_device = {
            'device_type': 'tablet',  # Not in targeting
            'os': 'iPadOS',
            'browser': 'Safari',
            'screen_resolution': '1024x768'
        }
        
        is_targeted = self.campaign_service.check_device_targeting(targeting, non_targeted_device)
        self.assertFalse(is_targeted)
    
    def test_time_targeting(self):
        """Test time-based targeting functionality."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='time',
            targeting_criteria={
                'days_of_week': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                'hours_of_day': {'start': 9, 'end': 17},
                'time_zones': ['EST', 'CST', 'MST', 'PST'],
                'holidays': ['Christmas', 'New Year', 'Thanksgiving'],
                'seasonal_adjustments': {
                    'summer': {'bid_multiplier': 1.2},
                    'winter': {'bid_multiplier': 0.8}
                }
            },
            is_active=True
        )
        
        # Test targeting logic
        test_time = {
            'day_of_week': 'Wednesday',
            'hour': 14,
            'time_zone': 'EST',
            'is_holiday': False,
            'season': 'summer'
        }
        
        is_targeted = self.campaign_service.check_time_targeting(targeting, test_time)
        self.assertTrue(is_targeted)
        
        # Test non-targeted time
        non_targeted_time = {
            'day_of_week': 'Saturday',  # Weekend
            'hour': 20,
            'time_zone': 'EST',
            'is_holiday': False,
            'season': 'winter'
        }
        
        is_targeted = self.campaign_service.check_time_targeting(targeting, non_targeted_time)
        self.assertFalse(is_targeted)
    
    def test_behavioral_targeting(self):
        """Test behavioral targeting functionality."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='behavioral',
            targeting_criteria={
                'purchase_history': {
                    'categories': ['electronics', 'fashion'],
                    'price_range': {'min': 50, 'max': 500},
                    'frequency': 'monthly'
                },
                'browsing_behavior': {
                    'visited_sites': ['amazon.com', 'ebay.com'],
                    'search_queries': ['laptop', 'smartphone'],
                    'time_on_site': {'min': 30, 'max': 300}
                },
                'engagement_level': ['high', 'medium'],
                'loyalty_status': ['new', 'returning']
            },
            is_active=True
        )
        
        # Test targeting logic
        test_behavior = {
            'purchase_history': {
                'categories': ['electronics'],
                'avg_price': 200,
                'frequency': 'monthly'
            },
            'browsing_behavior': {
                'visited_sites': ['amazon.com'],
                'search_queries': ['laptop'],
                'avg_time_on_site': 120
            },
            'engagement_level': 'high',
            'loyalty_status': 'returning'
        }
        
        is_targeted = self.campaign_service.check_behavioral_targeting(targeting, test_behavior)
        self.assertTrue(is_targeted)
        
        # Test non-targeted behavior
        non_targeted_behavior = {
            'purchase_history': {
                'categories': ['books'],
                'avg_price': 20,
                'frequency': 'yearly'
            },
            'browsing_behavior': {
                'visited_sites': ['wikipedia.org'],
                'search_queries': ['history'],
                'avg_time_on_site': 10
            },
            'engagement_level': 'low',
            'loyalty_status': 'new'
        }
        
        is_targeted = self.campaign_service.check_behavioral_targeting(targeting, non_targeted_behavior)
        self.assertFalse(is_targeted)
    
    def test_targeting_optimization(self):
        """Test targeting optimization."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='geographic',
            targeting_criteria={
                'countries': ['US', 'CA', 'UK'],
                'regions': ['California', 'New York', 'Ontario']
            },
            is_active=True
        )
        
        # Simulate performance data
        performance_data = {
            'US': {'impressions': 1000, 'conversions': 10, 'ctr': 0.01},
            'CA': {'impressions': 500, 'conversions': 8, 'ctr': 0.016},
            'UK': {'impressions': 300, 'conversions': 2, 'ctr': 0.0067}
        }
        
        # Optimize targeting
        optimization_result = self.campaign_service.optimize_targeting(targeting, performance_data)
        
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommendations', optimization_result)
        self.assertIn('performance_analysis', optimization_result)
    
    def test_targeting_audience_size_estimation(self):
        """Test audience size estimation."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='demographic',
            targeting_criteria={
                'age_range': {'min': 25, 'max': 45},
                'gender': ['male', 'female'],
                'income': ['medium', 'high'],
                'education': ['college', 'graduate']
            },
            is_active=True
        )
        
        # Estimate audience size
        audience_size = self.campaign_service.estimate_targeting_audience_size(targeting)
        
        self.assertIsNotNone(audience_size)
        self.assertIn('estimated_size', audience_size)
        self.assertIn('confidence_level', audience_size)
    
    def test_targeting_combination_logic(self):
        """Test targeting combination logic (AND/OR)."""
        # Create multiple targeting rules
        geographic_targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA']},
            is_active=True
        )
        
        demographic_targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='demographic',
            targeting_criteria={'age_range': {'min': 25, 'max': 45}},
            is_active=True
        )
        
        device_targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='device',
            targeting_criteria={'device_types': ['desktop', 'mobile']},
            is_active=True
        )
        
        # Test combination logic
        test_user = {
            'location': {'country': 'US', 'region': 'California'},
            'demographics': {'age': 30, 'gender': 'male'},
            'device': {'device_type': 'desktop', 'os': 'Windows'}
        }
        
        # Test AND logic (user must match all targeting)
        is_targeted_and = self.campaign_service.check_combined_targeting(
            [geographic_targeting, demographic_targeting, device_targeting],
            test_user,
            logic='AND'
        )
        self.assertTrue(is_targeted_and)
        
        # Test OR logic (user must match at least one targeting)
        is_targeted_or = self.campaign_service.check_combined_targeting(
            [geographic_targeting, demographic_targeting, device_targeting],
            test_user,
            logic='OR'
        )
        self.assertTrue(is_targeted_or)
    
    def test_targeting_exclusion_rules(self):
        """Test targeting exclusion rules."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='demographic',
            targeting_criteria={
                'age_range': {'min': 18, 'max': 65},
                'income': ['medium', 'high']
            },
            exclusion_criteria={
                'age_range': {'min': 13, 'max': 17},  # Exclude minors
                'income': ['low']  # Exclude low income
            },
            is_active=True
        )
        
        # Test user that matches inclusion but not exclusion
        test_user = {
            'age': 30,
            'income': 'high'
        }
        
        is_targeted = self.campaign_service.check_targeting_with_exclusions(targeting, test_user)
        self.assertTrue(is_targeted)
        
        # Test user that matches exclusion
        excluded_user = {
            'age': 15,  # In exclusion range
            'income': 'medium'
        }
        
        is_targeted = self.campaign_service.check_targeting_with_exclusions(targeting, excluded_user)
        self.assertFalse(is_targeted)
    
    def test_targeting_performance_tracking(self):
        """Test targeting performance tracking."""
        targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA']},
            is_active=True
        )
        
        # Track performance
        performance = targeting.get_performance_metrics()
        
        self.assertIn('impressions', performance)
        self.assertIn('clicks', performance)
        self.assertIn('conversions', performance)
        self.assertIn('ctr', performance)
        self.assertIn('conversion_rate', performance)
        self.assertIn('cost', performance)


class CampaignTargetingSerializerTestCase(APITestCase):
    """Test cases for CampaignTargetingSerializer."""
    
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
        
        self.targeting = CampaignTargeting.objects.create(
            campaign=self.campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA']},
            is_active=True
        )
    
    def test_targeting_serialization(self):
        """Test targeting serialization."""
        serializer = CampaignTargetingSerializer(self.targeting)
        
        data = serializer.data
        
        self.assertEqual(data['campaign'], self.campaign.id)
        self.assertEqual(data['targeting_type'], 'geographic')
        self.assertIn('countries', data['targeting_criteria'])
        self.assertTrue(data['is_active'])
    
    def test_targeting_deserialization(self):
        """Test targeting deserialization."""
        data = {
            'campaign': self.campaign.id,
            'targeting_type': 'demographic',
            'targeting_criteria': {
                'age_range': {'min': 25, 'max': 45},
                'gender': ['male', 'female'],
                'income': ['medium', 'high']
            },
            'exclusion_criteria': {
                'age_range': {'min': 13, 'max': 17}
            },
            'is_active': True
        }
        
        serializer = CampaignTargetingSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        targeting = serializer.save()
        
        self.assertEqual(targeting.targeting_type, 'demographic')
        self.assertEqual(targeting.targeting_criteria['age_range']['min'], 25)
        self.assertEqual(targeting.targeting_criteria['age_range']['max'], 45)
        self.assertEqual(targeting.exclusion_criteria['age_range']['min'], 13)
        self.assertTrue(targeting.is_active)
    
    def test_targeting_validation(self):
        """Test targeting validation in serializer."""
        # Test invalid targeting type
        data = {
            'campaign': self.campaign.id,
            'targeting_type': 'invalid',
            'targeting_criteria': {}
        }
        
        serializer = CampaignTargetingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('targeting_type', serializer.errors)
        
        # Test invalid age range
        data = {
            'campaign': self.campaign.id,
            'targeting_type': 'demographic',
            'targeting_criteria': {
                'age_range': {'min': 65, 'max': 18}  # min > max
            }
        }
        
        serializer = CampaignTargetingSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('targeting_criteria', serializer.errors)
    
    def test_targeting_update_serialization(self):
        """Test targeting update serialization."""
        data = {
            'targeting_criteria': {
                'countries': ['US', 'CA', 'UK'],
                'regions': ['California', 'New York', 'Ontario']
            },
            'is_active': False
        }
        
        serializer = CampaignTargetingSerializer(instance=self.targeting, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_targeting = serializer.save()
        
        self.assertIn('UK', updated_targeting.targeting_criteria['countries'])
        self.assertIn('California', updated_targeting.targeting_criteria['regions'])
        self.assertFalse(updated_targeting.is_active)


class CampaignTargetingIntegrationTestCase(APITestCase):
    """Integration tests for campaign targeting."""
    
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
        
        self.campaign_service = CampaignService()
    
    def test_complete_targeting_lifecycle(self):
        """Test complete targeting lifecycle."""
        # 1. Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Targeting Lifecycle Campaign',
            description='Testing targeting lifecycle',
            status='active'
        )
        
        # 2. Create targeting rules
        geographic_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA']},
            is_active=True
        )
        
        demographic_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='demographic',
            targeting_criteria={'age_range': {'min': 25, 'max': 45}},
            is_active=True
        )
        
        # 3. Test targeting logic
        test_user = {
            'location': {'country': 'US', 'region': 'California'},
            'demographics': {'age': 30, 'gender': 'male'},
            'device': {'device_type': 'desktop', 'os': 'Windows'}
        }
        
        # Check if user is targeted
        is_targeted = self.campaign_service.check_combined_targeting(
            [geographic_targeting, demographic_targeting],
            test_user,
            logic='AND'
        )
        
        self.assertTrue(is_targeted)
        
        # 4. Optimize targeting based on performance
        performance_data = {
            'US': {'impressions': 1000, 'conversions': 10, 'ctr': 0.01},
            'CA': {'impressions': 500, 'conversions': 8, 'ctr': 0.016}
        }
        
        optimization_result = self.campaign_service.optimize_targeting(geographic_targeting, performance_data)
        
        # 5. Update targeting based on optimization
        if optimization_result.get('recommendations'):
            # Apply recommendations
            pass
        
        # Verify results
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommendations', optimization_result)
    
    def test_multiple_targeting_combinations(self):
        """Test multiple targeting combinations."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Multi Targeting Campaign',
            description='Testing multiple targeting',
            status='active'
        )
        
        # Create multiple targeting rules
        targeting_rules = []
        
        # Geographic targeting
        geographic_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA', 'UK']},
            is_active=True
        )
        targeting_rules.append(geographic_targeting)
        
        # Demographic targeting
        demographic_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='demographic',
            targeting_criteria={'age_range': {'min': 25, 'max': 45}},
            is_active=True
        )
        targeting_rules.append(demographic_targeting)
        
        # Device targeting
        device_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='device',
            targeting_criteria={'device_types': ['desktop', 'mobile']},
            is_active=True
        )
        targeting_rules.append(device_targeting)
        
        # Time targeting
        time_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='time',
            targeting_criteria={'hours_of_day': {'start': 9, 'end': 17}},
            is_active=True
        )
        targeting_rules.append(time_targeting)
        
        # Test various user profiles
        test_users = [
            {
                'name': 'Perfect Match',
                'location': {'country': 'US'},
                'demographics': {'age': 30},
                'device': {'device_type': 'desktop'},
                'time': {'hour': 14}
            },
            {
                'name': 'Partial Match',
                'location': {'country': 'US'},
                'demographics': {'age': 50},  # Outside age range
                'device': {'device_type': 'desktop'},
                'time': {'hour': 14}
            },
            {
                'name': 'No Match',
                'location': {'country': 'FR'},  # Outside countries
                'demographics': {'age': 30},
                'device': {'device_type': 'desktop'},
                'time': {'hour': 14}
            }
        ]
        
        # Test targeting with different logic
        for user in test_users:
            # AND logic
            is_targeted_and = self.campaign_service.check_combined_targeting(
                targeting_rules, user, logic='AND'
            )
            
            # OR logic
            is_targeted_or = self.campaign_service.check_combined_targeting(
                targeting_rules, user, logic='OR'
            )
            
            # Store results
            user['targeted_and'] = is_targeted_and
            user['targeted_or'] = is_targeted_or
        
        # Verify results
        perfect_match = next(u for u in test_users if u['name'] == 'Perfect Match')
        self.assertTrue(perfect_match['targeted_and'])
        self.assertTrue(perfect_match['targeted_or'])
        
        no_match = next(u for u in test_users if u['name'] == 'No Match')
        self.assertFalse(no_match['targeted_and'])
        self.assertFalse(no_match['targeted_or'])
    
    def test_targeting_budget_integration(self):
        """Test targeting integration with budget management."""
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Targeting Campaign',
            description='Testing budget integration',
            daily_budget=Decimal('100.00'),
            status='active'
        )
        
        # Create targeting with different performance levels
        high_performance_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US']},
            is_active=True
        )
        
        low_performance_targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['FR']},
            is_active=True
        )
        
        # Simulate performance data
        performance_data = {
            'US': {'ctr': 0.02, 'cpa': Decimal('10.00')},
            'FR': {'ctr': 0.005, 'cpa': Decimal('40.00')}
        }
        
        # Optimize targeting based on budget constraints
        optimization_result = self.campaign_service.optimize_targeting_for_budget(
            [high_performance_targeting, low_performance_targeting],
            performance_data,
            campaign.daily_budget
        )
        
        self.assertIsNotNone(optimization_result)
        self.assertIn('recommended_targeting', optimization_result)
        self.assertIn('budget_allocation', optimization_result)
    
    @patch('advertiser_portal.services.campaign.CampaignService.check_combined_targeting')
    def test_targeting_integration(self, mock_check):
        """Test targeting integration."""
        mock_check.return_value = True
        
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Integration Targeting Campaign',
            description='Testing targeting integration',
            status='active'
        )
        
        targeting = CampaignTargeting.objects.create(
            campaign=campaign,
            targeting_type='geographic',
            targeting_criteria={'countries': ['US', 'CA']},
            is_active=True
        )
        
        test_user = {
            'location': {'country': 'US'},
            'demographics': {'age': 30},
            'device': {'device_type': 'desktop'}
        }
        
        # Check targeting
        is_targeted = self.campaign_service.check_combined_targeting([targeting], test_user, logic='AND')
        
        # Verify integration
        mock_check.assert_called_once_with([targeting], test_user, logic='AND')
        self.assertTrue(is_targeted)

"""
Test Conversion Tracking

Comprehensive tests for conversion tracking functionality
including conversion recording, validation, and attribution.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.tracking import Conversion, TrackingPixel, S2SPostback
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.advertiser import Advertiser
try:
    from ..services import ConversionTrackingService
except ImportError:
    ConversionTrackingService = None
try:
    from ..services import TrackingPixelService
except ImportError:
    TrackingPixelService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class ConversionTrackingServiceTestCase(TestCase):
    """Test cases for ConversionTrackingService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.tracking_service = ConversionTrackingService()
        
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
        
        # Create tracking pixel
        self.pixel_service = TrackingPixelService()
        self.pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            {
                'name': 'Test Pixel',
                'pixel_type': 'conversion',
                'description': 'Test conversion pixel',
                'target_url': 'https://example.com/thank-you',
                'status': 'active',
            }
        )
        
        # Create campaign
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Create offer
        self.offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Test Offer',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='active'
        )
        
        self.valid_conversion_data = {
            'conversion_id': 'conv_12345',
            'revenue': Decimal('25.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'pixel': self.pixel,
            'campaign': self.campaign,
            'offer': self.offer,
        }
    
    def test_record_conversion_success(self):
        """Test successful conversion recording."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        self.assertIsInstance(conversion, Conversion)
        self.assertEqual(conversion.advertiser, self.advertiser)
        self.assertEqual(conversion.conversion_id, 'conv_12345')
        self.assertEqual(conversion.revenue, Decimal('25.00'))
        self.assertEqual(conversion.pixel, self.pixel)
        self.assertEqual(conversion.campaign, self.campaign)
        self.assertEqual(conversion.offer, self.offer)
        self.assertEqual(conversion.status, 'pending')
        self.assertIsNotNone(conversion.created_at)
    
    def test_record_conversion_missing_required_fields(self):
        """Test conversion recording with missing required fields."""
        invalid_data = self.valid_conversion_data.copy()
        del invalid_data['conversion_id']  # Missing conversion ID
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(invalid_data)
        
        self.assertIn('Conversion ID is required', str(context.exception))
    
    def test_record_conversion_invalid_revenue(self):
        """Test conversion recording with invalid revenue."""
        invalid_data = self.valid_conversion_data.copy()
        invalid_data['revenue'] = Decimal('-10.00')  # Negative revenue
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(invalid_data)
        
        self.assertIn('Revenue must be positive', str(context.exception))
    
    def test_record_conversion_with_custom_parameters(self):
        """Test conversion recording with custom parameters."""
        conversion_data = self.valid_conversion_data.copy()
        conversion_data['custom_parameters'] = {
            'affiliate_id': '12345',
            'campaign_id': '67890',
            'sub_id': 'abc123',
            'source': 'google_ads'
        }
        
        conversion = self.tracking_service.record_conversion(conversion_data)
        
        self.assertEqual(conversion.custom_parameters['affiliate_id'], '12345')
        self.assertEqual(conversion.custom_parameters['campaign_id'], '67890')
        self.assertEqual(conversion.custom_parameters['sub_id'], 'abc123')
        self.assertEqual(conversion.custom_parameters['source'], 'google_ads')
    
    def test_record_conversion_with_attribution_data(self):
        """Test conversion recording with attribution data."""
        conversion_data = self.valid_conversion_data.copy()
        conversion_data['attribution_data'] = {
            'click_id': 'click_12345',
            'click_time': timezone.now() - timezone.timedelta(hours=2),
            'landing_page': 'https://example.com/landing',
            'source': 'google',
            'medium': 'cpc',
            'campaign_name': 'test_campaign'
        }
        
        conversion = self.tracking_service.record_conversion(conversion_data)
        
        self.assertEqual(conversion.attribution_data['click_id'], 'click_12345')
        self.assertEqual(conversion.attribution_data['source'], 'google')
        self.assertEqual(conversion.attribution_data['medium'], 'cpc')
    
    def test_validate_conversion_success(self):
        """Test successful conversion validation."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        validation_result = self.tracking_service.validate_conversion(conversion)
        
        self.assertTrue(validation_result.get('valid', False))
        self.assertEqual(len(validation_result.get('errors', [])), 0)
    
    def test_validate_conversion_duplicate_id(self):
        """Test conversion validation with duplicate ID."""
        # Record first conversion
        self.tracking_service.record_conversion(self.valid_conversion_data)
        
        # Try to record second conversion with same ID
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(self.valid_conversion_data)
        
        self.assertIn('Conversion ID already exists', str(context.exception))
    
    def test_validate_conversion_invalid_ip(self):
        """Test conversion validation with invalid IP."""
        conversion_data = self.valid_conversion_data.copy()
        conversion_data['ip_address'] = 'invalid_ip_address'
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(conversion_data)
        
        self.assertIn('Invalid IP address', str(context.exception))
    
    def test_validate_conversion_future_timestamp(self):
        """Test conversion validation with future timestamp."""
        conversion_data = self.valid_conversion_data.copy()
        conversion_data['created_at'] = timezone.now() + timezone.timedelta(hours=1)
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(conversion_data)
        
        self.assertIn('Conversion timestamp cannot be in the future', str(context.exception))
    
    def test_approve_conversion_success(self):
        """Test successful conversion approval."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        approved_conversion = self.tracking_service.approve_conversion(conversion)
        
        self.assertEqual(approved_conversion.status, 'approved')
        self.assertIsNotNone(approved_conversion.approved_at)
    
    def test_reject_conversion_success(self):
        """Test successful conversion rejection."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        reason = 'Invalid conversion - suspicious activity'
        rejected_conversion = self.tracking_service.reject_conversion(
            conversion,
            reason
        )
        
        self.assertEqual(rejected_conversion.status, 'rejected')
        self.assertEqual(rejected_conversion.rejection_reason, reason)
        self.assertIsNotNone(rejected_conversion.rejected_at)
    
    def test_reject_conversion_no_reason(self):
        """Test conversion rejection without reason."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.reject_conversion(conversion)
        
        self.assertIn('Rejection reason is required', str(context.exception))
    
    def test_get_conversion_by_id_success(self):
        """Test getting conversion by ID."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        retrieved_conversion = self.tracking_service.get_conversion_by_id(
            self.advertiser,
            'conv_12345'
        )
        
        self.assertEqual(retrieved_conversion.id, conversion.id)
        self.assertEqual(retrieved_conversion.conversion_id, 'conv_12345')
    
    def test_get_conversion_by_id_not_found(self):
        """Test getting conversion by ID when not found."""
        with self.assertRaises(ValueError) as context:
            self.tracking_service.get_conversion_by_id(
                self.advertiser,
                'non_existent_id'
            )
        
        self.assertIn('Conversion not found', str(context.exception))
    
    def test_search_conversions(self):
        """Test conversion search functionality."""
        # Create multiple conversions
        for i in range(5):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal(str(10.00 + i))
            self.tracking_service.record_conversion(data)
        
        # Search by conversion ID
        results = self.tracking_service.search_conversions(
            self.advertiser,
            'conv_1'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].conversion_id, 'conv_1')
    
    def test_get_conversions_by_status(self):
        """Test getting conversions by status."""
        # Create conversions with different statuses
        statuses = ['pending', 'approved', 'rejected']
        
        for status in statuses:
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{status}'
            conversion = self.tracking_service.record_conversion(data)
            
            if status == 'approved':
                self.tracking_service.approve_conversion(conversion)
            elif status == 'rejected':
                self.tracking_service.reject_conversion(conversion, f'Test rejection for {status}')
        
        # Get conversions by status
        pending_conversions = self.tracking_service.get_conversions_by_status(
            self.advertiser,
            'pending'
        )
        approved_conversions = self.tracking_service.get_conversions_by_status(
            self.advertiser,
            'approved'
        )
        rejected_conversions = self.tracking_service.get_conversions_by_status(
            self.advertiser,
            'rejected'
        )
        
        self.assertEqual(len(pending_conversions), 1)
        self.assertEqual(len(approved_conversions), 1)
        self.assertEqual(len(rejected_conversions), 1)
    
    def test_get_conversion_analytics_success(self):
        """Test getting conversion analytics."""
        # Create conversions
        for i in range(10):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal(str(10.00 + i))
            data['custom_parameters'] = {
                'affiliate_id': str(i % 3),  # 0, 1, 2 repeating
                'source': 'google' if i % 2 == 0 else 'facebook'
            }
            
            conversion = self.tracking_service.record_conversion(data)
            
            # Approve some conversions
            if i < 7:
                self.tracking_service.approve_conversion(conversion)
        
        # Get analytics for last 7 days
        analytics = self.tracking_service.get_conversion_analytics(
            self.advertiser,
            days=7
        )
        
        self.assertIn('total_conversions', analytics)
        self.assertIn('approved_conversions', analytics)
        self.assertIn('rejected_conversions', analytics)
        self.assertIn('pending_conversions', analytics)
        self.assertIn('total_revenue', analytics)
        self.assertIn('average_revenue', analytics)
        self.assertIn('conversion_rate', analytics)
        self.assertIn('daily_breakdown', analytics)
        self.assertIn('affiliate_breakdown', analytics)
        self.assertIn('source_breakdown', analytics)
        
        # Check totals
        self.assertEqual(analytics['total_conversions'], 10)
        self.assertEqual(analytics['approved_conversions'], 7)
    
    def test_get_conversion_analytics_no_data(self):
        """Test getting conversion analytics with no data."""
        analytics = self.tracking_service.get_conversion_analytics(
            self.advertiser,
            days=7
        )
        
        self.assertEqual(analytics['total_conversions'], 0)
        self.assertEqual(analytics['approved_conversions'], 0)
        self.assertEqual(analytics['rejected_conversions'], 0)
        self.assertEqual(analytics['pending_conversions'], 0)
        self.assertEqual(analytics['total_revenue'], Decimal('0.00'))
    
    def test_get_conversion_performance_trends(self):
        """Test getting conversion performance trends."""
        # Create conversions over different days
        for i in range(7):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal('10.00')
            data['created_at'] = timezone.now() - timezone.timedelta(days=i)
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        trends = self.tracking_service.get_conversion_performance_trends(
            self.advertiser,
            days=7
        )
        
        self.assertIn('daily_trends', trends)
        self.assertIn('growth_rate', trends)
        self.assertIn('revenue_trend', trends)
        self.assertIn('conversion_volume_trend', trends)
        self.assertIn('forecast', trends)
    
    def test_batch_approve_conversions(self):
        """Test batch approval of conversions."""
        # Create conversions
        conversions = []
        for i in range(5):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            conversion = self.tracking_service.record_conversion(data)
            conversions.append(conversion)
        
        # Batch approve
        approved_conversions = self.tracking_service.batch_approve_conversions(
            conversions
        )
        
        self.assertEqual(len(approved_conversions), 5)
        
        for conversion in approved_conversions:
            self.assertEqual(conversion.status, 'approved')
    
    def test_batch_reject_conversions(self):
        """Test batch rejection of conversions."""
        # Create conversions
        conversions = []
        for i in range(5):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            conversion = self.tracking_service.record_conversion(data)
            conversions.append(conversion)
        
        # Batch reject
        rejected_conversions = self.tracking_service.batch_reject_conversions(
            conversions,
            'Batch rejection - test'
        )
        
        self.assertEqual(len(rejected_conversions), 5)
        
        for conversion in rejected_conversions:
            self.assertEqual(conversion.status, 'rejected')
            self.assertEqual(conversion.rejection_reason, 'Batch rejection - test')
    
    def test_export_conversion_data(self):
        """Test exporting conversion data."""
        # Create conversions
        for i in range(5):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal(str(10.00 + i))
            data['custom_parameters'] = {
                'affiliate_id': str(i),
                'campaign_id': str(i * 10)
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        # Export data
        export_data = self.tracking_service.export_conversion_data(
            self.advertiser,
            days=30
        )
        
        self.assertIn('conversions', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('performance', export_data)
        self.assertIn('export_date', export_data)
        
        # Check conversions count
        self.assertEqual(len(export_data['conversions']), 5)
    
    def test_get_conversion_statistics(self):
        """Test getting conversion statistics."""
        # Create conversions
        for i in range(20):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal('10.00')
            
            conversion = self.tracking_service.record_conversion(data)
            
            # Approve 15, reject 3, leave 2 pending
            if i < 15:
                self.tracking_service.approve_conversion(conversion)
            elif i < 18:
                self.tracking_service.reject_conversion(conversion, 'Test rejection')
        
        stats = self.tracking_service.get_conversion_statistics(self.advertiser)
        
        self.assertIn('total_conversions', stats)
        self.assertIn('approved_conversions', stats)
        self.assertIn('rejected_conversions', stats)
        self.assertIn('pending_conversions', stats)
        self.assertIn('approval_rate', stats)
        self.assertIn('rejection_rate', stats)
        self.assertIn('total_revenue', stats)
        self.assertIn('average_revenue', stats)
        
        # Check totals
        self.assertEqual(stats['total_conversions'], 20)
        self.assertEqual(stats['approved_conversions'], 15)
        self.assertEqual(stats['rejected_conversions'], 3)
        self.assertEqual(stats['pending_conversions'], 2)
        self.assertEqual(stats['approval_rate'], 75.0)
    
    def test_get_conversion_attribution_analysis(self):
        """Test getting conversion attribution analysis."""
        # Create conversions with attribution data
        sources = ['google', 'facebook', 'email', 'direct']
        for i, source in enumerate(sources):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['attribution_data'] = {
                'source': source,
                'medium': 'cpc' if source in ['google', 'facebook'] else 'organic',
                'campaign_name': f'campaign_{source}',
                'click_time': timezone.now() - timezone.timedelta(hours=i+1)
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        attribution_analysis = self.tracking_service.get_conversion_attribution_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('source_breakdown', attribution_analysis)
        self.assertIn('medium_breakdown', attribution_analysis)
        self.assertIn('campaign_breakdown', attribution_analysis)
        self.assertIn('attribution_window', attribution_analysis)
        self.assertIn('path_analysis', attribution_analysis)
        
        # Check source breakdown
        source_breakdown = attribution_analysis['source_breakdown']
        self.assertEqual(len(source_breakdown), 4)
        self.assertIn('google', source_breakdown)
        self.assertIn('facebook', source_breakdown)
    
    def test_get_conversion_funnel_analysis(self):
        """Test getting conversion funnel analysis."""
        # Create conversions with different stages
        funnel_stages = ['awareness', 'interest', 'consideration', 'conversion']
        for i, stage in enumerate(funnel_stages):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{stage}'
            data['custom_parameters'] = {
                'funnel_stage': stage,
                'landing_page': f'/page_{stage}'
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        funnel_analysis = self.tracking_service.get_conversion_funnel_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('stages', funnel_analysis)
        self.assertIn('conversion_rates', funnel_analysis)
        self.assertIn('drop_off_points', funnel_analysis)
        self.assertIn('optimization_opportunities', funnel_analysis)
        
        # Check stages
        stages = funnel_analysis['stages']
        self.assertEqual(len(stages), 4)
        self.assertIn('awareness', stages)
        self.assertIn('conversion', stages)
    
    def test_validate_conversion_attribution_window(self):
        """Test conversion attribution window validation."""
        # Create conversion with old click time
        conversion_data = self.valid_conversion_data.copy()
        conversion_data['attribution_data'] = {
            'click_time': timezone.now() - timezone.timedelta(days=35)  # 35 days ago
        }
        
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(conversion_data)
        
        self.assertIn('Attribution window exceeded', str(context.exception))
    
    def test_get_conversion_revenue_attribution(self):
        """Test getting conversion revenue attribution."""
        # Create conversions with different revenue amounts and sources
        for i in range(10):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal(str(5.00 + i * 5))  # $5, $10, $15, ..., $50
            data['custom_parameters'] = {
                'affiliate_id': str(i % 3),  # 3 affiliates
                'source': 'google' if i % 2 == 0 else 'facebook'
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        revenue_attribution = self.tracking_service.get_conversion_revenue_attribution(
            self.advertiser,
            days=7
        )
        
        self.assertIn('total_revenue', revenue_attribution)
        self.assertIn('affiliate_breakdown', revenue_attribution)
        self.assertIn('source_breakdown', revenue_attribution)
        self.assertIn('revenue_trends', revenue_attribution)
        
        # Check total revenue
        total_revenue = revenue_attribution['total_revenue']
        expected_total = sum(Decimal(str(5.00 + i * 5)) for i in range(10))
        self.assertEqual(total_revenue, expected_total)
    
    def test_get_conversion_quality_metrics(self):
        """Test getting conversion quality metrics."""
        # Create conversions with different quality indicators
        for i in range(10):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal('10.00')
            data['custom_parameters'] = {
                'session_duration': i * 60,  # 0, 60, 120, ..., 540 seconds
                'pages_visited': i % 5 + 1,  # 1-5 pages
                'device_type': 'mobile' if i % 2 == 0 else 'desktop'
            }
            
            conversion = self.tracking_service.record_conversion(data)
            
            # Approve based on quality
            if i > 2:  # Approve higher quality conversions
                self.tracking_service.approve_conversion(conversion)
            else:
                self.tracking_service.reject_conversion(conversion, 'Low quality')
        
        quality_metrics = self.tracking_service.get_conversion_quality_metrics(
            self.advertiser,
            days=7
        )
        
        self.assertIn('quality_score', quality_metrics)
        self.assertIn('approval_rate_by_quality', quality_metrics)
        self.assertIn('device_quality_breakdown', quality_metrics)
        self.assertIn('session_quality_analysis', quality_metrics)
    
    def test_get_conversion_geographic_analysis(self):
        """Test getting conversion geographic analysis."""
        # Create conversions from different countries
        countries = ['US', 'CA', 'UK', 'DE', 'FR']
        for i, country in enumerate(countries):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{country}'
            data['custom_parameters'] = {
                'country': country,
                'city': f'City_{country}',
                'region': f'Region_{country}'
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        geographic_analysis = self.tracking_service.get_conversion_geographic_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('country_breakdown', geographic_analysis)
        self.assertIn('regional_breakdown', geographic_analysis)
        self.assertIn('city_breakdown', geographic_analysis)
        self.assertIn('geographic_trends', geographic_analysis)
        
        # Check country breakdown
        country_breakdown = geographic_analysis['country_breakdown']
        self.assertEqual(len(country_breakdown), 5)
        self.assertIn('US', country_breakdown)
        self.assertIn('CA', country_breakdown)
    
    def test_get_conversion_device_analysis(self):
        """Test getting conversion device analysis."""
        # Create conversions from different devices
        devices = ['desktop', 'mobile', 'tablet']
        for i, device in enumerate(devices):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{device}'
            data['custom_parameters'] = {
                'device_type': device,
                'os': 'Windows' if device == 'desktop' else ('iOS' if device == 'mobile' else 'Android')
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        device_analysis = self.tracking_service.get_conversion_device_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('device_breakdown', device_analysis)
        self.assertIn('os_breakdown', device_analysis)
        self.assertIn('browser_breakdown', device_analysis)
        self.assertIn('device_performance', device_analysis)
        
        # Check device breakdown
        device_breakdown = device_analysis['device_breakdown']
        self.assertEqual(len(device_breakdown), 3)
        self.assertIn('desktop', device_breakdown)
        self.assertIn('mobile', device_breakdown)
    
    def test_get_conversion_time_analysis(self):
        """Test getting conversion time analysis."""
        # Create conversions at different times
        for i in range(24):  # One conversion per hour
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_hour_{i}'
            data['created_at'] = timezone.now().replace(hour=i, minute=0, second=0, microsecond=0)
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        time_analysis = self.tracking_service.get_conversion_time_analysis(
            self.advertiser,
            days=1
        )
        
        self.assertIn('hourly_breakdown', time_analysis)
        self.assertIn('daily_breakdown', time_analysis)
        self.assertIn('weekly_breakdown', time_analysis)
        self.assertIn('peak_hours', time_analysis)
        self.assertIn('conversion_patterns', time_analysis)
        
        # Check hourly breakdown
        hourly_breakdown = time_analysis['hourly_breakdown']
        self.assertEqual(len(hourly_breakdown), 24)
    
    @patch('api.advertiser_portal.services.tracking.ConversionTrackingService.send_notification')
    def test_send_conversion_notification(self, mock_send_notification):
        """Test sending conversion notification."""
        conversion = self.tracking_service.record_conversion(
            self.valid_conversion_data
        )
        
        # Send notification
        self.tracking_service.send_conversion_notification(
            conversion,
            'conversion_approved',
            'Your conversion has been approved'
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'conversion_approved')
            self.assertIn('approved', notification_data['message'])
    
    def test_get_conversion_recommendations(self):
        """Test getting conversion recommendations."""
        # Create conversions
        for i in range(10):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal(str(5.00 + i))
            
            conversion = self.tracking_service.record_conversion(data)
            
            # Approve based on revenue
            if i > 3:
                self.tracking_service.approve_conversion(conversion)
            else:
                self.tracking_service.reject_conversion(conversion, 'Low revenue')
        
        recommendations = self.tracking_service.get_conversion_recommendations(
            self.advertiser,
            days=7
        )
        
        self.assertIn('optimization_suggestions', recommendations)
        self.assertIn('quality_improvements', recommendations)
        self.assertIn('attribution_optimization', recommendations)
        self.assertIn('revenue_optimization', recommendations)
    
    def test_get_conversion_health_status(self):
        """Test getting conversion health status."""
        # Create conversions
        for i in range(20):
            data = self.valid_conversion_data.copy()
            data['conversion_id'] = f'conv_{i}'
            data['revenue'] = Decimal('10.00')
            
            conversion = self.tracking_service.record_conversion(data)
            
            # Approve most conversions
            if i < 18:
                self.tracking_service.approve_conversion(conversion)
        
        health_status = self.tracking_service.get_conversion_health_status(
            self.advertiser,
            days=7
        )
        
        self.assertIn('status', health_status)
        self.assertIn('conversion_rate', health_status)
        self.assertIn('approval_rate', health_status)
        self.assertIn('revenue_trend', health_status)
        self.assertIn('quality_score', health_status)
        self.assertIn('recommendations', health_status)
        
        # Should be healthy with good approval rate
        self.assertEqual(health_status['status'], 'healthy')


class ConversionTrackingIntegrationTestCase(TestCase):
    """Test cases for conversion tracking integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.tracking_service = ConversionTrackingService()
        self.pixel_service = TrackingPixelService()
        self.client = Client()
        
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
        
        self.pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            {
                'name': 'Test Pixel',
                'pixel_type': 'conversion',
                'description': 'Test conversion pixel',
                'target_url': 'https://example.com/thank-you',
                'status': 'active',
            }
        )
    
    def test_pixel_to_conversion_flow(self):
        """Test complete pixel to conversion flow."""
        # Fire pixel (should create conversion)
        conversion_data = {
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'revenue': Decimal('25.00'),
            'custom_parameters': {
                'affiliate_id': '12345',
                'campaign_id': '67890'
            }
        }
        
        fired_pixel = self.pixel_service.fire_tracking_pixel(self.pixel, conversion_data)
        
        self.assertTrue(fired_pixel.get('success', False))
        
        # Get conversion
        conversion_id = fired_pixel.get('conversion_id')
        conversion = Conversion.objects.get(id=conversion_id)
        
        # Verify conversion data
        self.assertEqual(conversion.pixel, self.pixel)
        self.assertEqual(conversion.revenue, Decimal('25.00'))
        self.assertEqual(conversion.custom_parameters['affiliate_id'], '12345')
        self.assertEqual(conversion.custom_parameters['campaign_id'], '67890')
    
    def test_conversion_validation_integration(self):
        """Test conversion validation integration."""
        # Create conversion with invalid data
        invalid_conversion_data = {
            'conversion_id': 'conv_invalid',
            'revenue': Decimal('25.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0',
            'pixel': self.pixel,
        }
        
        # Try to record conversion with missing required fields
        with self.assertRaises(ValueError) as context:
            self.tracking_service.record_conversion(invalid_conversion_data)
        
        self.assertIn('Missing required fields', str(context.exception))
    
    def test_conversion_attribution_integration(self):
        """Test conversion attribution integration."""
        # Create conversion with attribution data
        conversion_data = {
            'conversion_id': 'conv_attribution',
            'revenue': Decimal('25.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0',
            'pixel': self.pixel,
            'attribution_data': {
                'click_id': 'click_12345',
                'click_time': timezone.now() - timezone.timedelta(hours=2),
                'source': 'google',
                'medium': 'cpc',
                'campaign_name': 'test_campaign',
                'landing_page': 'https://example.com/landing'
            }
        }
        
        conversion = self.tracking_service.record_conversion(conversion_data)
        
        # Verify attribution data
        self.assertEqual(conversion.attribution_data['click_id'], 'click_12345')
        self.assertEqual(conversion.attribution_data['source'], 'google')
        self.assertEqual(conversion.attribution_data['medium'], 'cpc')
        
        # Get attribution analysis
        attribution_analysis = self.tracking_service.get_conversion_attribution_analysis(
            self.advertiser,
            days=7
        )
        
        self.assertIn('source_breakdown', attribution_analysis)
        self.assertIn('google', attribution_analysis['source_breakdown'])
    
    def test_conversion_fraud_detection_integration(self):
        """Test conversion fraud detection integration."""
        # Create suspicious conversion
        suspicious_conversion_data = {
            'conversion_id': 'conv_suspicious',
            'revenue': Decimal('1000.00'),  # Unusually high revenue
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0',
            'pixel': self.pixel,
            'custom_parameters': {
                'suspicious_activity': 'true',
                'multiple_conversions': 'true'
            }
        }
        
        conversion = self.tracking_service.record_conversion(suspicious_conversion_data)
        
        # Check fraud score (would be calculated by fraud detection service)
        fraud_score = self.tracking_service.calculate_fraud_score(conversion)
        
        self.assertIsInstance(fraud_score, float)
        self.assertGreaterEqual(fraud_score, 0.0)
        self.assertLessEqual(fraud_score, 1.0)
    
    def test_conversion_real_time_processing(self):
        """Test conversion real-time processing."""
        # Create conversion in real-time
        conversion_data = {
            'conversion_id': 'conv_realtime',
            'revenue': Decimal('25.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0',
            'pixel': self.pixel,
            'real_time': True
        }
        
        conversion = self.tracking_service.record_conversion(conversion_data)
        
        # Check that conversion was processed immediately
        self.assertIsNotNone(conversion.created_at)
        self.assertEqual(conversion.status, 'pending')
        
        # Approve conversion in real-time
        approved_conversion = self.tracking_service.approve_conversion(conversion)
        
        self.assertEqual(approved_conversion.status, 'approved')
        self.assertIsNotNone(approved_conversion.approved_at)
    
    def test_conversion_batch_processing(self):
        """Test conversion batch processing."""
        # Create multiple conversions
        conversions = []
        for i in range(10):
            data = {
                'conversion_id': f'conv_batch_{i}',
                'revenue': Decimal(str(10.00 + i)),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'pixel': self.pixel,
            }
            
            conversion = self.tracking_service.record_conversion(data)
            conversions.append(conversion)
        
        # Batch approve
        approved_conversions = self.tracking_service.batch_approve_conversions(
            conversions
        )
        
        self.assertEqual(len(approved_conversions), 10)
        
        # Check that all were approved
        for conversion in approved_conversions:
            self.assertEqual(conversion.status, 'approved')
    
    def test_conversion_data_export_integration(self):
        """Test conversion data export integration."""
        # Create conversions with various data
        for i in range(5):
            data = {
                'conversion_id': f'conv_export_{i}',
                'revenue': Decimal(str(10.00 + i)),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'pixel': self.pixel,
                'custom_parameters': {
                    'affiliate_id': str(i),
                    'campaign_id': str(i * 10),
                    'source': 'google' if i % 2 == 0 else 'facebook'
                },
                'attribution_data': {
                    'source': 'google' if i % 2 == 0 else 'facebook',
                    'medium': 'cpc',
                    'campaign_name': f'campaign_{i}'
                }
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        # Export data
        export_data = self.tracking_service.export_conversion_data(
            self.advertiser,
            days=30
        )
        
        self.assertIn('conversions', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('performance', export_data)
        
        # Check that all conversions are included
        self.assertEqual(len(export_data['conversions']), 5)
        
        # Check that custom parameters are included
        for conversion in export_data['conversions']:
            self.assertIn('custom_parameters', conversion)
            self.assertIn('attribution_data', conversion)
    
    def test_conversion_analytics_integration(self):
        """Test conversion analytics integration."""
        # Create conversions with different characteristics
        sources = ['google', 'facebook', 'email']
        devices = ['desktop', 'mobile', 'tablet']
        
        for i in range(9):
            data = {
                'conversion_id': f'conv_analytics_{i}',
                'revenue': Decimal(str(10.00 + i)),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'pixel': self.pixel,
                'custom_parameters': {
                    'source': sources[i % 3],
                    'device': devices[i % 3],
                    'country': 'US' if i % 2 == 0 else 'CA'
                }
            }
            
            conversion = self.tracking_service.record_conversion(data)
            self.tracking_service.approve_conversion(conversion)
        
        # Get comprehensive analytics
        analytics = self.tracking_service.get_conversion_analytics(
            self.advertiser,
            days=7
        )
        
        self.assertIn('total_conversions', analytics)
        self.assertIn('source_breakdown', analytics)
        self.assertIn('device_breakdown', analytics)
        self.assertIn('country_breakdown', analytics)
        
        # Check breakdowns
        self.assertEqual(len(analytics['source_breakdown']), 3)
        self.assertEqual(len(analytics['device_breakdown']), 3)
        self.assertEqual(len(analytics['country_breakdown']), 2)
    
    def test_conversion_error_handling(self):
        """Test conversion error handling."""
        # Test with various error conditions
        
        # 1. Missing required fields
        with self.assertRaises(ValueError):
            self.tracking_service.record_conversion({})
        
        # 2. Invalid revenue
        with self.assertRaises(ValueError):
            self.tracking_service.record_conversion({
                'conversion_id': 'test',
                'revenue': Decimal('-10.00'),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0',
                'pixel': self.pixel,
            })
        
        # 3. Invalid IP address
        with self.assertRaises(ValueError):
            self.tracking_service.record_conversion({
                'conversion_id': 'test',
                'revenue': Decimal('10.00'),
                'ip_address': 'invalid_ip',
                'user_agent': 'Mozilla/5.0',
                'pixel': self.pixel,
            })
        
        # 4. Duplicate conversion ID
        valid_data = {
            'conversion_id': 'test_duplicate',
            'revenue': Decimal('10.00'),
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0',
            'pixel': self.pixel,
        }
        
        self.tracking_service.record_conversion(valid_data)
        
        with self.assertRaises(ValueError):
            self.tracking_service.record_conversion(valid_data)

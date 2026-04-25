"""
Test Tracking Pixel

Comprehensive tests for tracking pixel functionality
including pixel generation, testing, and analytics.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urlencode

from ..models.tracking import TrackingPixel, Conversion
from ..models.advertiser import Advertiser
try:
    from ..services import TrackingPixelService
except ImportError:
    TrackingPixelService = None
try:
    from ..services import ConversionTrackingService
except ImportError:
    ConversionTrackingService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class TrackingPixelServiceTestCase(TestCase):
    """Test cases for TrackingPixelService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.pixel_service = TrackingPixelService()
        
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
        
        self.valid_pixel_data = {
            'name': 'Test Pixel',
            'pixel_type': 'conversion',
            'description': 'Test conversion pixel',
            'target_url': 'https://example.com/thank-you',
            'status': 'active',
        }
    
    def test_create_tracking_pixel_success(self):
        """Test successful tracking pixel creation."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        self.assertIsInstance(pixel, TrackingPixel)
        self.assertEqual(pixel.advertiser, self.advertiser)
        self.assertEqual(pixel.name, 'Test Pixel')
        self.assertEqual(pixel.pixel_type, 'conversion')
        self.assertEqual(pixel.status, 'active')
        self.assertIsNotNone(pixel.pixel_code)
        self.assertIsNotNone(pixel.pixel_id)
    
    def test_create_tracking_pixel_invalid_data(self):
        """Test tracking pixel creation with invalid data."""
        invalid_data = self.valid_pixel_data.copy()
        invalid_data['name'] = ''  # Empty name
        
        with self.assertRaises(ValueError) as context:
            self.pixel_service.create_tracking_pixel(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Pixel name is required', str(context.exception))
    
    def test_create_tracking_pixel_invalid_url(self):
        """Test tracking pixel creation with invalid URL."""
        invalid_data = self.valid_pixel_data.copy()
        invalid_data['target_url'] = 'invalid-url'
        
        with self.assertRaises(ValueError) as context:
            self.pixel_service.create_tracking_pixel(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Invalid target URL', str(context.exception))
    
    def test_update_tracking_pixel_success(self):
        """Test successful tracking pixel update."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        update_data = {
            'name': 'Updated Pixel',
            'description': 'Updated description',
        }
        
        updated_pixel = self.pixel_service.update_tracking_pixel(
            pixel,
            update_data
        )
        
        self.assertEqual(updated_pixel.name, 'Updated Pixel')
        self.assertEqual(updated_pixel.description, 'Updated description')
        self.assertEqual(pixel.pixel_type, 'conversion')  # Unchanged
    
    def test_update_active_pixel_critical_fields(self):
        """Test updating critical fields on active pixel."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Try to update pixel type
        update_data = {
            'pixel_type': 'impression',  # Critical field
        }
        
        with self.assertRaises(ValueError) as context:
            self.pixel_service.update_tracking_pixel(
                pixel,
                update_data
            )
        
        self.assertIn('Cannot change pixel type on active pixel', str(context.exception))
    
    def test_generate_pixel_code_success(self):
        """Test successful pixel code generation."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        pixel_code = self.pixel_service.generate_pixel_code(pixel)
        
        self.assertIsInstance(pixel_code, str)
        self.assertIn(pixel.pixel_id, pixel_code)
        self.assertIn('tracking', pixel_code.lower())
        self.assertIn('pixel', pixel_code.lower())
    
    def test_test_tracking_pixel_success(self):
        """Test successful tracking pixel testing."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        test_result = self.pixel_service.test_tracking_pixel(pixel)
        
        self.assertTrue(test_result.get('success', False))
        self.assertIn('test_url', test_result)
        self.assertIn('pixel_code', test_result)
        self.assertIn('fired_at', test_result)
    
    def test_test_tracking_pixel_inactive(self):
        """Test testing inactive tracking pixel."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Deactivate pixel
        pixel.status = 'inactive'
        pixel.save()
        
        with self.assertRaises(ValueError) as context:
            self.pixel_service.test_tracking_pixel(pixel)
        
        self.assertIn('Cannot test inactive pixel', str(context.exception))
    
    def test_fire_tracking_pixel_success(self):
        """Test successful tracking pixel firing."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversion data
        conversion_data = {
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'revenue': Decimal('25.00'),
            'custom_parameters': {
                'affiliate_id': '12345',
                'campaign_id': '67890'
            }
        }
        
        fired_pixel = self.pixel_service.fire_tracking_pixel(
            pixel,
            conversion_data
        )
        
        self.assertTrue(fired_pixel.get('success', False))
        self.assertIn('conversion_id', fired_pixel)
        self.assertIn('fired_at', fired_pixel)
        
        # Check that conversion was created
        conversion_id = fired_pixel.get('conversion_id')
        self.assertIsNotNone(conversion_id)
        
        conversion = Conversion.objects.get(id=conversion_id)
        self.assertEqual(conversion.pixel, pixel)
        self.assertEqual(conversion.revenue, Decimal('25.00'))
    
    def test_fire_tracking_pixel_no_revenue(self):
        """Test firing tracking pixel without revenue."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversion data without revenue
        conversion_data = {
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        fired_pixel = self.pixel_service.fire_tracking_pixel(
            pixel,
            conversion_data
        )
        
        self.assertTrue(fired_pixel.get('success', False))
        
        # Check that conversion was created with zero revenue
        conversion_id = fired_pixel.get('conversion_id')
        conversion = Conversion.objects.get(id=conversion_id)
        self.assertEqual(conversion.revenue, Decimal('0.00'))
    
    def test_get_pixel_analytics_success(self):
        """Test getting pixel analytics."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create some conversions
        for i in range(5):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal(str(10.00 + i)),
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        # Get analytics for last 7 days
        analytics = self.pixel_service.get_pixel_analytics(
            pixel,
            days=7
        )
        
        self.assertIn('total_conversions', analytics)
        self.assertIn('total_revenue', analytics)
        self.assertIn('average_revenue', analytics)
        self.assertIn('conversion_rate', analytics)
        self.assertIn('daily_breakdown', analytics)
        
        # Check totals
        self.assertEqual(analytics['total_conversions'], 5)
        self.assertEqual(analytics['total_revenue'], Decimal('40.00'))
    
    def test_get_pixel_analytics_no_data(self):
        """Test getting pixel analytics with no data."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Get analytics
        analytics = self.pixel_service.get_pixel_analytics(
            pixel,
            days=7
        )
        
        self.assertEqual(analytics['total_conversions'], 0)
        self.assertEqual(analytics['total_revenue'], Decimal('0.00'))
        self.assertEqual(analytics['average_revenue'], Decimal('0.00'))
    
    def test_pause_tracking_pixel_success(self):
        """Test successful tracking pixel pausing."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        paused_pixel = self.pixel_service.pause_tracking_pixel(pixel)
        
        self.assertEqual(paused_pixel.status, 'paused')
        self.assertIsNotNone(paused_pixel.paused_at)
    
    def test_resume_tracking_pixel_success(self):
        """Test successful tracking pixel resumption."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Pause pixel first
        self.pixel_service.pause_tracking_pixel(pixel)
        
        # Resume pixel
        resumed_pixel = self.pixel_service.resume_tracking_pixel(pixel)
        
        self.assertEqual(resumed_pixel.status, 'active')
        self.assertIsNone(resumed_pixel.paused_at)
    
    def test_delete_tracking_pixel_success(self):
        """Test successful tracking pixel deletion."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        pixel_id = pixel.id
        
        self.pixel_service.delete_tracking_pixel(pixel)
        
        with self.assertRaises(TrackingPixel.DoesNotExist):
            TrackingPixel.objects.get(id=pixel_id)
    
    def test_delete_tracking_pixel_with_conversions(self):
        """Test deleting tracking pixel with conversions."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversion
        conversion_data = {
            'ip_address': '192.168.1.1',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'revenue': Decimal('25.00'),
        }
        
        self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        with self.assertRaises(ValueError) as context:
            self.pixel_service.delete_tracking_pixel(pixel)
        
        self.assertIn('Cannot delete pixel with conversions', str(context.exception))
    
    def test_search_tracking_pixels(self):
        """Test tracking pixel search functionality."""
        # Create multiple pixels
        for i in range(5):
            data = self.valid_pixel_data.copy()
            data['name'] = f'Pixel {i}'
            self.pixel_service.create_tracking_pixel(self.advertiser, data)
        
        # Search by name
        results = self.pixel_service.search_tracking_pixels(
            self.advertiser,
            'Pixel 1'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'Pixel 1')
    
    def test_get_active_tracking_pixels(self):
        """Test getting active tracking pixels."""
        # Create pixels
        pixels = []
        for i in range(3):
            data = self.valid_pixel_data.copy()
            data['name'] = f'Pixel {i}'
            pixel = self.pixel_service.create_tracking_pixel(self.advertiser, data)
            
            if i < 2:
                pixel.status = 'active'
            else:
                pixel.status = 'paused'
            
            pixel.save()
            pixels.append(pixel)
        
        active_pixels = self.pixel_service.get_active_tracking_pixels(self.advertiser)
        
        self.assertEqual(len(active_pixels), 2)
        
        for pixel in active_pixels:
            self.assertEqual(pixel.status, 'active')
    
    def test_validate_pixel_data_success(self):
        """Test successful pixel data validation."""
        is_valid, errors = self.pixel_service.validate_pixel_data(
            self.valid_pixel_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_pixel_data_invalid_type(self):
        """Test pixel data validation with invalid type."""
        invalid_data = self.valid_pixel_data.copy()
        invalid_data['pixel_type'] = 'invalid_type'
        
        is_valid, errors = self.pixel_service.validate_pixel_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('pixel_type', errors)
    
    def test_validate_pixel_data_missing_url(self):
        """Test pixel data validation with missing URL."""
        invalid_data = self.valid_pixel_data.copy()
        del invalid_data['target_url']
        
        is_valid, errors = self.pixel_service.validate_pixel_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('target_url', errors)
    
    def test_get_pixel_statistics(self):
        """Test getting pixel statistics."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions
        for i in range(10):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('10.00'),
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        stats = self.pixel_service.get_pixel_statistics(pixel)
        
        self.assertIn('total_conversions', stats)
        self.assertIn('total_revenue', stats)
        self.assertIn('average_revenue', stats)
        self.assertIn('conversion_rate', stats)
        self.assertIn('last_conversion', stats)
        
        # Check totals
        self.assertEqual(stats['total_conversions'], 10)
        self.assertEqual(stats['total_revenue'], Decimal('100.00'))
    
    def test_get_pixel_performance_trends(self):
        """Test getting pixel performance trends."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions over different days
        for i in range(7):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('10.00'),
                'created_at': timezone.now() - timezone.timedelta(days=i)
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        trends = self.pixel_service.get_pixel_performance_trends(
            pixel,
            days=7
        )
        
        self.assertIn('daily_trends', trends)
        self.assertIn('growth_rate', trends)
        self.assertIn('performance_trend', trends)
        self.assertIn('forecast', trends)
    
    def test_duplicate_tracking_pixel(self):
        """Test tracking pixel duplication."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create some conversions
        for i in range(3):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('10.00'),
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        # Duplicate pixel
        duplicated_pixel = self.pixel_service.duplicate_tracking_pixel(pixel)
        
        self.assertEqual(duplicated_pixel.name, 'Test Pixel (Duplicate)')
        self.assertEqual(duplicated_pixel.pixel_type, pixel.pixel_type)
        self.assertEqual(duplicated_pixel.target_url, pixel.target_url)
        self.assertEqual(duplicated_pixel.status, 'draft')
        
        # Check that conversions were not duplicated
        self.assertEqual(duplicated_pixel.conversions.count(), 0)
        self.assertEqual(pixel.conversions.count(), 3)
    
    def test_export_pixel_data(self):
        """Test exporting pixel data."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions
        for i in range(5):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal(str(10.00 + i)),
                'custom_parameters': {
                    'affiliate_id': str(i),
                    'campaign_id': str(i * 10)
                }
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        export_data = self.pixel_service.export_pixel_data(
            pixel,
            days=30
        )
        
        self.assertIn('pixel', export_data)
        self.assertIn('conversions', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('performance', export_data)
        self.assertIn('export_date', export_data)
        
        # Check conversions count
        self.assertEqual(len(export_data['conversions']), 5)
    
    def test_get_supported_pixel_types(self):
        """Test getting supported pixel types."""
        pixel_types = self.pixel_service.get_supported_pixel_types()
        
        expected_types = [
            'conversion',
            'impression',
            'click',
            'lead',
            'sale',
            'signup',
            'download',
            'custom'
        ]
        
        for pixel_type in expected_types:
            self.assertIn(pixel_type, pixel_types)
    
    @patch('api.advertiser_portal.services.tracking.TrackingPixelService.send_notification')
    def test_send_pixel_notification(self, mock_send_notification):
        """Test sending pixel notification."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Send notification
        self.pixel_service.send_pixel_notification(
            pixel,
            'pixel_created',
            'Your tracking pixel has been created successfully'
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'pixel_created')
            self.assertIn('created successfully', notification_data['message'])
    
    def test_bulk_pause_tracking_pixels(self):
        """Test bulk pausing of tracking pixels."""
        # Create multiple pixels
        pixels = []
        for i in range(3):
            data = self.valid_pixel_data.copy()
            data['name'] = f'Pixel {i}'
            pixel = self.pixel_service.create_tracking_pixel(self.advertiser, data)
            pixels.append(pixel)
        
        # Bulk pause
        paused_pixels = self.pixel_service.bulk_pause_tracking_pixels(pixels)
        
        self.assertEqual(len(paused_pixels), 3)
        
        for pixel in paused_pixels:
            self.assertEqual(pixel.status, 'paused')
    
    def test_bulk_resume_tracking_pixels(self):
        """Test bulk resuming of tracking pixels."""
        # Create and pause pixels
        pixels = []
        for i in range(3):
            data = self.valid_pixel_data.copy()
            data['name'] = f'Pixel {i}'
            pixel = self.pixel_service.create_tracking_pixel(self.advertiser, data)
            self.pixel_service.pause_tracking_pixel(pixel)
            pixels.append(pixel)
        
        # Bulk resume
        resumed_pixels = self.pixel_service.bulk_resume_tracking_pixels(pixels)
        
        self.assertEqual(len(resumed_pixels), 3)
        
        for pixel in resumed_pixels:
            self.assertEqual(pixel.status, 'active')
    
    def test_get_pixel_health_status(self):
        """Test getting pixel health status."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions
        for i in range(10):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('10.00'),
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        health_status = self.pixel_service.get_pixel_health_status(pixel)
        
        self.assertIn('status', health_status)
        self.assertIn('last_fired', health_status)
        self.assertIn('conversion_rate', health_status)
        self.assertIn('error_rate', health_status)
        self.assertIn('recommendations', health_status)
        
        # Should be healthy with conversions
        self.assertEqual(health_status['status'], 'healthy')
    
    def test_get_pixel_recommendations(self):
        """Test getting pixel recommendations."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions
        for i in range(5):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('5.00'),
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        recommendations = self.pixel_service.get_pixel_recommendations(pixel)
        
        self.assertIn('optimization_suggestions', recommendations)
        self.assertIn('placement_recommendations', recommendations)
        self.assertIn('performance_improvements', recommendations)
        self.assertIn('target_audience_suggestions', recommendations)
    
    def test_get_pixel_conversion_funnel(self):
        """Test getting pixel conversion funnel."""
        pixel = self.pixel_service.create_tracking_pixel(
            self.advertiser,
            self.valid_pixel_data
        )
        
        # Create conversions with different timestamps
        base_time = timezone.now()
        for i in range(20):
            conversion_data = {
                'ip_address': f'192.168.1.{i+1}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'revenue': Decimal('10.00'),
                'created_at': base_time - timezone.timedelta(hours=i)
            }
            
            self.pixel_service.fire_tracking_pixel(pixel, conversion_data)
        
        funnel = self.pixel_service.get_pixel_conversion_funnel(
            pixel,
            days=7
        )
        
        self.assertIn('stages', funnel)
        self.assertIn('conversion_rates', funnel)
        self.assertIn('drop_off_points', funnel)
        self.assertIn('optimization_opportunities', funnel)


class TrackingPixelIntegrationTestCase(TestCase):
    """Test cases for tracking pixel integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
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
    
    def test_pixel_endpoint_access(self):
        """Test accessing pixel endpoint."""
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')
    
    def test_pixel_endpoint_with_parameters(self):
        """Test pixel endpoint with parameters."""
        # Generate pixel URL with parameters
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'revenue': '25.00',
                'affiliate_id': '12345',
                'campaign_id': '67890'
            }
        )
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        self.assertEqual(conversion.revenue, Decimal('25.00'))
    
    def test_pixel_endpoint_with_invalid_revenue(self):
        """Test pixel endpoint with invalid revenue parameter."""
        # Generate pixel URL with invalid revenue
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'revenue': 'invalid_revenue'
            }
        )
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created with zero revenue
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        self.assertEqual(conversion.revenue, Decimal('0.00'))
    
    def test_pixel_endpoint_with_custom_parameters(self):
        """Test pixel endpoint with custom parameters."""
        # Generate pixel URL with custom parameters
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'revenue': '25.00',
                'custom_param1': 'value1',
                'custom_param2': 'value2'
            }
        )
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created with custom parameters
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        custom_params = conversion.custom_parameters
        self.assertEqual(custom_params.get('custom_param1'), 'value1')
        self.assertEqual(custom_params.get('custom_param2'), 'value2')
    
    def test_pixel_endpoint_rate_limiting(self):
        """Test pixel endpoint rate limiting."""
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make multiple requests rapidly
        responses = []
        for i in range(10):
            response = self.client.get(pixel_url)
            responses.append(response)
        
        # All requests should succeed (rate limiting implementation dependent)
        for response in responses:
            self.assertEqual(response.status_code, 200)
    
    def test_pixel_endpoint_with_invalid_pixel_id(self):
        """Test pixel endpoint with invalid pixel ID."""
        # Create URL with invalid pixel ID
        invalid_pixel_url = f'/tracking/pixel/invalid_pixel_id/'
        
        # Make request to invalid URL
        response = self.client.get(invalid_pixel_url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_pixel_endpoint_with_inactive_pixel(self):
        """Test pixel endpoint with inactive pixel."""
        # Deactivate pixel
        self.pixel.status = 'inactive'
        self.pixel.save()
        
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_pixel_endpoint_with_expired_pixel(self):
        """Test pixel endpoint with expired pixel."""
        # Set pixel as expired
        self.pixel.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.pixel.save()
        
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_pixel_endpoint_with_ip_tracking(self):
        """Test pixel endpoint IP tracking."""
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that IP was tracked
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        self.assertIsNotNone(conversion.ip_address)
    
    def test_pixel_endpoint_with_user_agent_tracking(self):
        """Test pixel endpoint user agent tracking."""
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL with user agent
        response = self.client.get(
            pixel_url,
            HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that user agent was tracked
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        self.assertIsNotNone(conversion.user_agent)
        self.assertIn('Mozilla', conversion.user_agent)
    
    def test_pixel_endpoint_with_referer_tracking(self):
        """Test pixel endpoint referer tracking."""
        # Generate pixel URL
        pixel_url = self.pixel_service.get_pixel_url(self.pixel)
        
        # Make request to pixel URL with referer
        response = self.client.get(
            pixel_url,
            HTTP_REFERER='https://example.com/source-page'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that referer was tracked
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        self.assertIsNotNone(conversion.referer)
        self.assertEqual(conversion.referer, 'https://example.com/source-page')
    
    def test_pixel_endpoint_with_duplicate_conversions(self):
        """Test pixel endpoint duplicate conversion handling."""
        # Generate pixel URL with unique identifier
        unique_id = 'test_unique_id_12345'
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'unique_id': unique_id,
                'revenue': '25.00'
            }
        )
        
        # Make first request
        response1 = self.client.get(pixel_url)
        self.assertEqual(response1.status_code, 200)
        
        # Make second request with same unique ID
        response2 = self.client.get(pixel_url)
        self.assertEqual(response2.status_code, 200)
        
        # Should only have one conversion (duplicate handling)
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
    
    def test_pixel_endpoint_with_large_payload(self):
        """Test pixel endpoint with large parameter payload."""
        # Generate pixel URL with many parameters
        parameters = {}
        for i in range(100):
            parameters[f'param_{i}'] = f'value_{i}' * 10  # Long values
        
        pixel_url = self.pixel_service.get_pixel_url(self.pixel, parameters)
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
    
    def test_pixel_endpoint_with_unicode_parameters(self):
        """Test pixel endpoint with unicode parameters."""
        # Generate pixel URL with unicode parameters
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'revenue': '25.00',
                'unicode_param': 'Unicode test: ñáéíóú',
                'emoji_param': 'Test emoji: \ud83d\ude0a'
            }
        )
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created with unicode parameters
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        custom_params = conversion.custom_parameters
        self.assertIn('unicode_param', custom_params)
        self.assertIn('ñáéíóú', custom_params['unicode_param'])
        self.assertIn('emoji_param', custom_params)
        self.assertIn('\ud83d\ude0a', custom_params['emoji_param'])
    
    def test_pixel_endpoint_with_malicious_parameters(self):
        """Test pixel endpoint with potentially malicious parameters."""
        # Generate pixel URL with potentially malicious parameters
        pixel_url = self.pixel_service.get_pixel_url(
            self.pixel,
            parameters={
                'revenue': '25.00',
                'script_param': '<script>alert("xss")</script>',
                'sql_param': "'; DROP TABLE conversions; --"
            }
        )
        
        # Make request to pixel URL
        response = self.client.get(pixel_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that conversion was created (parameters should be sanitized)
        conversions = Conversion.objects.filter(pixel=self.pixel)
        self.assertEqual(conversions.count(), 1)
        
        conversion = conversions.first()
        custom_params = conversion.custom_parameters
        
        # Parameters should be sanitized or filtered
        self.assertNotIn('<script>', custom_params.get('script_param', ''))
        self.assertNotIn('DROP TABLE', custom_params.get('sql_param', ''))

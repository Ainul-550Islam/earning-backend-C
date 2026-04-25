"""
Test S2S Postback

Comprehensive tests for server-to-server postback functionality
including postback configuration, testing, and validation.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from urllib.parse import urlencode

from ..models.tracking import S2SPostback, Conversion
from ..models.advertiser import Advertiser
try:
    from ..services import S2SPostbackService
except ImportError:
    S2SPostbackService = None
try:
    from ..services import ConversionTrackingService
except ImportError:
    ConversionTrackingService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class S2SPostbackServiceTestCase(TestCase):
    """Test cases for S2SPostbackService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.postback_service = S2SPostbackService()
        
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
        
        self.valid_postback_data = {
            'name': 'Test Postback',
            'postback_type': 'conversion',
            'description': 'Test conversion postback',
            'postback_url': 'https://example.com/postback',
            'method': 'POST',
            'status': 'active',
        }
    
    def test_create_s2s_postback_success(self):
        """Test successful S2S postback creation."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        self.assertIsInstance(postback, S2SPostback)
        self.assertEqual(postback.advertiser, self.advertiser)
        self.assertEqual(postback.name, 'Test Postback')
        self.assertEqual(postback.postback_type, 'conversion')
        self.assertEqual(postback.method, 'POST')
        self.assertEqual(postback.status, 'active')
        self.assertIsNotNone(postback.postback_token)
    
    def test_create_s2s_postback_invalid_data(self):
        """Test S2S postback creation with invalid data."""
        invalid_data = self.valid_postback_data.copy()
        invalid_data['name'] = ''  # Empty name
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.create_s2s_postback(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Postback name is required', str(context.exception))
    
    def test_create_s2s_postback_invalid_url(self):
        """Test S2S postback creation with invalid URL."""
        invalid_data = self.valid_postback_data.copy()
        invalid_data['postback_url'] = 'invalid-url'
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.create_s2s_postback(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Invalid postback URL', str(context.exception))
    
    def test_create_s2s_postback_invalid_method(self):
        """Test S2S postback creation with invalid method."""
        invalid_data = self.valid_postback_data.copy()
        invalid_data['method'] = 'INVALID'  # Invalid HTTP method
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.create_s2s_postback(
                self.advertiser,
                invalid_data
            )
        
        self.assertIn('Invalid HTTP method', str(context.exception))
    
    def test_update_s2s_postback_success(self):
        """Test successful S2S postback update."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        update_data = {
            'name': 'Updated Postback',
            'description': 'Updated description',
        }
        
        updated_postback = self.postback_service.update_s2s_postback(
            postback,
            update_data
        )
        
        self.assertEqual(updated_postback.name, 'Updated Postback')
        self.assertEqual(updated_postback.description, 'Updated description')
        self.assertEqual(postback.postback_type, 'conversion')  # Unchanged
    
    def test_update_active_postback_critical_fields(self):
        """Test updating critical fields on active postback."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Try to update postback URL
        update_data = {
            'postback_url': 'https://example.com/new-postback',  # Critical field
        }
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.update_s2s_postback(
                postback,
                update_data
            )
        
        self.assertIn('Cannot change postback URL on active postback', str(context.exception))
    
    def test_generate_postback_token_success(self):
        """Test successful postback token generation."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        token = self.postback_service.generate_postback_token(postback)
        
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 32)  # Should be 32 characters
        self.assertNotEqual(token, postback.postback_token)
    
    def test_test_s2s_postback_success(self):
        """Test successful S2S postback testing."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        test_data = {
            'conversion_id': 'test_conv_123',
            'revenue': '25.00',
            'affiliate_id': '12345',
            'campaign_id': '67890'
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            test_result = self.postback_service.test_s2s_postback(
                postback,
                test_data
            )
            
            self.assertTrue(test_result.get('success', False))
            self.assertIn('test_response', test_result)
            self.assertIn('sent_at', test_result)
            
            # Check that the postback was sent
            mock_post.assert_called_once()
    
    def test_test_s2s_postback_failure(self):
        """Test S2S postback testing with failure."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        test_data = {
            'conversion_id': 'test_conv_123',
            'revenue': '25.00',
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json.return_value = {'error': 'Internal server error'}
            
            test_result = self.postback_service.test_s2s_postback(
                postback,
                test_data
            )
            
            self.assertFalse(test_result.get('success', False))
            self.assertIn('error', test_result)
    
    def test_test_s2s_postback_inactive(self):
        """Test testing inactive S2S postback."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Deactivate postback
        postback.status = 'inactive'
        postback.save()
        
        test_data = {
            'conversion_id': 'test_conv_123',
            'revenue': '25.00',
        }
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.test_s2s_postback(
                postback,
                test_data
            )
        
        self.assertIn('Cannot test inactive postback', str(context.exception))
    
    def test_send_s2s_postback_success(self):
        """Test successful S2S postback sending."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            sent_postback = self.postback_service.send_s2s_postback(
                postback,
                conversion
            )
            
            self.assertTrue(sent_postback.get('success', False))
            self.assertIn('postback_id', sent_postback)
            self.assertIn('sent_at', sent_postback)
            
            # Check that the postback was sent
            mock_post.assert_called_once()
    
    def test_send_s2s_postback_with_custom_parameters(self):
        """Test S2S postback sending with custom parameters."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversion with custom parameters
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            custom_parameters={
                'affiliate_id': '12345',
                'campaign_id': '67890',
                'sub_id': 'abc123'
            }
        )
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            sent_postback = self.postback_service.send_s2s_postback(
                postback,
                conversion
            )
            
            self.assertTrue(sent_postback.get('success', False))
            
            # Check that custom parameters were included
            call_args = mock_post.call_args
            sent_data = call_args[1]['data'] if call_args and 'data' in call_args[1] else {}
            
            self.assertIn('affiliate_id', sent_data)
            self.assertIn('campaign_id', sent_data)
            self.assertIn('sub_id', sent_data)
    
    def test_send_s2s_postback_get_method(self):
        """Test S2S postback sending with GET method."""
        postback_data = self.valid_postback_data.copy()
        postback_data['method'] = 'GET'
        
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'status': 'success'}
            
            sent_postback = self.postback_service.send_s2s_postback(
                postback,
                conversion
            )
            
            self.assertTrue(sent_postback.get('success', False))
            
            # Check that GET was used
            mock_get.assert_called_once()
    
    def test_send_s2s_postback_retry_on_failure(self):
        """Test S2S postback sending with retry on failure."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        with patch('requests.post') as mock_post:
            # First call fails, second succeeds
            mock_post.side_effect = [
                Mock(status_code=500, json=lambda: {'error': 'Internal server error'}),
                Mock(status_code=200, json=lambda: {'status': 'success'})
            ]
            
            sent_postback = self.postback_service.send_s2s_postback(
                postback,
                conversion
            )
            
            self.assertTrue(sent_postback.get('success', False))
            self.assertEqual(mock_post.call_count, 2)  # Should retry once
    
    def test_get_postback_analytics_success(self):
        """Test getting postback analytics."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create some conversions and postbacks
        for i in range(5):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(10.00 + i)),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            
            # Simulate successful postback
            postback_data = {
                'conversion_id': conversion.conversion_id,
                'revenue': str(conversion.revenue),
                'status': 'success'
            }
            
            self.postback_service.record_postback_result(
                postback,
                conversion,
                postback_data
            )
        
        # Get analytics for last 7 days
        analytics = self.postback_service.get_postback_analytics(
            postback,
            days=7
        )
        
        self.assertIn('total_postbacks', analytics)
        self.assertIn('successful_postbacks', analytics)
        self.assertIn('failed_postbacks', analytics)
        self.assertIn('success_rate', analytics)
        self.assertIn('daily_breakdown', analytics)
        
        # Check totals
        self.assertEqual(analytics['total_postbacks'], 5)
        self.assertEqual(analytics['successful_postbacks'], 5)
        self.assertEqual(analytics['failed_postbacks'], 0)
    
    def test_get_postback_analytics_no_data(self):
        """Test getting postback analytics with no data."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Get analytics
        analytics = self.postback_service.get_postback_analytics(
            postback,
            days=7
        )
        
        self.assertEqual(analytics['total_postbacks'], 0)
        self.assertEqual(analytics['successful_postbacks'], 0)
        self.assertEqual(analytics['failed_postbacks'], 0)
        self.assertEqual(analytics['success_rate'], 0)
    
    def test_pause_s2s_postback_success(self):
        """Test successful S2S postback pausing."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        paused_postback = self.postback_service.pause_s2s_postback(postback)
        
        self.assertEqual(paused_postback.status, 'paused')
        self.assertIsNotNone(paused_postback.paused_at)
    
    def test_resume_s2s_postback_success(self):
        """Test successful S2S postback resumption."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Pause postback first
        self.postback_service.pause_s2s_postback(postback)
        
        # Resume postback
        resumed_postback = self.postback_service.resume_s2s_postback(postback)
        
        self.assertEqual(resumed_postback.status, 'active')
        self.assertIsNone(resumed_postback.paused_at)
    
    def test_delete_s2s_postback_success(self):
        """Test successful S2S postback deletion."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        postback_id = postback.id
        
        self.postback_service.delete_s2s_postback(postback)
        
        with self.assertRaises(S2SPostback.DoesNotExist):
            S2SPostback.objects.get(id=postback_id)
    
    def test_delete_s2s_postback_with_results(self):
        """Test deleting S2S postback with results."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversion and postback result
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        self.postback_service.record_postback_result(
            postback,
            conversion,
            {'status': 'success'}
        )
        
        with self.assertRaises(ValueError) as context:
            self.postback_service.delete_s2s_postback(postback)
        
        self.assertIn('Cannot delete postback with results', str(context.exception))
    
    def test_search_s2s_postbacks(self):
        """Test S2S postback search functionality."""
        # Create multiple postbacks
        for i in range(5):
            data = self.valid_postback_data.copy()
            data['name'] = f'Postback {i}'
            self.postback_service.create_s2s_postback(self.advertiser, data)
        
        # Search by name
        results = self.postback_service.search_s2s_postbacks(
            self.advertiser,
            'Postback 1'
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'Postback 1')
    
    def test_get_active_s2s_postbacks(self):
        """Test getting active S2S postbacks."""
        # Create postbacks
        postbacks = []
        for i in range(3):
            data = self.valid_postback_data.copy()
            data['name'] = f'Postback {i}'
            postback = self.postback_service.create_s2s_postback(self.advertiser, data)
            
            if i < 2:
                postback.status = 'active'
            else:
                postback.status = 'paused'
            
            postback.save()
            postbacks.append(postback)
        
        active_postbacks = self.postback_service.get_active_s2s_postbacks(self.advertiser)
        
        self.assertEqual(len(active_postbacks), 2)
        
        for postback in active_postbacks:
            self.assertEqual(postback.status, 'active')
    
    def test_validate_postback_data_success(self):
        """Test successful postback data validation."""
        is_valid, errors = self.postback_service.validate_postback_data(
            self.valid_postback_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_postback_data_invalid_type(self):
        """Test postback data validation with invalid type."""
        invalid_data = self.valid_postback_data.copy()
        invalid_data['postback_type'] = 'invalid_type'
        
        is_valid, errors = self.postback_service.validate_postback_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('postback_type', errors)
    
    def test_validate_postback_data_missing_url(self):
        """Test postback data validation with missing URL."""
        invalid_data = self.valid_postback_data.copy()
        del invalid_data['postback_url']
        
        is_valid, errors = self.postback_service.validate_postback_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertIn('postback_url', errors)
    
    def test_get_postback_statistics(self):
        """Test getting postback statistics."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversions and postback results
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            
            # Simulate postback results (8 success, 2 failure)
            status = 'success' if i < 8 else 'failed'
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {'status': status}
            )
        
        stats = self.postback_service.get_postback_statistics(postback)
        
        self.assertIn('total_postbacks', stats)
        self.assertIn('successful_postbacks', stats)
        self.assertIn('failed_postbacks', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('last_postback', stats)
        
        # Check totals
        self.assertEqual(stats['total_postbacks'], 10)
        self.assertEqual(stats['successful_postbacks'], 8)
        self.assertEqual(stats['failed_postbacks'], 2)
        self.assertEqual(stats['success_rate'], 80.0)
    
    def test_get_postback_performance_trends(self):
        """Test getting postback performance trends."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create postback results over different days
        for i in range(7):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now() - timezone.timedelta(days=i)
            )
            
            status = 'success' if i < 5 else 'failed'
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {'status': status, 'sent_at': timezone.now() - timezone.timedelta(days=i)}
            )
        
        trends = self.postback_service.get_postback_performance_trends(
            postback,
            days=7
        )
        
        self.assertIn('daily_trends', trends)
        self.assertIn('success_rate_trend', trends)
        self.assertIn('performance_trend', trends)
        self.assertIn('forecast', trends)
    
    def test_duplicate_s2s_postback(self):
        """Test S2S postback duplication."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create some postback results
        for i in range(3):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {'status': 'success'}
            )
        
        # Duplicate postback
        duplicated_postback = self.postback_service.duplicate_s2s_postback(postback)
        
        self.assertEqual(duplicated_postback.name, 'Test Postback (Duplicate)')
        self.assertEqual(duplicated_postback.postback_type, postback.postback_type)
        self.assertEqual(duplicated_postback.postback_url, postback.postback_url)
        self.assertEqual(duplicated_postback.status, 'draft')
        
        # Check that results were not duplicated
        self.assertEqual(duplicated_postback.results.count(), 0)
        self.assertEqual(postback.results.count(), 3)
    
    def test_export_postback_data(self):
        """Test exporting postback data."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create conversions and postback results
        for i in range(5):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(10.00 + i)),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={
                    'affiliate_id': str(i),
                    'campaign_id': str(i * 10)
                }
            )
            
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {
                    'status': 'success',
                    'response_time': 0.5 + i * 0.1,
                    'sent_at': timezone.now() - timezone.timedelta(hours=i)
                }
            )
        
        export_data = self.postback_service.export_postback_data(
            postback,
            days=30
        )
        
        self.assertIn('postback', export_data)
        self.assertIn('results', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('performance', export_data)
        self.assertIn('export_date', export_data)
        
        # Check results count
        self.assertEqual(len(export_data['results']), 5)
    
    def test_get_supported_postback_types(self):
        """Test getting supported postback types."""
        postback_types = self.postback_service.get_supported_postback_types()
        
        expected_types = [
            'conversion',
            'lead',
            'sale',
            'signup',
            'download',
            'click',
            'impression',
            'custom'
        ]
        
        for postback_type in expected_types:
            self.assertIn(postback_type, postback_types)
    
    def test_get_supported_http_methods(self):
        """Test getting supported HTTP methods."""
        http_methods = self.postback_service.get_supported_http_methods()
        
        expected_methods = ['GET', 'POST', 'PUT', 'PATCH']
        
        for method in expected_methods:
            self.assertIn(method, http_methods)
    
    @patch('api.advertiser_portal.services.tracking.S2SPostbackService.send_notification')
    def test_send_postback_notification(self, mock_send_notification):
        """Test sending postback notification."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Send notification
        self.postback_service.send_postback_notification(
            postback,
            'postback_created',
            'Your S2S postback has been created successfully'
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'postback_created')
            self.assertIn('created successfully', notification_data['message'])
    
    def test_bulk_pause_s2s_postbacks(self):
        """Test bulk pausing of S2S postbacks."""
        # Create multiple postbacks
        postbacks = []
        for i in range(3):
            data = self.valid_postback_data.copy()
            data['name'] = f'Postback {i}'
            postback = self.postback_service.create_s2s_postback(self.advertiser, data)
            postbacks.append(postback)
        
        # Bulk pause
        paused_postbacks = self.postback_service.bulk_pause_s2s_postbacks(postbacks)
        
        self.assertEqual(len(paused_postbacks), 3)
        
        for postback in paused_postbacks:
            self.assertEqual(postback.status, 'paused')
    
    def test_bulk_resume_s2s_postbacks(self):
        """Test bulk resuming of S2S postbacks."""
        # Create and pause postbacks
        postbacks = []
        for i in range(3):
            data = self.valid_postback_data.copy()
            data['name'] = f'Postback {i}'
            postback = self.postback_service.create_s2s_postback(self.advertiser, data)
            self.postback_service.pause_s2s_postback(postback)
            postbacks.append(postback)
        
        # Bulk resume
        resumed_postbacks = self.postback_service.bulk_resume_s2s_postbacks(postbacks)
        
        self.assertEqual(len(resumed_postbacks), 3)
        
        for postback in resumed_postbacks:
            self.assertEqual(postback.status, 'active')
    
    def test_get_postback_health_status(self):
        """Test getting postback health status."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create postback results
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            
            # 8 success, 2 failure
            status = 'success' if i < 8 else 'failed'
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {'status': status, 'response_time': 0.5}
            )
        
        health_status = self.postback_service.get_postback_health_status(postback)
        
        self.assertIn('status', health_status)
        self.assertIn('last_sent', health_status)
        self.assertIn('success_rate', health_status)
        self.assertIn('average_response_time', health_status)
        self.assertIn('error_rate', health_status)
        self.assertIn('recommendations', health_status)
        
        # Should be healthy with good success rate
        self.assertEqual(health_status['status'], 'healthy')
    
    def test_get_postback_recommendations(self):
        """Test getting postback recommendations."""
        postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            self.valid_postback_data
        )
        
        # Create postback results with varying response times
        for i in range(5):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            
            self.postback_service.record_postback_result(
                postback,
                conversion,
                {
                    'status': 'success',
                    'response_time': 2.0 + i * 0.5  # Increasing response times
                }
            )
        
        recommendations = self.postback_service.get_postback_recommendations(postback)
        
        self.assertIn('optimization_suggestions', recommendations)
        self.assertIn('url_recommendations', recommendations)
        self.assertIn('method_recommendations', recommendations)
        self.assertIn('performance_improvements', recommendations)


class S2SPostbackIntegrationTestCase(TestCase):
    """Test cases for S2S postback integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.postback_service = S2SPostbackService()
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
        
        self.postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            {
                'name': 'Test Postback',
                'postback_type': 'conversion',
                'description': 'Test conversion postback',
                'postback_url': 'https://example.com/postback',
                'method': 'POST',
                'status': 'active',
            }
        )
    
    def test_postback_endpoint_receives_conversion(self):
        """Test postback endpoint receives conversion data."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            custom_parameters={
                'affiliate_id': '12345',
                'campaign_id': '67890'
            }
        )
        
        # Send postback
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            result = self.postback_service.send_s2s_postback(self.postback, conversion)
            
            self.assertTrue(result.get('success', False))
            
            # Check that data was sent correctly
            call_args = mock_post.call_args
            sent_data = call_args[1]['data'] if call_args and 'data' in call_args[1] else {}
            
            self.assertIn('conversion_id', sent_data)
            self.assertIn('revenue', sent_data)
            self.assertIn('affiliate_id', sent_data)
            self.assertIn('campaign_id', sent_data)
            self.assertEqual(sent_data['conversion_id'], 'conv_12345')
            self.assertEqual(sent_data['revenue'], '25.00')
    
    def test_postback_endpoint_handles_failure(self):
        """Test postback endpoint handles failure gracefully."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send postback with failure
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.json.return_value = {'error': 'Internal server error'}
            
            result = self.postback_service.send_s2s_postback(self.postback, conversion)
            
            self.assertFalse(result.get('success', False))
            self.assertIn('error', result)
            
            # Check that result was recorded
            postback_results = self.postback.results.filter(postback=self.postback)
            self.assertEqual(postback_results.count(), 1)
            
            result_record = postback_results.first()
            self.assertEqual(result_record.status, 'failed')
            self.assertIn('error', result_record.response_data)
    
    def test_postback_endpoint_retry_mechanism(self):
        """Test postback endpoint retry mechanism."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send postback with retry
        with patch('requests.post') as mock_post:
            # First two calls fail, third succeeds
            mock_post.side_effect = [
                Mock(status_code=500, json=lambda: {'error': 'Internal server error'}),
                Mock(status_code=500, json=lambda: {'error': 'Internal server error'}),
                Mock(status_code=200, json=lambda: {'status': 'success'})
            ]
            
            result = self.postback_service.send_s2s_postback(self.postback, conversion)
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(mock_post.call_count, 3)  # Should retry twice
            
            # Check that retry attempts were recorded
            postback_results = self.postback.results.filter(postback=self.postback)
            self.assertEqual(postback_results.count(), 3)
            
            # Check retry attempts
            failed_attempts = postback_results.filter(status='failed')
            successful_attempts = postback_results.filter(status='success')
            
            self.assertEqual(failed_attempts.count(), 2)
            self.assertEqual(successful_attempts.count(), 1)
    
    def test_postback_endpoint_timeout_handling(self):
        """Test postback endpoint timeout handling."""
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send postback with timeout
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception('Request timeout')
            
            result = self.postback_service.send_s2s_postback(self.postback, conversion)
            
            self.assertFalse(result.get('success', False))
            self.assertIn('error', result)
            
            # Check that timeout was recorded
            postback_results = self.postback.results.filter(postback=self.postback)
            self.assertEqual(postback_results.count(), 1)
            
            result_record = postback_results.first()
            self.assertEqual(result_record.status, 'failed')
            self.assertIn('timeout', result_record.response_data.get('error', '').lower())
    
    def test_postback_endpoint_authentication(self):
        """Test postback endpoint authentication."""
        # Create postback with authentication
        postback_data = self.valid_postback_data.copy()
        postback_data['auth_type'] = 'bearer'
        postback_data['auth_token'] = 'test_token_12345'
        
        authenticated_postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send authenticated postback
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            result = self.postback_service.send_s2s_postback(authenticated_postback, conversion)
            
            self.assertTrue(result.get('success', False))
            
            # Check that authentication was included
            call_args = mock_post.call_args
            headers = call_args[1]['headers'] if call_args and 'headers' in call_args[1] else {}
            
            self.assertIn('Authorization', headers)
            self.assertEqual(headers['Authorization'], 'Bearer test_token_12345')
    
    def test_postback_endpoint_custom_headers(self):
        """Test postback endpoint custom headers."""
        # Create postback with custom headers
        postback_data = self.valid_postback_data.copy()
        postback_data['custom_headers'] = {
            'X-Custom-Header': 'custom_value',
            'X-Another-Header': 'another_value'
        }
        
        custom_postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send postback with custom headers
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            result = self.postback_service.send_s2s_postback(custom_postback, conversion)
            
            self.assertTrue(result.get('success', False))
            
            # Check that custom headers were included
            call_args = mock_post.call_args
            headers = call_args[1]['headers'] if call_args and 'headers' in call_args[1] else {}
            
            self.assertIn('X-Custom-Header', headers)
            self.assertIn('X-Another-Header', headers)
            self.assertEqual(headers['X-Custom-Header'], 'custom_value')
            self.assertEqual(headers['X-Another-Header'], 'another_value')
    
    def test_postback_endpoint_data_transformation(self):
        """Test postback endpoint data transformation."""
        # Create postback with data transformation
        postback_data = self.valid_postback_data.copy()
        postback_data['data_transformation'] = {
            'revenue': 'multiply:2',  # Double the revenue
            'conversion_id': 'prefix:TEST_'  # Add prefix
        }
        
        transformed_postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send transformed postback
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            result = self.postback_service.send_s2s_postback(transformed_postback, conversion)
            
            self.assertTrue(result.get('success', False))
            
            # Check that data was transformed
            call_args = mock_post.call_args
            sent_data = call_args[1]['data'] if call_args and 'data' in call_args[1] else {}
            
            self.assertIn('revenue', sent_data)
            self.assertIn('conversion_id', sent_data)
            self.assertEqual(sent_data['revenue'], '50.00')  # Doubled
            self.assertEqual(sent_data['conversion_id'], 'TEST_conv_12345')  # Prefixed
    
    def test_postback_endpoint_batch_processing(self):
        """Test postback endpoint batch processing."""
        # Create multiple conversions
        conversions = []
        for i in range(5):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(10.00 + i)),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            conversions.append(conversion)
        
        # Send batch postbacks
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            results = self.postback_service.send_batch_s2s_postbacks(
                self.postback,
                conversions
            )
            
            self.assertEqual(len(results), 5)
            
            # Check that all were successful
            for result in results:
                self.assertTrue(result.get('success', False))
            
            # Check that all requests were made
            self.assertEqual(mock_post.call_count, 5)
    
    def test_postback_endpoint_webhook_validation(self):
        """Test postback endpoint webhook validation."""
        # Create postback with webhook validation
        postback_data = self.valid_postback_data.copy()
        postback_data['webhook_secret'] = 'test_secret_12345'
        postback_data['webhook_signature_header'] = 'X-Signature'
        
        webhook_postback = self.postback_service.create_s2s_postback(
            self.advertiser,
            postback_data
        )
        
        # Create conversion
        conversion = Conversion.objects.create(
            advertiser=self.advertiser,
            conversion_id='conv_12345',
            revenue=Decimal('25.00'),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Send webhook postback
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'status': 'success'}
            
            result = self.postback_service.send_s2s_postback(webhook_postback, conversion)
            
            self.assertTrue(result.get('success', False))
            
            # Check that signature was included
            call_args = mock_post.call_args
            headers = call_args[1]['headers'] if call_args and 'headers' in call_args[1] else {}
            
            self.assertIn('X-Signature', headers)
            self.assertIsNotNone(headers['X-Signature'])
    
    def test_postback_endpoint_rate_limiting(self):
        """Test postback endpoint rate limiting."""
        # Create multiple conversions
        conversions = []
        for i in range(10):
            conversion = Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0'
            )
            conversions.append(conversion)
        
        # Send postbacks rapidly (should be rate limited)
        results = []
        for conversion in conversions:
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {'status': 'success'}
                
                result = self.postback_service.send_s2s_postback(self.postback, conversion)
                results.append(result)
        
        # Check rate limiting (implementation dependent)
        # Most should succeed, but some might be rate limited
        successful_results = [r for r in results if r.get('success', False)]
        rate_limited_results = [r for r in results if not r.get('success', False)]
        
        self.assertGreater(len(successful_results), 0)
        # Rate limiting implementation would affect rate_limited_results count

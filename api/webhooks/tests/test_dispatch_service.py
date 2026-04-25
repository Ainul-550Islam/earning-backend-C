"""Test Dispatch Service for Webhooks System

This module contains tests for the webhook dispatch service
including webhook emission, retry logic, and error handling.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from requests.exceptions import RequestException, Timeout, ConnectionError

from ..services.core import DispatchService
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)

User = get_user_model()


class DispatchServiceTest(TestCase):
    """Test cases for DispatchService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.dispatch_service = DispatchService()
    
    def test_emit_webhook_success(self):
        """Test successful webhook emission."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z'
        }
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
            
            # Check the call arguments
            call_args = mock_post.call_args
            self.assertEqual(call_args[0][0], self.endpoint.url)
            self.assertEqual(call_args[1]['headers']['Content-Type'], 'application/json')
            self.assertIn('X-Webhook-Signature', call_args[1]['headers'])
            self.assertIn('X-Webhook-Timestamp', call_args[1]['headers'])
    
    def test_emit_webhook_failure(self):
        """Test webhook emission failure."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = '{"error": "Server error"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_timeout(self):
        """Test webhook emission timeout."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Timeout()
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
    
    def test_emit_webhook_connection_error(self):
        """Test webhook emission connection error."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = ConnectionError()
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
    
    def test_emit_webhook_with_custom_headers(self):
        """Test webhook emission with custom headers."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            headers={'X-Custom-Header': 'custom-value'},
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            
            # Check that custom headers are included
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]['headers']['X-Custom-Header'], 'custom-value')
    
    def test_emit_webhook_with_different_methods(self):
        """Test webhook emission with different HTTP methods."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            http_method=HttpMethod.PUT,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.put') as mock_put:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_put.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_put.assert_called_once()
    
    def test_emit_webhook_paused_endpoint(self):
        """Test webhook emission to paused endpoint."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.PAUSED,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_disabled_endpoint(self):
        """Test webhook emission to disabled endpoint."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.DISABLED,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_suspended_endpoint(self):
        """Test webhook emission to suspended endpoint."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.SUSPENDED,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_with_template(self):
        """Test webhook emission with template transformation."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com'
        }
        
        template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "message": "Welcome {{email}}!"}',
            is_active=True,
            created_by=self.user,
        )
        
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            payload_template=template,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            
            # Check that template was applied
            call_args = mock_post.call_args
            payload = json.loads(call_args[1]['data'])
            self.assertEqual(payload['user_id'], 12345)
            self.assertEqual(payload['message'], 'Welcome test@example.com!')
    
    def test_emit_webhook_with_filters(self):
        """Test webhook emission with filters."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com'
        }
        
        # Create filter that should pass
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_with_filters_not_matching(self):
        """Test webhook emission with filters that don't match."""
        event_data = {
            'user_id': 12345,
            'email': 'test@other-domain.com'
        }
        
        # Create filter that should not pass
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_creates_delivery_log(self):
        """Test that webhook emission creates delivery log."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            
            # Check that delivery log was created
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            self.assertEqual(delivery_log.event_type, 'user.created')
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery_log.response_code, 200)
            self.assertEqual(delivery_log.attempt_number, 1)
    
    def test_emit_webhook_creates_failed_delivery_log(self):
        """Test that webhook emission creates failed delivery log."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = '{"error": "Server error"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            
            # Check that delivery log was created
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            self.assertEqual(delivery_log.event_type, 'user.created')
            self.assertEqual(delivery_log.status, DeliveryStatus.FAILED)
            self.assertEqual(delivery_log.response_code, 500)
            self.assertEqual(delivery_log.attempt_number, 1)
    
    def test_emit_webhook_with_retry_logic(self):
        """Test webhook emission with retry logic."""
        event_data = {'user_id': 12345}
        
        # Create delivery log with retry attempt
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload=event_data,
            status=DeliveryStatus.FAILED,
            response_code=500,
            attempt_number=1,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.retry_delivery(delivery_log)
            
            self.assertTrue(success)
            
            # Check that delivery log was updated
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery_log.response_code, 200)
            self.assertEqual(delivery_log.attempt_number, 2)
    
    def test_emit_webhook_retry_exhausted(self):
        """Test webhook emission retry when max attempts exhausted."""
        event_data = {'user_id': 12345}
        
        # Create delivery log with exhausted attempts
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload=event_data,
            status=DeliveryStatus.FAILED,
            response_code=500,
            attempt_number=5,
            max_attempts=5,
            created_by=self.user,
        )
        
        success = self.dispatch_service.retry_delivery(delivery_log)
        
        self.assertFalse(success)
        
        # Check that delivery log was marked as exhausted
        delivery_log.refresh_from_db()
        self.assertEqual(delivery_log.status, DeliveryStatus.EXHAUSTED)
    
    def test_emit_webhook_with_ip_whitelist_allowed(self):
        """Test webhook emission with allowed IP."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            ip_whitelist=['192.168.1.1'],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            with patch('api.webhooks.services.core.get_client_ip') as mock_get_ip:
                mock_get_ip.return_value = '192.168.1.1'
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertTrue(success)
                mock_post.assert_called_once()
    
    def test_emit_webhook_with_ip_whitelist_blocked(self):
        """Test webhook emission with blocked IP."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            ip_whitelist=['192.168.1.1'],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            with patch('api.webhooks.services.core.get_client_ip') as mock_get_ip:
                mock_get_ip.return_value = '192.168.1.2'
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertFalse(success)
                mock_post.assert_not_called()
    
    def test_emit_webhook_with_rate_limit_not_exceeded(self):
        """Test webhook emission when rate limit not exceeded."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            rate_limit_per_min=1000,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            with patch('api.webhooks.services.analytics.RateLimiterService.is_rate_limited') as mock_rate_limit:
                mock_rate_limit.return_value = False
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertTrue(success)
                mock_post.assert_called_once()
    
    def test_emit_webhook_with_rate_limit_exceeded(self):
        """Test webhook emission when rate limit exceeded."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            rate_limit_per_min=1000,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            with patch('api.webhooks.services.analytics.RateLimiterService.is_rate_limited') as mock_rate_limit:
                mock_rate_limit.return_value = True
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertFalse(success)
                mock_post.assert_not_called()
    
    def test_emit_webhook_async(self):
        """Test asynchronous webhook emission."""
        event_data = {'user_id': 12345}
        
        with patch('api.webhooks.tasks.dispatch_event.delay') as mock_task:
            mock_task.return_value = Mock(id='task-123')
            
            success = self.dispatch_service.emit_async(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_task.assert_called_once()
            
            # Check task arguments
            call_args = mock_task.call_args
            self.assertEqual(call_args[1]['endpoint_id'], self.endpoint.id)
            self.assertEqual(call_args[1]['event_type'], 'user.created')
            self.assertEqual(call_args[1]['payload'], event_data)
    
    def test_emit_webhook_batch(self):
        """Test webhook emission in batch."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            results = self.dispatch_service.emit_batch(
                endpoint=self.endpoint,
                event_type='user.created',
                events=events
            )
            
            self.assertEqual(len(results), 3)
            self.assertTrue(all(result['success'] for result in results))
            self.assertEqual(mock_post.call_count, 3)
    
    def test_emit_webhook_batch_with_failures(self):
        """Test webhook emission in batch with some failures."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        with patch('requests.post') as mock_post:
            # First two succeed, third fails
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.text = '{"status": "success"}'
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            
            mock_response_failure = Mock()
            mock_response_failure.status_code = 500
            mock_response_failure.text = '{"error": "Server error"}'
            mock_response_failure.elapsed.total_seconds.return_value = 0.1
            
            mock_post.side_effect = [
                mock_response_success,
                mock_response_success,
                mock_response_failure
            ]
            
            results = self.dispatch_service.emit_batch(
                endpoint=self.endpoint,
                event_type='user.created',
                events=events
            )
            
            self.assertEqual(len(results), 3)
            self.assertTrue(results[0]['success'])
            self.assertTrue(results[1]['success'])
            self.assertFalse(results[2]['success'])
            self.assertEqual(mock_post.call_count, 3)
    
    def test_emit_webhook_with_subscription_filter(self):
        """Test webhook emission with subscription filter."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com'
        }
        
        # Create subscription with filter
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_with_subscription_filter_not_matching(self):
        """Test webhook emission with subscription filter that doesn't match."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com'
        }
        
        # Create subscription with filter that doesn't match
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 54321},
            is_active=True,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_with_inactive_subscription(self):
        """Test webhook emission with inactive subscription."""
        event_data = {'user_id': 12345}
        
        # Create inactive subscription
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=False,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertFalse(success)
            mock_post.assert_not_called()
    
    def test_emit_webhook_with_timeout_configuration(self):
        """Test webhook emission with timeout configuration."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            timeout_seconds=60,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            
            # Check that timeout was set
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]['timeout'], 60)
    
    def test_emit_webhook_with_ssl_verification_disabled(self):
        """Test webhook emission with SSL verification disabled."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            verify_ssl=False,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            
            # Check that SSL verification was disabled
            call_args = mock_post.call_args
            self.assertFalse(call_args[1]['verify'])
    
    def test_emit_webhook_with_max_retries_configuration(self):
        """Test webhook emission with max retries configuration."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            max_retries=10,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        # Create delivery log
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=endpoint,
            event_type='user.created',
            payload=event_data,
            status=DeliveryStatus.FAILED,
            response_code=500,
            attempt_number=1,
            max_attempts=10,
            created_by=self.user,
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.retry_delivery(delivery_log)
            
            self.assertTrue(success)
            
            # Check that attempt number was incremented
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.attempt_number, 2)
            self.assertEqual(delivery_log.max_attempts, 10)
    
    def test_emit_webhook_with_large_payload(self):
        """Test webhook emission with large payload."""
        event_data = {
            'user_id': 12345,
            'large_data': ['x' * 10000] * 100  # ~1MB of data
        }
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_with_unicode_payload(self):
        """Test webhook emission with unicode payload."""
        event_data = {
            'user_id': 12345,
            'message': 'Hello World! ñáéíóú',
            'emoji': 'Hello World! emoji test'
        }
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_with_none_values(self):
        """Test webhook emission with None values in payload."""
        event_data = {
            'user_id': 12345,
            'email': None,
            'profile': None
        }
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_performance(self):
        """Test webhook emission performance."""
        import time
        
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            start_time = time.time()
            
            # Emit 100 webhooks
            for i in range(100):
                success = self.dispatch_service.emit(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': i}
                )
                self.assertTrue(success)
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 5 seconds)
            self.assertLess(end_time - start_time, 5.0)
            self.assertEqual(mock_post.call_count, 100)
    
    def test_emit_webhook_concurrent_safety(self):
        """Test webhook emission concurrent safety."""
        import threading
        
        results = []
        
        def emit_webhook():
            event_data = {'user_id': 12345}
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data
            )
            results.append(success)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=emit_webhook)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All emissions should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result for result in results))

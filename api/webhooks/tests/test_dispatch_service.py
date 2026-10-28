"""Test Dispatch Service for Webhooks System

This module contains tests for the webhook dispatch service
including webhook emission, retry logic, and error handling.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from requests.exceptions import RequestException, Timeout, ConnectionError

from ..services.core.DispatchService import DispatchService
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.dispatch_service = DispatchService()
    
    def test_emit_webhook_success(self):
        """Test successful webhook emission."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z'
        }
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            self.assertEqual(call_args[1]['url'], self.endpoint.target_url)
            self.assertEqual(call_args[1]['headers']['Content-Type'], 'application/json')
            self.assertIn('X-Webhook-Signature', call_args[1]['headers'])
            self.assertIn('X-Webhook-Timestamp', call_args[1]['headers'])
    
    def test_emit_webhook_failure(self):
        """Test webhook emission failure."""
        event_data = {'user_id': 12345}
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        
        with patch('requests.request') as mock_post:
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
        
        with patch('requests.request') as mock_post:
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            custom_headers={'X-Custom-Header': 'custom-value'},
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            http_method=HttpMethod.PUT,
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_request:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_request.return_value = mock_response
            
            success = self.dispatch_service.emit(
                endpoint=endpoint,
                event_type='user.created',
                payload=event_data
            )
            
            self.assertTrue(success)
            mock_request.assert_called_once()
            self.assertEqual(mock_request.call_args[1]['method'], HttpMethod.PUT)
    
    def test_emit_webhook_paused_endpoint(self):
        """Test webhook emission to paused endpoint."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.PAUSED,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.DISABLED,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.SUSPENDED,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
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
            payload_template='{"user_id": {{user_id}}, "message": {{ "Welcome " + email + "!" }}}',
            is_active=True,
        )
        
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            payload_template=template,
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        """Test that emit_to_subscribers respects subscription-level
        filters that don't match.

        Subscription filtering lives in emit_to_subscribers() (via
        EventRouter.route_event -> WebhookSubscription.filters, a JSON
        blob), not in emit() itself - confirmed by reading both. emit() is
        the low-level "dispatch to this specific endpoint" primitive;
        WebhookEmitAPIView's staff-triggered manual dispatch calls it
        directly with zero subscriptions in place, so emit() can't require
        a matching subscription/filter without breaking that
        already-verified path. (The standalone WebhookFilter model, tested
        elsewhere, is exclusively a BatchDispatchService concern - it's
        never consulted by emit_to_subscribers/EventRouter.)
        """
        event_data = {
            'user_id': 12345,
            'email': 'test@other-domain.com'
        }
        
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
            filters={'email': {'operator': FilterOperator.CONTAINS, 'value': '@example.com'}},
        )
        
        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.delay') as mock_delay:
            result = self.dispatch_service.emit_to_subscribers(
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertEqual(result['filtered_subscriptions'], 0)
            mock_delay.assert_not_called()
    
    def test_emit_webhook_creates_delivery_log(self):
        """Test that webhook emission creates delivery log."""
        event_data = {'user_id': 12345}
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            self.assertEqual(delivery_log.http_status_code, 200)
            self.assertEqual(delivery_log.attempt_number, 1)
    
    def test_emit_webhook_creates_failed_delivery_log(self):
        """Test that webhook emission creates failed delivery log."""
        event_data = {'user_id': 12345}
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            self.assertEqual(delivery_log.http_status_code, 500)
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
            http_status_code=500,
            attempt_number=1,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            success = self.dispatch_service.retry_delivery(delivery_log)
            
            self.assertTrue(success)
            
            # Check that delivery log was updated
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery_log.http_status_code, 200)
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
            http_status_code=500,
            attempt_number=5,
            max_attempts=5,
        )
        
        success = self.dispatch_service.retry_delivery(delivery_log)
        
        self.assertFalse(success)
        
        # Check that delivery log was marked as exhausted
        delivery_log.refresh_from_db()
        self.assertEqual(delivery_log.status, DeliveryStatus.EXHAUSTED)
    
    def test_emit_webhook_has_no_ip_whitelist_concept(self):
        """Document that emit() has no IP-whitelist gating.

        The original two tests here mocked
        api.webhooks.services.core.get_client_ip, which does not exist
        anywhere in the codebase (confirmed via introspection), and
        emit(endpoint, event_type, payload) takes no request parameter at
        all - there is no incoming request to pull a client IP from for an
        outbound, server-to-server dispatch. This reads like it was
        written for an inbound webhook-receiving flow and landed in the
        wrong test file. Rather than invent a fake IP-whitelist feature
        with no supporting design anywhere, this documents current, real
        behavior: dispatch proceeds regardless.
        """
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            mock_post.assert_called_once()
    
    def test_emit_webhook_with_rate_limit_not_exceeded(self):
        """Test webhook emission when rate limit not exceeded."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            with patch('api.webhooks.services.analytics.RateLimiterService.RateLimiterService.is_rate_limited') as mock_rate_limit:
                mock_rate_limit.return_value = False
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertTrue(success)
                mock_post.assert_called_once()
    
    def test_emit_webhook_does_not_enforce_rate_limit(self):
        """Document that emit()/DispatchService deliberately does not
        enforce rate limiting.

        Confirmed via an existing comment in tasks/dispatch_event.py:
        "Rate-limit enforcement belongs in the view/serializer layer
        before the task is queued; removed from here to avoid
        AttributeError." The original version of this test expected
        emit() to consult RateLimiterService.is_rate_limited() and block
        dispatch - that would contradict this already-documented,
        deliberate architectural boundary. This locks in current, correct
        behavior instead: dispatch proceeds regardless of rate-limit
        state at this layer.
        """
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            with patch('api.webhooks.services.analytics.RateLimiterService.RateLimiterService.is_rate_limited') as mock_rate_limit:
                mock_rate_limit.return_value = True
                
                success = self.dispatch_service.emit(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload=event_data
                )
                
                self.assertTrue(success)
                mock_post.assert_called_once()
                mock_rate_limit.assert_not_called()
    
    def test_emit_webhook_async(self):
        """Test asynchronous webhook emission."""
        event_data = {'user_id': 12345}
        
        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.delay') as mock_task:
            mock_task.return_value = Mock(id='task-123')
            
            # There is no emit_async() method - async dispatch goes through
            # emit(..., async_emit=True), which calls _emit_async()
            # internally (confirmed by reading the source).
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data,
                async_emit=True,
            )
            
            self.assertTrue(success)
            mock_task.assert_called_once()
            
            # Check task arguments - endpoint_id is passed as str(endpoint.id)
            call_args = mock_task.call_args
            self.assertEqual(call_args[1]['endpoint_id'], str(self.endpoint.id))
            self.assertEqual(call_args[1]['event_type'], 'user.created')
            self.assertEqual(call_args[1]['payload'], event_data)
    
    def test_emit_webhook_batch(self):
        """Test webhook emission in batch."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            # There is no emit_batch() on DispatchService - batch operations
            # live in the dedicated BatchDispatchService. "Batch" here just
            # means calling emit() once per event.
            results = [
                {'success': self.dispatch_service.emit(
                    endpoint=self.endpoint, event_type='user.created', payload=event,
                )}
                for event in events
            ]
            
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
        
        with patch('requests.request') as mock_post:
            # First two succeed, third fails
            mock_response_success = Mock()
            mock_response_success.headers = {}
            mock_response_success.status_code = 200
            mock_response_success.text = '{"status": "success"}'
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            
            mock_response_failure = Mock()
            mock_response_failure.headers = {}
            mock_response_failure.status_code = 500
            mock_response_failure.text = '{"error": "Server error"}'
            mock_response_failure.elapsed.total_seconds.return_value = 0.1
            
            mock_post.side_effect = [
                mock_response_success,
                mock_response_success,
                mock_response_failure
            ]
            
            # There is no emit_batch() on DispatchService (see test_emit_webhook_batch).
            results = [
                {'success': self.dispatch_service.emit(
                    endpoint=self.endpoint, event_type='user.created', payload=event,
                )}
                for event in events
            ]
            
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
            is_active=True,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        """Test that emit_to_subscribers doesn't route to a subscription
        for a different event_type.

        Same relocation rationale as test_emit_webhook_with_filters_not_matching
        above - this is emit_to_subscribers()/EventRouter territory, not
        emit(). The original version of this test had setup identical to
        the (passing) test_emit_webhook_with_subscription_filter, which
        can't genuinely represent a "not matching" case; scoping the
        subscription to a different event_type gives a real, unambiguous
        non-match.
        """
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com'
        }
        
        # Subscribed to a different event_type than what's being emitted
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='payout.success',
            is_active=True,
        )
        
        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.delay') as mock_delay:
            result = self.dispatch_service.emit_to_subscribers(
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertEqual(result['total_subscriptions'], 0)
            mock_delay.assert_not_called()
    
    def test_emit_webhook_with_inactive_subscription(self):
        """Test that emit_to_subscribers doesn't route to an inactive
        subscription.

        Same relocation rationale as the two tests above - EventRouter's
        base queryset filters is_active=True (confirmed by reading
        route_event), so an inactive subscription is excluded before any
        filter evaluation even happens.
        """
        event_data = {'user_id': 12345}
        
        # Create inactive subscription
        WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=False,
        )
        
        with patch('api.webhooks.tasks.dispatch_event.dispatch_event.delay') as mock_delay:
            result = self.dispatch_service.emit_to_subscribers(
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertEqual(result['total_subscriptions'], 0)
            mock_delay.assert_not_called()
    
    def test_emit_webhook_uses_default_timeout(self):
        """Test webhook emission uses the service-level default timeout.

        WebhookEndpoint has no timeout_seconds field - per-endpoint timeout
        configuration was deliberately removed (see the BUG FIX comment in
        DispatchService._dispatch()), so every dispatch uses
        self.default_timeout regardless of the endpoint.
        """
        event_data = {'user_id': 12345}
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            
            # Check that the service's default timeout was used
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]['timeout'], self.dispatch_service.default_timeout)
    
    def test_emit_webhook_with_ssl_verification_disabled(self):
        """Test webhook emission with SSL verification disabled."""
        event_data = {'user_id': 12345}
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            verify_ssl=False,
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            max_retries=10,
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        # Create delivery log
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=endpoint,
            event_type='user.created',
            payload=event_data,
            status=DeliveryStatus.FAILED,
            http_status_code=500,
            attempt_number=1,
            max_attempts=10,
        )
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
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


class DispatchServiceConcurrencyTest(TransactionTestCase):
    """Concurrency tests for DispatchService.

    Split out into its own TransactionTestCase, matching the established
    pattern in test_batch_dispatch.py's BatchServiceTest
    (test_process_batch_concurrent_safety): TestCase wraps each test in an
    outer transaction, which real multi-threaded DB writes under SQLite
    contend with ("database table is locked") since other threads' own
    connections don't share that transaction. TransactionTestCase avoids
    the outer wrapper entirely.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.dispatch_service = DispatchService()

    def test_emit_webhook_concurrent_safety(self):
        """Test webhook emission concurrent safety."""
        import threading
        
        results = []
        
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
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

    def test_retry_delivery_concurrent_safety(self):
        """Regression test for the retry_delivery() read-modify-write race.

        Before the fix: N threads each loading their own copy of the same
        delivery log and calling retry_delivery() would lose increments -
        confirmed empirically (8 concurrent callers starting from
        attempt_number=1 landed on 5, not 9, before the fix in
        DispatchService.retry_delivery()). Each thread here fetches its
        own fresh instance (not a shared Python object) specifically to
        reproduce that scenario, matching how the two real concurrent
        callers (tasks/retry_failed_dispatch.py's scheduled beat-task
        retry and views.py's manual API retry action) each work with
        their own independently-loaded copy.

        Same known flake as WebhookIntegrationConcurrencyTest and
        ReplayServiceConcurrencyTest: can occasionally hit "database table
        is locked" under full-suite load (observed ~1/8 runs alongside
        other files' concurrency tests, 0/13 otherwise) even inside this
        TransactionTestCase - SQLite-under-test-load contention, not a
        code defect. Re-run alone before assuming something broke.
        """
        import threading

        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            attempt_number=1,
            max_attempts=20,  # headroom so no thread hits EXHAUSTED
        )

        n_threads = 8
        results = []
        errors = []

        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response

            def retry_once():
                try:
                    # Fresh fetch per thread - a separate in-memory copy,
                    # like two independent real-world callers would have.
                    own_copy = WebhookDeliveryLog.objects.get(pk=delivery_log.pk)
                    results.append(self.dispatch_service.retry_delivery(own_copy))
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(exc)

            threads = [threading.Thread(target=retry_once) for _ in range(n_threads)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), n_threads)
        self.assertTrue(all(results), "every retry should have been claimed and dispatched")

        delivery_log.refresh_from_db()
        self.assertEqual(
            delivery_log.attempt_number, 1 + n_threads,
            "no increment should be lost under concurrent retries",
        )
        self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
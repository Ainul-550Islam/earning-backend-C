"""Integration Tests for Webhooks System

This module contains integration tests for the complete webhook system
including end-to-end workflows, emit->deliver->retry->replay flow, and system integration.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    WebhookAnalytics, WebhookHealthLog, WebhookReplay, WebhookReplayBatch
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)

User = get_user_model()


class WebhookIntegrationTest(TestCase):
    """Integration tests for the complete webhook system."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
            created_by=self.user,
        )
    
    def test_complete_webhook_flow_success(self):
        """Test complete webhook flow: emit -> deliver -> success."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            # Emit webhook
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(emit_response.data['success'])
            
            # Check delivery log was created
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            self.assertEqual(delivery_log.event_type, 'user.created')
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery_log.response_code, 200)
            self.assertEqual(delivery_log.attempt_number, 1)
            
            # Check endpoint statistics were updated
            self.endpoint.refresh_from_db()
            self.assertEqual(self.endpoint.total_deliveries, 1)
            self.assertEqual(self.endpoint.success_deliveries, 1)
            self.assertEqual(self.endpoint.failed_deliveries, 0)
    
    def test_complete_webhook_flow_with_retry(self):
        """Test complete webhook flow: emit -> deliver -> fail -> retry -> success."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            # First call fails, second succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = '{"error": "Server error"}'
            mock_response_fail.elapsed.total_seconds.return_value = 0.1
            
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.text = '{"status": "success"}'
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            
            mock_post.side_effect = [mock_response_fail, mock_response_success]
            
            # Emit webhook
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])  # First attempt failed
            
            # Retry the delivery
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            retry_url = f'/api/webhooks/delivery-logs/{delivery_log.id}/retry/'
            retry_response = self.client.post(retry_url)
            
            self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
            self.assertTrue(retry_response.data['success'])
            
            # Check delivery log was updated
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(delivery_log.response_code, 200)
            self.assertEqual(delivery_log.attempt_number, 2)
            
            # Check endpoint statistics were updated
            self.endpoint.refresh_from_db()
            self.assertEqual(self.endpoint.total_deliveries, 2)
            self.assertEqual(self.endpoint.success_deliveries, 1)
            self.assertEqual(self.endpoint.failed_deliveries, 1)
    
    def test_complete_webhook_flow_with_filters(self):
        """Test complete webhook flow with filters: emit -> filter -> deliver -> success."""
        # Create filter
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        payload = {'user_id': 12345, 'user_email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            # Emit webhook
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(emit_response.data['success'])
            
            # Check delivery log was created
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            self.assertEqual(delivery_log.event_type, 'user.created')
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
    
    def test_complete_webhook_flow_with_filters_blocked(self):
        """Test complete webhook flow with filters that block the event."""
        # Create filter
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        payload = {'user_id': 12345, 'user_email': 'test@other.com'}
        
        with patch('requests.post') as mock_post:
            # Emit webhook
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])  # Blocked by filter
            
            # Check no delivery log was created
            with self.assertRaises(WebhookDeliveryLog.DoesNotExist):
                WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
    
    def test_complete_webhook_flow_with_template(self):
        """Test complete webhook flow with template transformation."""
        # Create template
        template = WebhookTemplate.objects.create(
            name='User Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "message": "Welcome {{user_email}}!"}',
            is_active=True,
            created_by=self.user,
        )
        
        # Update endpoint with template
        self.endpoint.payload_template = template
        self.endpoint.save()
        
        payload = {'user_id': 12345, 'user_email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            # Emit webhook
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(emit_response.data['success'])
            
            # Check that template was applied
            call_args = mock_post.call_args
            sent_payload = json.loads(call_args[1]['data'])
            self.assertEqual(sent_payload['user_id'], 12345)
            self.assertEqual(sent_payload['message'], 'Welcome test@example.com!')
    
    def test_complete_webhook_flow_with_batch(self):
        """Test complete webhook flow with batch processing."""
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
            
            # Create batch
            batch_data = {
                'endpoint_id': self.endpoint.id,
                'event_type': 'user.created',
                'events': events
            }
            
            batch_url = '/api/webhooks/batches/'
            batch_response = self.client.post(batch_url, batch_data, format='json')
            
            self.assertEqual(batch_response.status_code, status.HTTP_201_CREATED)
            batch_id = batch_response.data['id']
            
            # Process batch
            process_url = f'/api/webhooks/batches/{batch_id}/process/'
            process_response = self.client.post(process_url)
            
            self.assertEqual(process_response.status_code, status.HTTP_200_OK)
            self.assertTrue(process_response.data['success'])
            self.assertEqual(process_response.data['processed_count'], 3)
            self.assertEqual(process_response.data['success_count'], 3)
            self.assertEqual(process_response.data['failed_count'], 0)
            
            # Check that 3 delivery logs were created
            delivery_logs = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint)
            self.assertEqual(delivery_logs.count(), 3)
    
    def test_complete_webhook_flow_with_replay(self):
        """Test complete webhook flow: emit -> fail -> replay -> success."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            # First call fails
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = '{"error": "Server error"}'
            mock_response_fail.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response_fail
            
            # Emit webhook (fails)
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])
            
            # Get failed delivery log
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=self.endpoint)
            
            # Create replay
            replay_data = {
                'original_log_id': delivery_log.id,
                'reason': 'Test replay'
            }
            
            replay_url = '/api/webhooks/replays/'
            replay_response = self.client.post(replay_url, replay_data, format='json')
            
            self.assertEqual(replay_response.status_code, status.HTTP_201_CREATED)
            replay_id = replay_response.data['id']
            
            # Process replay (now succeeds)
            mock_post.return_value = Mock(
                status_code=200,
                text='{"status": "success"}',
                elapsed=Mock(total_seconds=lambda: 0.1)
            )
            
            process_url = f'/api/webhooks/replays/{replay_id}/process/'
            process_response = self.client.post(process_url)
            
            self.assertEqual(process_response.status_code, status.HTTP_200_OK)
            self.assertTrue(process_response.data['success'])
            
            # Check replay was successful
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.status, DeliveryStatus.FAILED)  # Original still failed
            
            replay = WebhookReplay.objects.get(id=replay_id)
            self.assertEqual(replay.status, ReplayStatus.COMPLETED)
            self.assertIsNotNone(replay.new_log)
            self.assertEqual(replay.new_log.status, DeliveryStatus.SUCCESS)
    
    def test_complete_webhook_flow_with_batch_replay(self):
        """Test complete webhook flow with batch replay."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'}
        ]
        
        with patch('requests.post') as mock_post:
            # All calls fail initially
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = '{"error": "Server error"}'
            mock_response_fail.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response_fail
            
            # Create and process batch (all fail)
            batch_data = {
                'endpoint_id': self.endpoint.id,
                'event_type': 'user.created',
                'events': events
            }
            
            batch_url = '/api/webhooks/batches/'
            batch_response = self.client.post(batch_url, batch_data, format='json')
            batch_id = batch_response.data['id']
            
            process_url = f'/api/webhooks/batches/{batch_id}/process/'
            process_response = self.client.post(process_url)
            
            self.assertEqual(process_response.status_code, status.HTTP_200_OK)
            self.assertEqual(process_response.data['failed_count'], 2)
            
            # Get failed delivery logs
            failed_logs = WebhookDeliveryLog.objects.filter(
                endpoint=self.endpoint,
                status=DeliveryStatus.FAILED
            )
            self.assertEqual(failed_logs.count(), 2)
            
            # Create replay batch
            replay_batch_data = {
                'delivery_log_ids': [log.id for log in failed_logs],
                'reason': 'Batch replay test'
            }
            
            replay_batch_url = '/api/webhooks/replay-batches/'
            replay_batch_response = self.client.post(replay_batch_url, replay_batch_data, format='json')
            
            self.assertEqual(replay_batch_response.status_code, status.HTTP_201_CREATED)
            replay_batch_id = replay_batch_response.data['id']
            
            # Process replay batch (now succeeds)
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.text = '{"status": "success"}'
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response_success
            
            process_replay_url = f'/api/webhooks/replay-batches/{replay_batch_id}/process/'
            process_replay_response = self.client.post(process_replay_url)
            
            self.assertEqual(process_replay_response.status_code, status.HTTP_200_OK)
            self.assertTrue(process_replay_response.data['success'])
            self.assertEqual(process_replay_response.data['success_count'], 2)
    
    def test_complete_webhook_flow_with_health_check(self):
        """Test complete webhook flow with health check integration."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            # Perform health check
            health_url = f'/api/webhooks/endpoints/{self.endpoint.id}/health-check/'
            health_response = self.client.post(health_url)
            
            self.assertEqual(health_response.status_code, status.HTTP_200_OK)
            self.assertTrue(health_response.data['is_healthy'])
            self.assertEqual(health_response.data['status_code'], 200)
            
            # Check health log was created
            health_log = WebhookHealthLog.objects.get(endpoint=self.endpoint)
            self.assertTrue(health_log.is_healthy)
            self.assertEqual(health_log.status_code, 200)
            self.assertEqual(health_log.response_time_ms, 100)
    
    def test_complete_webhook_flow_with_analytics(self):
        """Test complete webhook flow with analytics integration."""
        # Create multiple delivery logs
        for i in range(10):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS if i < 8 else DeliveryStatus.FAILED,
                response_code=200 if i < 8 else 500,
                duration_ms=100 + i * 10,
                created_at=timezone.now() - timedelta(hours=i),
                created_by=self.user,
            )
        
        # Generate analytics
        analytics_url = f'/api/webhooks/endpoints/{self.endpoint.id}/analytics/'
        analytics_response = self.client.get(analytics_url)
        
        self.assertEqual(analytics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(analytics_response.data['total_sent'], 10)
        self.assertEqual(analytics_response.data['success_count'], 8)
        self.assertEqual(analytics_response.data['failed_count'], 2)
        self.assertEqual(analytics_response.data['success_rate'], 80.0)
    
    def test_complete_webhook_flow_with_rate_limiting(self):
        """Test complete webhook flow with rate limiting."""
        # Create rate limit
        WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=5,
            current_count=5,  # Already at limit
            reset_at=timezone.now() + timedelta(minutes=1),
            created_by=self.user,
        )
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            # Emit webhook (should be rate limited)
            emit_data = {
                'event_type': 'user.created',
                'payload': payload,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])
            self.assertIn('rate limited', emit_response.data.get('error', '').lower())
    
    def test_complete_webhook_flow_with_secret_rotation(self):
        """Test complete webhook flow with secret rotation."""
        old_secret = self.endpoint.secret
        
        # Rotate secret
        rotate_url = f'/api/webhooks/endpoints/{self.endpoint.id}/rotate-secret/'
        rotate_response = self.client.post(rotate_url)
        
        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)
        self.assertIn('new_secret', rotate_response.data)
        self.assertNotEqual(rotate_response.data['new_secret'], old_secret)
        
        # Check endpoint was updated
        self.endpoint.refresh_from_db()
        self.assertNotEqual(self.endpoint.secret, old_secret)
        
        # Check old secret was archived
        archived_secret = WebhookSecret.objects.get(endpoint=self.endpoint)
        self.assertEqual(archived_secret.is_active, False)
    
    def test_complete_webhook_flow_with_subscription_management(self):
        """Test complete webhook flow with subscription management."""
        # Create additional subscription
        subscription_data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.updated',
            'is_active': True,
            'filter_config': {
                'user.status': {
                    'operator': 'equals',
                    'value': 'active'
                }
            }
        }
        
        subscription_url = '/api/webhooks/subscriptions/'
        subscription_response = self.client.post(subscription_url, subscription_data, format='json')
        
        self.assertEqual(subscription_response.status_code, status.HTTP_201_CREATED)
        subscription_id = subscription_response.data['id']
        
        # Test with different event types
        payload_active = {'user_id': 12345, 'user_status': 'active'}
        payload_inactive = {'user_id': 12346, 'user_status': 'inactive'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            # Emit active user event (should be delivered)
            emit_data = {
                'event_type': 'user.updated',
                'payload': payload_active,
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(emit_response.data['success'])
            
            # Emit inactive user event (should be filtered)
            emit_data['payload'] = payload_inactive
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])
    
    def test_complete_webhook_flow_error_handling(self):
        """Test complete webhook flow with comprehensive error handling."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            # Test various error scenarios
            error_scenarios = [
                (Exception('Connection error'), 'connection error'),
                (Timeout(), 'timeout'),
                (Mock(status_code=500, text='Server error'), 'server error'),
                (Mock(status_code=404, text='Not found'), 'not found'),
                (Mock(status_code=401, text='Unauthorized'), 'unauthorized'),
            ]
            
            for error, expected_error_type in error_scenarios:
                mock_post.side_effect = error if isinstance(error, Exception) else error
                
                # Emit webhook
                emit_data = {
                    'event_type': 'user.created',
                    'payload': payload,
                    'endpoint_id': self.endpoint.id,
                    'async_emit': False
                }
                
                emit_url = '/api/webhooks/emit/'
                emit_response = self.client.post(emit_url, emit_data, format='json')
                
                self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
                self.assertFalse(emit_response.data['success'])
                
                # Check error was properly logged
                delivery_log = WebhookDeliveryLog.objects.filter(
                    endpoint=self.endpoint,
                    event_type='user.created'
                ).latest('created_at')
                
                self.assertEqual(delivery_log.status, DeliveryStatus.FAILED)
                self.assertIsNotNone(delivery_log.error_message)
    
    def test_complete_webhook_flow_performance(self):
        """Test complete webhook flow performance."""
        import time
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            start_time = time.time()
            
            # Emit 100 webhooks
            for i in range(100):
                emit_data = {
                    'event_type': 'user.created',
                    'payload': {**payload, 'user_id': 12345 + i},
                    'endpoint_id': self.endpoint.id,
                    'async_emit': False
                }
                
                emit_url = '/api/webhooks/emit/'
                emit_response = self.client.post(emit_url, emit_data, format='json')
                
                self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
                self.assertTrue(emit_response.data['success'])
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 5 seconds)
            self.assertLess(end_time - start_time, 5.0)
            
            # Check all delivery logs were created
            delivery_logs = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint)
            self.assertEqual(delivery_logs.count(), 100)
            self.assertTrue(all(log.status == DeliveryStatus.SUCCESS for log in delivery_logs))
    
    def test_complete_webhook_flow_concurrent_requests(self):
        """Test complete webhook flow with concurrent requests."""
        import threading
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            results = []
            
            def emit_webhook():
                emit_data = {
                    'event_type': 'user.created',
                    'payload': payload,
                    'endpoint_id': self.endpoint.id,
                    'async_emit': False
                }
                
                emit_url = '/api/webhooks/emit/'
                emit_response = self.client.post(emit_url, emit_data, format='json')
                results.append(emit_response.status_code)
            
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
            
            # All requests should succeed
            self.assertEqual(len(results), 10)
            self.assertTrue(all(status == status.HTTP_200_OK for status in results))
            
            # Check all delivery logs were created
            delivery_logs = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint)
            self.assertEqual(delivery_logs.count(), 10)
            self.assertTrue(all(log.status == DeliveryStatus.SUCCESS for log in delivery_logs))


class WebhookSystemIntegrationTest(TestCase):
    """Integration tests for the entire webhook system."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def test_end_to_end_webhook_system(self):
        """Test end-to-end webhook system functionality."""
        # Create endpoint
        endpoint_data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'status': WebhookStatus.ACTIVE,
            'http_method': HttpMethod.POST,
            'timeout_seconds': 30,
            'max_retries': 3,
            'verify_ssl': True,
            'rate_limit_per_min': 1000,
            'label': 'Test Endpoint',
            'description': 'A test webhook endpoint'
        }
        
        endpoint_url = '/api/webhooks/endpoints/'
        endpoint_response = self.client.post(endpoint_url, endpoint_data, format='json')
        
        self.assertEqual(endpoint_response.status_code, status.HTTP_201_CREATED)
        endpoint_id = endpoint_response.data['id']
        
        # Create subscription
        subscription_data = {
            'endpoint': endpoint_id,
            'event_type': 'user.created',
            'is_active': True,
            'filter_config': {
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                }
            }
        }
        
        subscription_url = '/api/webhooks/subscriptions/'
        subscription_response = self.client.post(subscription_url, subscription_data, format='json')
        
        self.assertEqual(subscription_response.status_code, status.HTTP_201_CREATED)
        
        # Create template
        template_data = {
            'name': 'User Template',
            'event_type': 'user.created',
            'payload_template': '{"user_id": {{user_id}}, "message": "Welcome {{user_email}}!"}',
            'is_active': True
        }
        
        template_url = '/api/webhooks/templates/'
        template_response = self.client.post(template_url, template_data, format='json')
        
        self.assertEqual(template_response.status_code, status.HTTP_201_CREATED)
        template_id = template_response.data['id']
        
        # Update endpoint with template
        update_data = {'payload_template': template_id}
        update_url = f'/api/webhooks/endpoints/{endpoint_id}/'
        update_response = self.client.patch(update_url, update_data, format='json')
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # Emit webhook
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"status": "success"}'
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_post.return_value = mock_response
            
            emit_data = {
                'event_type': 'user.created',
                'payload': {'user_id': 12345, 'user_email': 'test@example.com'},
                'endpoint_id': endpoint_id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(emit_response.data['success'])
        
        # Check analytics
        analytics_url = f'/api/webhooks/endpoints/{endpoint_id}/analytics/'
        analytics_response = self.client.get(analytics_url)
        
        self.assertEqual(analytics_response.status_code, status.HTTP_200_OK)
        self.assertEqual(analytics_response.data['total_sent'], 1)
        self.assertEqual(analytics_response.data['success_count'], 1)
        self.assertEqual(analytics_response.data['success_rate'], 100.0)
        
        # Check health
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            health_url = f'/api/webhooks/endpoints/{endpoint_id}/health-check/'
            health_response = self.client.post(health_url)
            
            self.assertEqual(health_response.status_code, status.HTTP_200_OK)
            self.assertTrue(health_response.data['is_healthy'])
        
        # Rotate secret
        rotate_url = f'/api/webhooks/endpoints/{endpoint_id}/rotate-secret/'
        rotate_response = self.client.post(rotate_url)
        
        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)
        self.assertIn('new_secret', rotate_response.data)
        
        # Verify all components are working together
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
        self.assertEqual(endpoint.total_deliveries, 1)
        self.assertEqual(endpoint.success_deliveries, 1)
        self.assertEqual(endpoint.failed_deliveries, 0)
        
        subscription = WebhookSubscription.objects.get(endpoint=endpoint)
        self.assertEqual(subscription.event_type, 'user.created')
        self.assertTrue(subscription.is_active)
        
        template = WebhookTemplate.objects.get(id=template_id)
        self.assertEqual(template.event_type, 'user.created')
        self.assertTrue(template.is_active)
        
        delivery_log = WebhookDeliveryLog.objects.get(endpoint=endpoint)
        self.assertEqual(delivery_log.event_type, 'user.created')
        self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
        
        health_log = WebhookHealthLog.objects.get(endpoint=endpoint)
        self.assertTrue(health_log.is_healthy)
        self.assertEqual(health_log.status_code, 200)
        
        archived_secret = WebhookSecret.objects.get(endpoint=endpoint)
        self.assertEqual(archived_secret.is_active, False)
    
    def test_webhook_system_error_recovery(self):
        """Test webhook system error recovery mechanisms."""
        # Create endpoint
        endpoint_data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'status': WebhookStatus.ACTIVE,
            'max_retries': 3
        }
        
        endpoint_url = '/api/webhooks/endpoints/'
        endpoint_response = self.client.post(endpoint_url, endpoint_data, format='json')
        
        self.assertEqual(endpoint_response.status_code, status.HTTP_201_CREATED)
        endpoint_id = endpoint_response.data['id']
        
        # Create subscription
        subscription_data = {
            'endpoint': endpoint_id,
            'event_type': 'user.created',
            'is_active': True
        }
        
        subscription_url = '/api/webhooks/subscriptions/'
        subscription_response = self.client.post(subscription_url, subscription_data, format='json')
        
        self.assertEqual(subscription_response.status_code, status.HTTP_201_CREATED)
        
        # Test failure and recovery
        with patch('requests.post') as mock_post:
            # First two attempts fail, third succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = '{"error": "Server error"}'
            mock_response_fail.elapsed.total_seconds.return_value = 0.1
            
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.text = '{"status": "success"}'
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            
            mock_post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]
            
            # Emit webhook (fails)
            emit_data = {
                'event_type': 'user.created',
                'payload': {'user_id': 12345},
                'endpoint_id': endpoint_id,
                'async_emit': False
            }
            
            emit_url = '/api/webhooks/emit/'
            emit_response = self.client.post(emit_url, emit_data, format='json')
            
            self.assertEqual(emit_response.status_code, status.HTTP_200_OK)
            self.assertFalse(emit_response.data['success'])
            
            # Retry first time (fails)
            delivery_log = WebhookDeliveryLog.objects.get(endpoint=endpoint_id)
            retry_url = f'/api/webhooks/delivery-logs/{delivery_log.id}/retry/'
            retry_response = self.client.post(retry_url)
            
            self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
            self.assertFalse(retry_response.data['success'])
            
            # Retry second time (succeeds)
            retry_response = self.client.post(retry_url)
            
            self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
            self.assertTrue(retry_response.data['success'])
            
            # Verify recovery
            delivery_log.refresh_from_db()
            self.assertEqual(delivery_log.status, DeliveryStatus.FAILED)  # Original still failed
            self.assertEqual(delivery_log.attempt_number, 1)
            
            replay = WebhookReplay.objects.get(original_log=delivery_log)
            self.assertEqual(replay.status, ReplayStatus.COMPLETED)
            self.assertEqual(replay.new_log.status, DeliveryStatus.SUCCESS)
            self.assertEqual(replay.new_log.attempt_number, 3)
            
            # Check endpoint statistics
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
            self.assertEqual(endpoint.total_deliveries, 3)
            self.assertEqual(endpoint.success_deliveries, 1)
            self.assertEqual(endpoint.failed_deliveries, 2)

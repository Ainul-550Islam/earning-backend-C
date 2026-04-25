"""Test ViewSets for Webhooks System

This module contains tests for all webhook viewsets
including core viewsets, advanced features, analytics, and replay functionality.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import Mock, patch
from django.utils import timezone

from ...models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ...constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)

User = get_user_model()


class WebhookEndpointViewSetTest(APITestCase):
    """Test cases for WebhookEndpointViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_endpoints(self):
        """Test listing webhook endpoints."""
        url = reverse('webhookendpoint-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_endpoint(self):
        """Test creating a webhook endpoint."""
        url = reverse('webhookendpoint-list')
        data = {
            'url': 'https://example.com/new-webhook',
            'secret': 'new-secret',
            'status': WebhookStatus.ACTIVE,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['url'], 'https://example.com/new-webhook')
        self.assertEqual(response.data['secret'], 'new-secret')
    
    def test_retrieve_endpoint(self):
        """Test retrieving a specific webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.endpoint.id)
        self.assertEqual(response.data['url'], self.endpoint.url)
    
    def test_update_endpoint(self):
        """Test updating a webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        data = {
            'url': 'https://example.com/updated-webhook',
            'status': WebhookStatus.PAUSED,
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['url'], 'https://example.com/updated-webhook')
        self.assertEqual(response.data['status'], WebhookStatus.PAUSED)
    
    def test_delete_endpoint(self):
        """Test deleting a webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WebhookEndpoint.objects.filter(id=self.endpoint.id).exists())
    
    def test_test_endpoint_action(self):
        """Test testing webhook endpoint action."""
        url = reverse('webhookendpoint-test', kwargs={'pk': self.endpoint.id})
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
        }
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_rotate_secret_action(self):
        """Test rotating webhook secret action."""
        url = reverse('webhookendpoint-rotate-secret', kwargs={'pk': self.endpoint.id})
        
        with patch('api.webhooks.services.core.SecretRotationService.rotate_secret') as mock_rotate:
            mock_rotate.return_value = {
                'new_secret_hash': 'new-hash',
                'old_secret_expires_at': timezone.now() + timezone.timedelta(days=7),
            }
            
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('new_secret_hash', response.data)
            mock_rotate.assert_called_once()
    
    def test_pause_endpoint_action(self):
        """Test pausing webhook endpoint action."""
        url = reverse('webhookendpoint-pause', kwargs={'pk': self.endpoint.id})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check endpoint status
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.PAUSED)
    
    def test_resume_endpoint_action(self):
        """Test resuming webhook endpoint action."""
        # First pause the endpoint
        self.endpoint.status = WebhookStatus.PAUSED
        self.endpoint.save()
        
        url = reverse('webhookendpoint-resume', kwargs={'pk': self.endpoint.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check endpoint status
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.ACTIVE)
    
    def test_health_status_action(self):
        """Test getting health status action."""
        url = reverse('webhookendpoint-health-status', kwargs={'pk': self.endpoint.id})
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.get_endpoint_health_summary') as mock_health:
            mock_health.return_value = {
                'uptime_percentage': 95.0,
                'avg_response_time_ms': 150.0,
                'total_checks': 100,
                'healthy_checks': 95,
            }
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_health.assert_called_once()


class WebhookSubscriptionViewSetTest(APITestCase):
    """Test cases for WebhookSubscriptionViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_subscriptions(self):
        """Test listing webhook subscriptions."""
        url = reverse('webhooksubscription-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_subscription(self):
        """Test creating a webhook subscription."""
        url = reverse('webhooksubscription-list')
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'filter_config': {'user_id': 12345},
            'is_active': True,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_type'], 'user.created')
        self.assertEqual(response.data['filter_config'], {'user_id': 12345})
    
    def test_retrieve_subscription(self):
        """Test retrieving a specific webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        url = reverse('webhooksubscription-detail', kwargs={'pk': subscription.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], subscription.id)
    
    def test_update_subscription(self):
        """Test updating a webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        url = reverse('webhooksubscription-detail', kwargs={'pk': subscription.id})
        data = {
            'is_active': False,
            'filter_config': {'user_id': 54321},
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_active'], False)
        self.assertEqual(response.data['filter_config'], {'user_id': 54321})
    
    def test_delete_subscription(self):
        """Test deleting a webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        url = reverse('webhooksubscription-detail', kwargs={'pk': subscription.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WebhookSubscription.objects.filter(id=subscription.id).exists())


class WebhookDeliveryLogViewSetTest(APITestCase):
    """Test cases for WebhookDeliveryLogViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_delivery_logs(self):
        """Test listing webhook delivery logs."""
        url = reverse('webhookdeliverylog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_retrieve_delivery_log(self):
        """Test retrieving a specific webhook delivery log."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            attempt_number=1,
            created_by=self.user,
        )
        
        url = reverse('webhookdeliverylog-detail', kwargs={'pk': log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], log.id)
    
    def test_filter_delivery_logs(self):
        """Test filtering webhook delivery logs."""
        # Create multiple logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS if i < 3 else DeliveryStatus.FAILED,
                response_code=200 if i < 3 else 500,
                attempt_number=1,
                created_by=self.user,
            )
        
        url = reverse('webhookdeliverylog-list')
        response = self.client.get(url, {'status': DeliveryStatus.SUCCESS})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only successful logs are returned
        for result in response.data['results']:
            self.assertEqual(result['status'], DeliveryStatus.SUCCESS)
    
    def test_filter_by_endpoint(self):
        """Test filtering delivery logs by endpoint."""
        # Create another endpoint
        other_endpoint = WebhookEndpoint.objects.create(
            url='https://other.example.com/webhook',
            secret='other-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        # Create logs for both endpoints
        WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            attempt_number=1,
            created_by=self.user,
        )
        
        WebhookDeliveryLog.objects.create(
            endpoint=other_endpoint,
            event_type='user.created',
            payload={'user_id': 54321},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            attempt_number=1,
            created_by=self.user,
        )
        
        url = reverse('webhookdeliverylog-list')
        response = self.client.get(url, {'endpoint': self.endpoint.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only logs for the specified endpoint are returned
        for result in response.data['results']:
            self.assertEqual(result['endpoint'], self.endpoint.id)


class WebhookAnalyticsViewSetTest(APITestCase):
    """Test cases for WebhookAnalyticsViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_analytics(self):
        """Test listing webhook analytics."""
        url = reverse('webhookanalytics-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_health_summary_action(self):
        """Test getting health summary action."""
        url = reverse('webhookanalytics-health-summary')
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.get_endpoint_health_summary') as mock_health:
            mock_health.return_value = {
                'uptime_percentage': 95.0,
                'avg_response_time_ms': 150.0,
                'total_checks': 100,
                'healthy_checks': 95,
            }
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_health.assert_called_once()
    
    def test_performance_report_action(self):
        """Test getting performance report action."""
        url = reverse('webhookanalytics-performance-report')
        
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.get_performance_metrics') as mock_performance:
            mock_performance.return_value = {
                'total_sent': 1000,
                'total_success': 950,
                'total_failed': 50,
                'avg_latency_ms': 150.0,
                'overall_success_rate': 95.0,
            }
            
            response = self.client.get(url, {'days': 30})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_performance.assert_called_once()
    
    def test_event_statistics_action(self):
        """Test getting event statistics action."""
        url = reverse('webhookanalytics-event-stats')
        
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.get_event_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_events': 500,
                'successful_events': 475,
                'failed_events': 25,
                'success_rate': 95.0,
            }
            
            response = self.client.get(url, {'days': 30, 'event_type': 'user.created'})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_stats.assert_called_once()
    
    def test_export_csv_action(self):
        """Test exporting analytics data as CSV."""
        url = reverse('webhookanalytics-export-csv')
        
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.export_csv') as mock_export:
            mock_export.return_value = 'csv,data'
            
            response = self.client.get(url, {'days': 30})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response['Content-Type'], 'text/csv')
            mock_export.assert_called_once()


class WebhookReplayViewSetTest(APITestCase):
    """Test cases for WebhookReplayViewSet."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_replay_batch_action(self):
        """Test creating replay batch action."""
        url = reverse('webhookreplay-create-batch')
        data = {
            'event_type': 'user.created',
            'date_from': '2024-01-01',
            'date_to': '2024-01-31',
            'batch_size': 100,
        }
        
        with patch('api.webhooks.services.replay.ReplayService.create_replay_batch') as mock_replay:
            mock_replay.return_value = {
                'batch': Mock(id='TEST-BATCH-001'),
                'event_count': 50,
            }
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(response.data['success'])
            self.assertIn('batch_id', response.data)
            mock_replay.assert_called_once()
    
    def test_start_batch_action(self):
        """Test starting batch processing action."""
        url = reverse('webhookreplay-start-batch')
        data = {
            'batch_id': 'TEST-BATCH-001',
        }
        
        with patch('api.webhooks.services.replay.ReplayService.start_batch_processing') as mock_start:
            mock_start.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_start.assert_called_once()
    
    def test_batch_progress_action(self):
        """Test getting batch progress action."""
        url = reverse('webhookreplay-batch-progress')
        
        with patch('api.webhooks.services.replay.ReplayService.get_batch_progress') as mock_progress:
            mock_progress.return_value = {
                'total_items': 100,
                'processed_items': 75,
                'completion_percentage': 75.0,
            }
            
            response = self.client.get(url, {'batch_id': 'TEST-BATCH-001'})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_progress.assert_called_once()
    
    def test_cancel_batch_action(self):
        """Test cancelling batch action."""
        url = reverse('webhookreplay-cancel-batch')
        data = {
            'batch_id': 'TEST-BATCH-001',
            'reason': 'Test cancellation',
        }
        
        with patch('api.webhooks.services.replay.ReplayService.cancel_batch') as mock_cancel:
            mock_cancel.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_cancel.assert_called_once()
    
    def test_replay_history_action(self):
        """Test getting replay history action."""
        url = reverse('webhookreplay-replay-history')
        
        with patch('api.webhooks.services.replay.ReplayService.get_replay_history') as mock_history:
            mock_history.return_value = [
                {
                    'id': 1,
                    'event_type': 'user.created',
                    'status': ReplayStatus.COMPLETED,
                    'created_at': '2024-01-01T00:00:00Z',
                }
            ]
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_history.assert_called_once()
    
    def test_replay_statistics_action(self):
        """Test getting replay statistics action."""
        url = reverse('webhookreplay-replay-statistics')
        
        with patch('api.webhooks.services.replay.ReplayService.get_replay_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_replays': 100,
                'completed_replays': 95,
                'failed_replays': 5,
                'success_rate': 95.0,
            }
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('data', response.data)
            mock_stats.assert_called_once()


class WebhookEmitAPIViewTest(APITestCase):
    """Test cases for WebhookEmitAPIView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_emit_webhook(self):
        """Test emitting a webhook."""
        url = reverse('webhookemit-list')
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': self.endpoint.id,
        }
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_emit_webhook_async(self):
        """Test emitting a webhook asynchronously."""
        url = reverse('webhookemit-list')
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': self.endpoint.id,
            'async_emit': True,
        }
        
        with patch('api.webhooks.services.core.DispatchService.emit_async') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_emit_webhook_validation(self):
        """Test webhook emission validation."""
        url = reverse('webhookemit-list')
        data = {
            'event_type': '',  # Invalid: empty event type
            'payload': {'user_id': 12345},
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('errors', response.data)


class EventTypeListAPIViewTest(APITestCase):
    """Test cases for EventTypeListAPIView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_event_types(self):
        """Test listing all event types."""
        url = reverse('eventtypelistapi-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Check that event types are properly formatted
        for event_type in response.data['results']:
            self.assertIn('event_type', event_type)
            self.assertIn('display_name', event_type)
    
    def test_filter_event_types(self):
        """Test filtering event types."""
        url = reverse('eventtypelistapi-list')
        response = self.client.get(url, {'search': 'user'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Check that only user-related event types are returned
        for event_type in response.data['results']:
            self.assertIn('user', event_type['event_type'])

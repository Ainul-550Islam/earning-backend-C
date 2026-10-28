"""Test ViewSets for Webhooks System

This module contains tests for all webhook viewsets
including core viewsets, advanced features, analytics, and replay functionality.
"""

from datetime import timedelta
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import Mock, patch
from django.utils import timezone

from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ..constants import (
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_endpoints(self):
        """Test listing webhook endpoints."""
        url = reverse('webhooks:webhook-endpoint-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_endpoint(self):
        """Test creating a webhook endpoint."""
        url = reverse('webhooks:webhook-endpoint-list')
        data = {
            'label': 'New Webhook',
            'target_url': 'https://example.com/new-webhook',
            'status': WebhookStatus.ACTIVE,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['target_url'], 'https://example.com/new-webhook')
        # secret_key is deliberately not exposed by WebhookEndpointSerializer
        # (read_only_fields/write_only conflict, SER-05) - it's generated
        # server-side and only readable/rotatable via /rotate-secret/.
        self.assertNotIn('secret', response.data)
        self.assertNotIn('secret_key', response.data)
    
    def test_retrieve_endpoint(self):
        """Test retrieving a specific webhook endpoint."""
        url = reverse('webhooks:webhook-endpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # WebhookEndpoint.id is a UUIDField - response.data['id'] is a string.
        self.assertEqual(response.data['id'], str(self.endpoint.id))
        self.assertEqual(response.data['target_url'], self.endpoint.target_url)
    
    def test_update_endpoint(self):
        """Test updating a webhook endpoint."""
        url = reverse('webhooks:webhook-endpoint-detail', kwargs={'pk': self.endpoint.id})
        data = {
            'target_url': 'https://example.com/updated-webhook',
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['target_url'], 'https://example.com/updated-webhook')
        # status is read_only on WebhookEndpointSerializer by design - transitions
        # go through the dedicated /pause/ and /resume/ actions instead, covered
        # by test_pause_endpoint_action / test_resume_endpoint_action.
        self.assertEqual(response.data['status'], WebhookStatus.ACTIVE)
    
    def test_delete_endpoint(self):
        """Test deleting a webhook endpoint."""
        url = reverse('webhooks:webhook-endpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WebhookEndpoint.objects.filter(id=self.endpoint.id).exists())
    
    def test_test_endpoint_action(self):
        """Test testing webhook endpoint action."""
        url = reverse('webhooks:webhook-endpoint-test', kwargs={'pk': self.endpoint.id})
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
        }
        
        with patch('api.webhooks.views.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_rotate_secret_action(self):
        """Test rotating webhook secret action."""
        url = reverse('webhooks:webhook-endpoint-rotate-secret', kwargs={'pk': self.endpoint.id})
        
        with patch('api.webhooks.views.SecretRotationService.rotate_secret') as mock_rotate:
            mock_rotate.return_value = 'new-secret-value'

            response = self.client.post(url, {'confirm': True})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['new_secret'], 'new-secret-value')
            mock_rotate.assert_called_once()
    
    def test_pause_endpoint_action(self):
        """Test pausing webhook endpoint action."""
        url = reverse('webhooks:webhook-endpoint-pause', kwargs={'pk': self.endpoint.id})
        
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
        
        url = reverse('webhooks:webhook-endpoint-resume', kwargs={'pk': self.endpoint.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check endpoint status
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.ACTIVE)
    
    def test_health_status_action(self):
        """Test getting health status action."""
        url = reverse('webhooks:webhook-endpoint-health-status', kwargs={'pk': self.endpoint.id})
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.get_endpoint_health_summary') as mock_health:
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_subscriptions(self):
        """Test listing webhook subscriptions."""
        url = reverse('webhooks:webhook-subscription-list', kwargs={'endpoint_pk': self.endpoint.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_create_subscription(self):
        """Test creating a webhook subscription."""
        url = reverse('webhooks:webhook-subscription-list', kwargs={'endpoint_pk': self.endpoint.id})
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'filters': {'user_id': 12345},
            'is_active': True,
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_type'], 'user.created')
        self.assertEqual(response.data['filters'], {'user_id': 12345})
    
    def test_retrieve_subscription(self):
        """Test retrieving a specific webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        
        url = reverse(
            'webhooks:webhook-subscription-detail',
            kwargs={'endpoint_pk': self.endpoint.id, 'pk': subscription.id},
        )
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # WebhookSubscription.id is a UUIDField - response.data['id'] is a string.
        self.assertEqual(response.data['id'], str(subscription.id))
    
    def test_update_subscription(self):
        """Test updating a webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        
        url = reverse(
            'webhooks:webhook-subscription-detail',
            kwargs={'endpoint_pk': self.endpoint.id, 'pk': subscription.id},
        )
        data = {
            'is_active': False,
            'filters': {'user_id': 54321},
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_active'], False)
        self.assertEqual(response.data['filters'], {'user_id': 54321})
    
    def test_delete_subscription(self):
        """Test deleting a webhook subscription."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        
        url = reverse(
            'webhooks:webhook-subscription-detail',
            kwargs={'endpoint_pk': self.endpoint.id, 'pk': subscription.id},
        )
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_delivery_logs(self):
        """Test listing webhook delivery logs."""
        url = reverse('webhooks:webhook-log-list')
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
            http_status_code=200,
            attempt_number=1,
        )
        
        url = reverse('webhooks:webhook-log-detail', kwargs={'pk': log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # WebhookDeliveryLog.id is a UUIDField - response.data['id'] is a string.
        self.assertEqual(response.data['id'], str(log.id))
    
    def test_filter_delivery_logs(self):
        """Test filtering webhook delivery logs."""
        # Create multiple logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS if i < 3 else DeliveryStatus.FAILED,
                http_status_code=200 if i < 3 else 500,
                attempt_number=1,
            )
        
        url = reverse('webhooks:webhook-log-list')
        response = self.client.get(url, {'status': DeliveryStatus.SUCCESS})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that only successful logs are returned
        for result in response.data['results']:
            self.assertEqual(result['status'], DeliveryStatus.SUCCESS)
    
    def test_filter_by_endpoint(self):
        """Test filtering delivery logs by endpoint."""
        # Create another endpoint
        other_endpoint = WebhookEndpoint.objects.create(
            target_url='https://other.example.com/webhook',
            secret_key='other-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        # Create logs for both endpoints
        WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
            attempt_number=1,
        )
        
        WebhookDeliveryLog.objects.create(
            endpoint=other_endpoint,
            event_type='user.created',
            payload={'user_id': 54321},
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
            attempt_number=1,
        )
        
        url = reverse('webhooks:webhook-log-list')
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_list_analytics(self):
        """Test listing webhook analytics."""
        url = reverse('webhooks:webhook-analytics-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_health_summary_action(self):
        """Test getting health summary action."""
        url = reverse('webhooks:webhook-analytics-health-summary')
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.get_endpoint_health_summary') as mock_health:
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
        WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date(),
            total_sent=100,
            success_count=95,
            failed_count=5,
            avg_latency_ms=150.0,
            success_rate=95.0,
        )
        url = reverse('webhooks:webhook-analytics-performance-report', kwargs={'id': self.endpoint.id})
        
        # Real performance_report() aggregates WebhookAnalytics directly via
        # the ORM - it never calls
        # WebhookAnalyticsService.get_performance_metrics (confirmed by
        # reading the action body). {id} is captured but unused by this
        # action (it aggregates over all of request.user's endpoints).
        response = self.client.get(url, {'days': 30})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['total_sent'], 100)
        self.assertEqual(response.data['data']['total_success'], 95)
        self.assertEqual(response.data['data']['total_failed'], 5)
    
    def test_event_statistics_action(self):
        """Test getting event statistics action."""
        WebhookEventStat.objects.create(
            date=timezone.now().date(),
            event_type='user.created',
            fired_count=50,
            delivered_count=48,
            failed_count=2,
        )
        url = reverse('webhooks:webhook-analytics-event-stats', kwargs={'id': self.endpoint.id})
        
        # Real event_statistics() queries WebhookEventStat directly via the
        # ORM - it never calls
        # WebhookAnalyticsService.get_event_statistics (confirmed by reading
        # the action body). WebhookEventStat has no endpoint field (separate
        # production bug fixed in viewsets/WebhookAnalyticsViewSet.py), so
        # results are global, not scoped to self.endpoint.
        response = self.client.get(url, {'days': 30, 'event_type': 'user.created'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['event_type'], 'user.created')
    
    def test_export_csv_action(self):
        """Test exporting analytics data as CSV."""
        WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date(),
            total_sent=10,
            success_count=8,
            failed_count=2,
            avg_latency_ms=120.0,
            success_rate=80.0,
        )
        url = reverse('webhooks:webhook-analytics-export-csv', kwargs={'id': self.endpoint.id})
        
        # export_csv is POST-only (methods=["post"]) - the original test
        # used GET, which 405s. Real action streams a CSV via a direct ORM
        # query - it never calls WebhookAnalyticsService.export_csv
        # (confirmed by reading the action body).
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn(self.endpoint.target_url, content)


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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_create_replay_batch_action(self):
        """Test creating replay batch action."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 1},
            status=DeliveryStatus.FAILED,
            http_status_code=500,
            attempt_number=3,
        )
        # created_at is auto_now_add - move it into the filter's date range
        # via a queryset .update(), which bypasses auto_now_add.
        WebhookDeliveryLog.objects.filter(pk=log.pk).update(
            created_at=timezone.make_aware(timezone.datetime(2024, 1, 15))
        )

        url = reverse('webhooks:webhook-replay-create-batch')
        data = {
            'event_type': 'user.created',
            'date_from': '2024-01-01',
            'date_to': '2024-01-31',
            'batch_size': 100,
        }

        # Real create_batch() filters + creates WebhookReplayBatch/Item
        # directly via the ORM - it never calls
        # ReplayService.create_replay_batch (confirmed by reading the
        # action body), so mocking that method tested nothing.
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('batch_id', response.data)
        batch = WebhookReplayBatch.objects.get(pk=response.data['batch_id'])
        self.assertEqual(batch.count, 1)
        self.assertEqual(WebhookReplayItem.objects.filter(batch=batch).count(), 1)
    
    def test_start_batch_action(self):
        """Test starting batch processing action."""
        batch = WebhookReplayBatch.objects.create(
            event_type='user.created',
            created_by=self.user,
            count=1,
            date_from='2024-01-01',
            date_to='2024-01-31',
            status=ReplayStatus.PENDING,
        )
        url = reverse('webhooks:webhook-replay-start-batch', kwargs={'id': batch.id})

        # Real start_batch() queues the process_replay_batch Celery task -
        # it never calls ReplayService.start_batch_processing (confirmed by
        # reading the action body). CELERY_TASK_ALWAYS_EAGER is on, so mock
        # the task itself rather than let the full processing pipeline run
        # here (that pipeline has its own dedicated tests - see
        # test_start_batch_action_preserves_real_completion below for the
        # unmocked case, which this test deliberately doesn't cover).
        with patch('api.webhooks.tasks.process_replay_batch.delay') as mock_delay:
            response = self.client.post(url)
            mock_delay.assert_called_once_with(str(batch.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'processing')

    def test_start_batch_action_preserves_real_completion(self):
        """Regression test for the identical delay()-then-unconditional-
        status-set ordering bug in this action (see
        ReplayService.start_batch_processing()'s docstring for the full
        root cause - this action has the same pattern).

        Deliberately does NOT mock the task here, unlike
        test_start_batch_action above - under CELERY_TASK_ALWAYS_EAGER,
        that lets the real pipeline run synchronously with one real
        (mocked-HTTP) item. Before the fix, this action's own
        batch.status = "processing" line right after delay() would
        silently overwrite the real COMPLETED result the synchronous run
        just set, permanently.
        """
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 1},
            status=DeliveryStatus.FAILED,
        )
        batch = WebhookReplayBatch.objects.create(
            event_type='user.created',
            created_by=self.user,
            count=1,
            date_from='2024-01-01',
            date_to='2024-01-31',
            status=ReplayStatus.PENDING,
        )
        WebhookReplayItem.objects.create(
            batch=batch, original_log=log, status=ReplayStatus.PENDING,
        )
        url = reverse('webhooks:webhook-replay-start-batch', kwargs={'id': batch.id})

        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '{"status": "ok"}'
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_post.return_value = mock_response

            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        batch.refresh_from_db()
        self.assertEqual(batch.status, ReplayStatus.COMPLETED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_batch_progress_action(self):
        """Test getting batch progress action."""
        batch = WebhookReplayBatch.objects.create(
            event_type='user.created',
            created_by=self.user,
            count=2,
            date_from='2024-01-01',
            date_to='2024-01-31',
            status=ReplayStatus.PROCESSING,
        )
        log1 = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.FAILED, http_status_code=500, attempt_number=1,
        )
        log2 = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.FAILED, http_status_code=500, attempt_number=1,
        )
        WebhookReplayItem.objects.create(batch=batch, original_log=log1, status=ReplayStatus.COMPLETED)
        WebhookReplayItem.objects.create(batch=batch, original_log=log2, status=ReplayStatus.PENDING)

        url = reverse('webhooks:webhook-replay-batch-progress', kwargs={'id': batch.id})

        # Real batch_progress() counts WebhookReplayItem rows directly via
        # the ORM - it never calls ReplayService.get_batch_progress
        # (confirmed by reading the action body).
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['total'], 2)
        self.assertEqual(response.data['data']['completed'], 1)
        self.assertEqual(response.data['data']['pending'], 1)
    
    def test_cancel_batch_action(self):
        """Test cancelling batch action."""
        batch = WebhookReplayBatch.objects.create(
            event_type='user.created',
            created_by=self.user,
            count=1,
            date_from='2024-01-01',
            date_to='2024-01-31',
            status=ReplayStatus.PENDING,
        )
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.FAILED, http_status_code=500, attempt_number=1,
        )
        item = WebhookReplayItem.objects.create(batch=batch, original_log=log, status=ReplayStatus.PENDING)

        url = reverse('webhooks:webhook-replay-cancel-batch', kwargs={'id': batch.id})

        # Real cancel_batch() updates the batch + its pending items directly
        # via the ORM - it never calls ReplayService.cancel_batch (confirmed
        # by reading the action body).
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        batch.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(batch.status, 'cancelled')
        self.assertEqual(item.status, ReplayStatus.CANCELLED)
    
    def test_replay_history_action(self):
        """Test getting replay history action."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 1},
            status=DeliveryStatus.FAILED,
            http_status_code=500,
            attempt_number=1,
        )
        WebhookReplay.objects.create(
            original_log=log,
            replayed_by=self.user,
            reason='manual replay for test',
            status=ReplayStatus.COMPLETED,
        )

        url = reverse('webhooks:webhook-replay-history')
        response = self.client.get(url)

        # Real replay_history() is a direct ORM query + pagination - it never
        # calls ReplayService.get_replay_history (confirmed by reading the
        # action body), and returns the paginated list directly, no
        # {success, data} wrapper.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_replay_statistics_action(self):
        """Test getting replay statistics action."""
        url = reverse('webhooks:webhook-replay-statistics')
        
        # Real replay_statistics() computes stats via a direct ORM
        # aggregate() - it never calls ReplayService.get_replay_statistics
        # (confirmed by reading the action body), so mocking that method
        # tested nothing; the response shape itself was already correct.
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)


class WebhookEmitAPIViewTest(APITestCase):
    """Test cases for WebhookEmitAPIView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_staff=True,  # WebhookEmitAPIView is IsAdminUser-only (staff/system endpoint)
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)
    
    def test_emit_webhook(self):
        """Test emitting a webhook."""
        url = reverse('webhooks:webhook-emit')
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': self.endpoint.id,
        }
        
        with patch('api.webhooks.views.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_emit_webhook_async(self):
        """Test emitting a webhook asynchronously."""
        url = reverse('webhooks:webhook-emit')
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': self.endpoint.id,
            'async_emit': True,
        }
        
        with patch('api.webhooks.views.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            response = self.client.post(url, data)
            
            # Async path never calls DispatchService.emit synchronously - it
            # queues the dispatch_event Celery task and returns 202 Accepted.
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['status'], 'queued')
            mock_emit.assert_not_called()
    
    def test_emit_webhook_validation(self):
        """Test webhook emission validation."""
        url = reverse('webhooks:webhook-emit')
        data = {
            'endpoint_id': self.endpoint.id,
            'event_type': '',  # Invalid: empty event type
            'payload': {'user_id': 12345},
        }
        
        response = self.client.post(url, data)
        
        # WebhookEmitAPIView uses serializer.is_valid(raise_exception=True),
        # so DRF's default exception handler returns the raw field-errors
        # dict - there's no custom {success, errors} wrapper on this view.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # BUG FIX (Session 10): errors come back nested under the
        # project-wide webhook_exception_handler envelope, not as a bare
        # top-level key (see test_views.py::test_create_endpoint_invalid_data).
        self.assertIn('event_type', response.data['error']['detail'])


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
        url = reverse('webhooks:webhook-event-types')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Check that event types are properly formatted
        for event_type in response.data['results']:
            self.assertIn('event_type', event_type)
            self.assertIn('display_name', event_type)
            self.assertNotIn('value', event_type)
    
    def test_filter_event_types(self):
        """Test filtering event types."""
        url = reverse('webhooks:webhook-event-types')
        response = self.client.get(url, {'search': 'user'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        # Check that only user-related event types are returned
        for event_type in response.data['results']:
            self.assertIn('user', event_type['event_type'])
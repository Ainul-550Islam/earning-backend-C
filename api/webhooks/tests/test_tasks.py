"""Test Tasks for Webhooks System

This module contains tests for the webhook background tasks
including async webhook emission, retry logic, and cleanup tasks.
"""

from datetime import timedelta
import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from celery.exceptions import Retry

from ..tasks import (
    dispatch_event, retry_failed_dispatch, reap_exhausted_logs,
    auto_suspend_endpoints, health_check_tasks, analytics_tasks,
    rate_limit_reset_tasks, replay_tasks, cleanup_tasks
)
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat,
    WebhookRateLimit, WebhookReplay, WebhookReplayBatch
)
from ..constants import (
    WebhookStatus, DeliveryStatus, BatchStatus, ReplayStatus
)

User = get_user_model()


class DispatchEventTaskTest(TestCase):
    """Test cases for dispatch_event task."""
    
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
        self.subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
    
    def test_dispatch_event_success(self):
        """Test successful event dispatch."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            mock_emit.return_value = True
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_called_once()
    
    def test_dispatch_event_failure(self):
        """Test failed event dispatch — the task itself still completes
        without raising; the dispatch outcome is reported in the returned
        dict's 'success' key, not via task failure."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            mock_emit.return_value = False
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            self.assertFalse(result.result['success'])
            mock_emit.assert_called_once()
    
    def test_dispatch_event_with_exception(self):
        """Test event dispatch with exception — the task's own except
        block calls self.retry(), which raises celery.exceptions.Retry
        directly at the .delay() call in this eager-mode test config."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            mock_emit.side_effect = Exception('Dispatch error')
            
            with self.assertRaises(Retry):
                dispatch_event.delay(
                    endpoint_id=self.endpoint.id,
                    event_type='user.created',
                    payload=payload
                )
            
            mock_emit.assert_called_once()
    
    def test_dispatch_event_endpoint_not_found(self):
        """Test event dispatch with non-existent endpoint. The task
        catches WebhookEndpoint.DoesNotExist internally (documented in
        dispatch_event.py) and returns a result dict rather than raising."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        result = dispatch_event.delay(
            endpoint_id='123e4567-e89b-12d3-a456-426614174000',
            event_type='user.created',
            payload=payload
        )
        
        self.assertTrue(result.successful())
        self.assertFalse(result.result['success'])
        self.assertEqual(result.result['reason'], 'Endpoint not found')
    
    def test_dispatch_event_inactive_endpoint(self):
        """Test event dispatch with inactive endpoint."""
        self.endpoint.status = WebhookStatus.PAUSED
        self.endpoint.save()
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_not_called()
    
    def test_dispatch_event_no_subscription(self):
        """Test event dispatch with no matching subscription."""
        # Delete subscription
        self.subscription.delete()
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_not_called()
    
    def test_dispatch_event_with_filters(self):
        """Test event dispatch with subscription filters."""
        # Update subscription with filter
        self.subscription.filters = {'user_email': {'operator': 'contains', 'value': '@example.com'}}
        self.subscription.save()
        
        payload = {'user_id': 12345, 'user_email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            mock_emit.return_value = True
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_called_once()
    
    def test_dispatch_event_with_filters_no_match(self):
        """Test event dispatch with filters that don't match."""
        # Update subscription with filter
        self.subscription.filters = {'user_email': {'operator': 'contains', 'value': '@example.com'}}
        self.subscription.save()
        
        payload = {'user_id': 12345, 'user_email': 'test@other.com'}
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService._emit_sync') as mock_emit:
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_not_called()


class RetryFailedDispatchTaskTest(TestCase):
    """Test cases for retry_failed_dispatch task."""
    
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
        self.delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            http_status_code=500,
            attempt_number=1,
            max_attempts=3,
            next_retry_at=timezone.now() - timedelta(minutes=5),
        )
    
    def test_retry_failed_dispatch_success(self):
        """Test successful retry of failed dispatch."""
        with patch('api.webhooks.services.core.DispatchService.DispatchService.retry_delivery') as mock_retry:
            mock_retry.return_value = True
            
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_failure(self):
        """Test failed retry of failed dispatch."""
        with patch('api.webhooks.services.core.DispatchService.DispatchService.retry_delivery') as mock_retry:
            mock_retry.return_value = False
            
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_with_exception(self):
        """Test retry of failed dispatch with exception — self.retry()
        raises celery.exceptions.Retry directly at the .delay() call."""
        with patch('api.webhooks.services.core.DispatchService.DispatchService.retry_delivery') as mock_retry:
            mock_retry.side_effect = Exception('Retry error')
            
            with self.assertRaises(Retry):
                retry_failed_dispatch.delay(self.delivery_log.id)
            
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_log_not_found(self):
        """Test retry with non-existent delivery log. The task catches
        WebhookDeliveryLog.DoesNotExist internally and returns a result
        dict rather than raising."""
        result = retry_failed_dispatch.delay('123e4567-e89b-12d3-a456-426614174000')
        
        self.assertTrue(result.successful())
        self.assertFalse(result.result['success'])
        self.assertEqual(result.result['reason'], 'Delivery log not found')
    
    def test_retry_failed_dispatch_exhausted(self):
        """Test retry with exhausted delivery log."""
        self.delivery_log.status = DeliveryStatus.EXHAUSTED
        self.delivery_log.save()
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService.retry_delivery') as mock_retry:
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_not_called()
    
    def test_retry_failed_dispatch_not_ready(self):
        """Test retry with delivery log not ready for retry."""
        self.delivery_log.next_retry_at = timezone.now() + timedelta(hours=1)
        self.delivery_log.save()
        
        with patch('api.webhooks.services.core.DispatchService.DispatchService.retry_delivery') as mock_retry:
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_not_called()


class ReapExhaustedLogsTaskTest(TestCase):
    """Test cases for reap_exhausted_logs task."""
    
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
        # Create exhausted delivery log
        self.exhausted_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.EXHAUSTED,
            http_status_code=500,
            attempt_number=3,
            max_attempts=3,
            created_at=timezone.now() - timedelta(days=10),
        )
        # Create non-exhausted delivery log
        self.active_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
            created_at=timezone.now() - timedelta(days=10),
        )
    
    def test_reap_exhausted_logs_success(self):
        """Test successful cleanup of exhausted logs."""
        result = reap_exhausted_logs.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that exhausted log was deleted
        with self.assertRaises(WebhookDeliveryLog.DoesNotExist):
            WebhookDeliveryLog.objects.get(id=self.exhausted_log.id)
        
        # Check that active log still exists
        WebhookDeliveryLog.objects.get(id=self.active_log.id)
    
    def test_reap_exhausted_logs_no_logs(self):
        """Test cleanup with no exhausted logs."""
        # Delete exhausted log
        self.exhausted_log.delete()
        
        result = reap_exhausted_logs.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that active log still exists
        WebhookDeliveryLog.objects.get(id=self.active_log.id)
    
    def test_reap_exhausted_logs_recent_logs(self):
        """Test cleanup with recent exhausted logs."""
        # Update exhausted log to be recent
        self.exhausted_log.created_at = timezone.now() - timedelta(days=1)
        self.exhausted_log.save()
        
        result = reap_exhausted_logs.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that exhausted log still exists
        WebhookDeliveryLog.objects.get(id=self.exhausted_log.id)


class AutoSuspendEndpointsTaskTest(TestCase):
    """Test cases for auto_suspend_endpoints task."""
    
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
        # Create consecutive failed health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
            )
    
    def test_auto_suspend_endpoints_success(self):
        """Test successful auto-suspension of endpoints."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
            mock_suspend.return_value = {'suspended': True}
            
            result = auto_suspend_endpoints.delay(consecutive_failures=3)
            
            self.assertTrue(result.successful())
            mock_suspend.assert_called_once()
    
    def test_auto_suspend_endpoints_no_failures(self):
        """Test auto-suspension with no consecutive failures."""
        # Delete health logs
        WebhookHealthLog.objects.filter(endpoint=self.endpoint).delete()
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
            result = auto_suspend_endpoints.delay(consecutive_failures=3)
            
            self.assertTrue(result.successful())
            mock_suspend.assert_not_called()
    
    def test_auto_suspend_endpoints_already_suspended(self):
        """Test auto-suspension with already suspended endpoint."""
        self.endpoint.status = WebhookStatus.SUSPENDED
        self.endpoint.save()
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
            result = auto_suspend_endpoints.delay(consecutive_failures=3)
            
            self.assertTrue(result.successful())
            mock_suspend.assert_not_called()


class HealthCheckTasksTest(TestCase):
    """Test cases for health_check_tasks."""
    
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
    
    def test_health_check_task_success(self):
        """Test successful health check task."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {
                'is_healthy': True,
                'status_code': 200,
                'response_time_ms': 150
            }
            
            result = health_check_tasks.health_check_endpoint.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_health_check_task_failure(self):
        """Test health check task failure."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {
                'is_healthy': False,
                'status_code': 500,
                'response_time_ms': 5000,
                'error': 'Server error'
            }
            
            result = health_check_tasks.health_check_endpoint.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_health_check_task_exception(self):
        """Test health check task with exception — self.retry() raises
        celery.exceptions.Retry directly at the .delay() call."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.side_effect = Exception('Health check error')
            
            with self.assertRaises(Retry):
                health_check_tasks.health_check_endpoint.delay(self.endpoint.id)
            
            mock_health.assert_called_once()
    
    def test_health_check_task_endpoint_not_found(self):
        """Test health check task with non-existent endpoint. The task
        catches WebhookEndpoint.DoesNotExist internally and returns a
        result dict rather than raising."""
        result = health_check_tasks.health_check_endpoint.delay('123e4567-e89b-12d3-a456-426614174000')
        
        self.assertTrue(result.successful())
        self.assertFalse(result.result['success'])
        self.assertEqual(result.result['error'], 'Endpoint not found')
    
    def test_health_check_all_endpoints_success(self):
        """Test health check of all endpoints. The task queries active
        endpoints itself and calls HealthMonitorService.check_endpoint_health()
        per endpoint — there's no endpoint-list argument to pass in."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {'is_healthy': True, 'status_code': 200, 'response_time_ms': 100}
            
            result = health_check_tasks.health_check_all_endpoints.delay()
            
            self.assertTrue(result.successful())
            self.assertTrue(result.result['success'])
            self.assertEqual(result.result['endpoints_checked'], 1)
            self.assertEqual(result.result['healthy_endpoints'], 1)
            mock_health.assert_called_once()
    
    def test_schedule_health_check_success(self):
        """Test scheduling health check. The schedule_health_check task
        just calls HealthMonitorService().check_endpoint_health() and
        returns its result directly — it has no method of its own on the
        service to mock."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.HealthMonitorService.check_endpoint_health') as mock_check:
            mock_check.return_value = {'is_healthy': True, 'status_code': 200, 'response_time_ms': 100}
            
            result = health_check_tasks.schedule_health_check.delay(
                endpoint_id=self.endpoint.id,
                interval_minutes=5
            )
            
            self.assertTrue(result.successful())
            mock_check.assert_called_once()


class AnalyticsTasksTest(TestCase):
    """Test cases for analytics_tasks."""
    
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
        # Create delivery logs for analytics
        for i in range(10):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS if i < 8 else DeliveryStatus.FAILED,
                http_status_code=200 if i < 8 else 500,
                response_time_ms=100 + i * 10,
                created_at=timezone.now() - timedelta(hours=i),
            )
    
    def test_generate_daily_analytics_success(self):
        """Test successful daily analytics generation."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.WebhookAnalyticsService.generate_daily_analytics') as mock_analytics:
            mock_analytics.return_value = []
            
            result = analytics_tasks.generate_daily_analytics.delay(
                endpoint_id=self.endpoint.id,
                days=7
            )
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called_once()
    
    def test_generate_daily_analytics_all_endpoints(self):
        """Test daily analytics generation for all endpoints."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.WebhookAnalyticsService.generate_daily_analytics') as mock_analytics:
            mock_analytics.return_value = []
            
            result = analytics_tasks.generate_daily_analytics_all_endpoints.delay(days=7)
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called()
    
    def test_generate_event_statistics_success(self):
        """Test successful event statistics generation. The task does its
        own direct ORM aggregation (no service method to mock) — verifying
        the real WebhookEventStat side effect instead."""
        result = analytics_tasks.generate_event_statistics.delay(
            endpoint_id=self.endpoint.id,
            days=7
        )
        
        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])
        self.assertEqual(result.result['event_types_processed'], 1)
        
        stat = WebhookEventStat.objects.get(event_type='user.created', date=timezone.now().date())
        self.assertEqual(stat.fired_count, 10)
        self.assertEqual(stat.delivered_count, 8)
        self.assertEqual(stat.failed_count, 2)
    
    def test_generate_event_statistics_all_endpoints(self):
        """Test event statistics generation for all endpoints."""
        result = analytics_tasks.generate_event_statistics_all_endpoints.delay(days=7)
        
        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])
        self.assertEqual(result.result['success_count'], 1)
    
    def test_calculate_performance_metrics_success(self):
        """Test successful performance metrics calculation. The task does
        its own direct ORM aggregation (no service method to mock) —
        verifying the real computed result instead."""
        result = analytics_tasks.calculate_performance_metrics.delay(
            endpoint_id=self.endpoint.id,
            days=7
        )
        
        self.assertTrue(result.successful())
        metrics = result.result['performance_metrics']
        self.assertTrue(result.result['success'])
        self.assertEqual(metrics['total_requests'], 8)  # only the 8 successful logs
        self.assertEqual(metrics['min_response_time_ms'], 100)
        self.assertEqual(metrics['max_response_time_ms'], 170)
        self.assertEqual(metrics['avg_response_time_ms'], 135.0)
    
    def test_calculate_performance_metrics_all_endpoints(self):
        """Test performance metrics calculation for all endpoints."""
        result = analytics_tasks.calculate_performance_metrics_all_endpoints.delay(days=7)
        
        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])


class RateLimitResetTasksTest(TestCase):
    """Test cases for rate_limit_reset_tasks."""
    
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
        self.rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            current_count=50,
            reset_at=timezone.now() - timedelta(hours=1),
        )
    
    def test_reset_rate_limits_success(self):
        """Test successful rate limit reset."""
        with patch('api.webhooks.services.analytics.RateLimiterService.RateLimiterService.reset_rate_limit') as mock_reset:
            mock_reset.return_value = True
            
            result = rate_limit_reset_tasks.reset_rate_limits.delay()
            
            self.assertTrue(result.successful())
            mock_reset.assert_called()
    
    def test_reset_rate_limits_endpoint_specific(self):
        """Test rate limit reset for specific endpoint."""
        with patch('api.webhooks.services.analytics.RateLimiterService.RateLimiterService.reset_rate_limit') as mock_reset:
            mock_reset.return_value = True
            
            result = rate_limit_reset_tasks.reset_rate_limit.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_reset.assert_called_once()
    
    def test_cleanup_expired_rate_limits_success(self):
        """Test successful cleanup of expired rate limits."""
        with patch('api.webhooks.services.analytics.RateLimiterService.RateLimiterService.cleanup_expired_rate_limits') as mock_cleanup:
            mock_cleanup.return_value = {'cleaned_count': 5}
            
            result = rate_limit_reset_tasks.cleanup_expired_rate_limits.delay()
            
            self.assertTrue(result.successful())
            mock_cleanup.assert_called_once()


class ReplayTasksTest(TestCase):
    """Test cases for replay_tasks."""
    
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
        self.original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
        )
        self.replay = WebhookReplay.objects.create(
            original_log=self.original_log,
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
        )
    
    def test_process_replay_success(self):
        """Test successful replay processing."""
        with patch('api.webhooks.services.replay.ReplayService.process_replay') as mock_replay:
            mock_replay.return_value = {'success': True}
            
            result = replay_tasks.process_replay.delay(self.replay.id)
            
            self.assertTrue(result.successful())
            mock_replay.assert_called_once()
    
    def test_process_replay_batch_success(self):
        """Test successful replay batch processing."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now(),
            count=10,
            status=ReplayStatus.PENDING,
        )
        
        with patch('api.webhooks.services.replay.ReplayService.process_replay_batch') as mock_replay:
            mock_replay.return_value = {'success': True}
            
            result = replay_tasks.process_replay_batch.delay(batch.id)
            
            self.assertTrue(result.successful())
            mock_replay.assert_called_once()
    
    def test_create_replay_batch_success(self):
        """Test successful replay batch creation."""
        delivery_logs = [
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
            )
            for i in range(3)
        ]
        
        with patch('api.webhooks.services.replay.ReplayService.create_replay_batch') as mock_create:
            mock_create.return_value = Mock(id='batch-123')
            
            result = replay_tasks.create_replay_batch.delay(
                delivery_log_ids=[log.id for log in delivery_logs],
                replayed_by_id=self.user.id,
                reason='Batch replay'
            )
            
            self.assertTrue(result.successful())
            mock_create.assert_called_once()
    
    def test_cleanup_old_replays_success(self):
        """Test successful cleanup of old replays. The task does its own
        direct ORM deletion (filters WebhookReplay by created_at and
        deletes in a loop) — it never instantiates or calls
        ReplayService.cleanup_old_replays() at all, confirmed via the
        real task source. Verifying the real DB side effect instead,
        same precedent as AnalyticsTasksTest's generate_event_statistics/
        calculate_performance_metrics earlier this session.
        created_at is auto_now_add=True, so backdating goes through
        .filter().update() (bypasses pre_save) rather than .create()."""
        old_replay = WebhookReplay.objects.create(
            original_log=self.original_log,
            replayed_by=self.user,
            reason='Old replay',
            status=ReplayStatus.COMPLETED,
        )
        WebhookReplay.objects.filter(pk=old_replay.pk).update(
            created_at=timezone.now() - timedelta(days=45)
        )

        result = replay_tasks.cleanup_old_replays.delay(days=30)

        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])
        self.assertEqual(result.result['deleted_count'], 1)

        with self.assertRaises(WebhookReplay.DoesNotExist):
            WebhookReplay.objects.get(pk=old_replay.pk)
        # self.replay (setUp, just created) is recent and must survive
        WebhookReplay.objects.get(pk=self.replay.pk)
    
    def test_cleanup_old_replay_batches_success(self):
        """Test successful cleanup of old replay batches. Same situation
        as test_cleanup_old_replays_success above: the task does its own
        direct ORM deletion, never calling ReplayService. Verifying the
        real DB side effect instead."""
        old_batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date() - timedelta(days=2),
            date_to=timezone.now().date() - timedelta(days=1),
            count=5,
            status=ReplayStatus.COMPLETED,
        )
        WebhookReplayBatch.objects.filter(pk=old_batch.pk).update(
            created_at=timezone.now() - timedelta(days=45)
        )
        recent_batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.updated',
            date_from=timezone.now().date(),
            date_to=timezone.now().date(),
            count=2,
            status=ReplayStatus.PENDING,
        )

        result = replay_tasks.cleanup_old_replay_batches.delay(days=30)

        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])
        self.assertEqual(result.result['deleted_count'], 1)

        with self.assertRaises(WebhookReplayBatch.DoesNotExist):
            WebhookReplayBatch.objects.get(pk=old_batch.pk)
        WebhookReplayBatch.objects.get(pk=recent_batch.pk)


class CleanupTasksTest(TestCase):
    """Test cases for cleanup_tasks."""
    
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
    
    def test_cleanup_old_delivery_logs_success(self):
        """Test successful cleanup of old delivery logs."""
        # Create old delivery log
        old_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            created_at=timezone.now() - timedelta(days=30),
        )
        
        # Create recent delivery log
        recent_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            created_at=timezone.now() - timedelta(days=1),
        )
        
        result = cleanup_tasks.cleanup_old_delivery_logs.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that old log was deleted
        with self.assertRaises(WebhookDeliveryLog.DoesNotExist):
            WebhookDeliveryLog.objects.get(id=old_log.id)
        
        # Check that recent log still exists
        WebhookDeliveryLog.objects.get(id=recent_log.id)
    
    def test_cleanup_old_health_logs_success(self):
        """Test successful cleanup of old health logs."""
        # Create old health log
        old_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timedelta(days=30),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
        )
        
        # Create recent health log
        recent_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timedelta(days=1),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
        )
        
        result = cleanup_tasks.cleanup_old_health_logs.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that old log was deleted
        with self.assertRaises(WebhookHealthLog.DoesNotExist):
            WebhookHealthLog.objects.get(id=old_log.id)
        
        # Check that recent log still exists
        WebhookHealthLog.objects.get(id=recent_log.id)
    
    def test_cleanup_old_analytics_success(self):
        """Test successful cleanup of old analytics."""
        # Create old analytics
        old_analytics = WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date() - timedelta(days=30),
            total_sent=100,
            success_count=95,
            failed_count=5,
            avg_latency_ms=150.0,
            success_rate=95.0,
        )
        
        # Create recent analytics
        recent_analytics = WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date() - timedelta(days=1),
            total_sent=50,
            success_count=48,
            failed_count=2,
            avg_latency_ms=120.0,
            success_rate=96.0,
        )
        
        result = cleanup_tasks.cleanup_old_analytics.delay(days=7)
        
        self.assertTrue(result.successful())
        
        # Check that old analytics was deleted
        with self.assertRaises(WebhookAnalytics.DoesNotExist):
            WebhookAnalytics.objects.get(id=old_analytics.id)
        
        # Check that recent analytics still exists
        WebhookAnalytics.objects.get(id=recent_analytics.id)
    
    def test_cleanup_all_old_data_success(self):
        """Test successful cleanup of all old data."""
        result = cleanup_tasks.cleanup_all_old_data.delay(days=30)
        
        self.assertTrue(result.successful())
    
    def test_archive_old_data_success(self):
        """Test successful archiving of old data.

        archive_old_data does its own direct field-set (log.archived =
        True; log.archived_at = now(); log.save()) on WebhookDeliveryLog/
        WebhookHealthLog rows older than the cutoff — it never calls any
        service. api.webhooks.services.cleanup.ArchiveService does not
        exist anywhere in the codebase (confirmed: no services/cleanup
        module, no ArchiveService class anywhere). Prior to session 6,
        archived/archived_at also didn't exist as real model fields, so
        this task always reported success while persisting nothing.
        Verifying the real DB side effect instead, same precedent as the
        ReplayTasksTest cleanup fixes above — including that a second run
        doesn't re-touch already-archived rows (archived=False filter
        added alongside the fields, session 6).
        """
        old_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            created_at=timezone.now() - timedelta(days=200),
        )
        recent_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            created_at=timezone.now() - timedelta(days=1),
        )
        old_health_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timedelta(days=200),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
        )
        recent_health_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timedelta(days=1),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
        )

        result = cleanup_tasks.archive_old_data.delay(days=180)

        self.assertTrue(result.successful())
        self.assertTrue(result.result['success'])
        self.assertEqual(result.result['delivery_logs_archived'], 1)
        self.assertEqual(result.result['health_logs_archived'], 1)

        old_log.refresh_from_db()
        self.assertTrue(old_log.archived)
        first_archived_at = old_log.archived_at
        self.assertIsNotNone(first_archived_at)

        recent_log.refresh_from_db()
        self.assertFalse(recent_log.archived)
        self.assertIsNone(recent_log.archived_at)

        old_health_log.refresh_from_db()
        self.assertTrue(old_health_log.archived)
        self.assertIsNotNone(old_health_log.archived_at)

        recent_health_log.refresh_from_db()
        self.assertFalse(recent_health_log.archived)

        # Running again must not re-touch already-archived rows.
        result2 = cleanup_tasks.archive_old_data.delay(days=180)
        self.assertTrue(result2.successful())
        self.assertEqual(result2.result['delivery_logs_archived'], 0)
        self.assertEqual(result2.result['health_logs_archived'], 0)
        old_log.refresh_from_db()
        self.assertEqual(old_log.archived_at, first_archived_at)


# Additional task tests can be added here for any remaining tasks
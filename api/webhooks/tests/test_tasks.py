"""Test Tasks for Webhooks System

This module contains tests for the webhook background tasks
including async webhook emission, retry logic, and cleanup tasks.
"""

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
    
    def test_dispatch_event_success(self):
        """Test successful event dispatch."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_called_once()
    
    def test_dispatch_event_failure(self):
        """Test failed event dispatch."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = False
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_called_once()
    
    def test_dispatch_event_with_exception(self):
        """Test event dispatch with exception."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.side_effect = Exception('Dispatch error')
            
            result = dispatch_event.delay(
                endpoint_id=self.endpoint.id,
                event_type='user.created',
                payload=payload
            )
            
            self.assertTrue(result.successful())
            mock_emit.assert_called_once()
    
    def test_dispatch_event_endpoint_not_found(self):
        """Test event dispatch with non-existent endpoint."""
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with self.assertRaises(WebhookEndpoint.DoesNotExist):
            dispatch_event.delay(
                endpoint_id='123e4567-e89b-12d3-a456-426614174000',
                event_type='user.created',
                payload=payload
            )
    
    def test_dispatch_event_inactive_endpoint(self):
        """Test event dispatch with inactive endpoint."""
        self.endpoint.status = WebhookStatus.INACTIVE
        self.endpoint.save()
        
        payload = {'user_id': 12345, 'email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
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
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
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
        self.subscription.filter_config = {'user.email': {'operator': 'contains', 'value': '@example.com'}}
        self.subscription.save()
        
        payload = {'user_id': 12345, 'user_email': 'test@example.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
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
        self.subscription.filter_config = {'user.email': {'operator': 'contains', 'value': '@example.com'}}
        self.subscription.save()
        
        payload = {'user_id': 12345, 'user_email': 'test@other.com'}
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            response_code=500,
            attempt_number=1,
            max_attempts=3,
            next_retry_at=timezone.now() + timezone.timedelta(minutes=5),
            created_by=self.user,
        )
    
    def test_retry_failed_dispatch_success(self):
        """Test successful retry of failed dispatch."""
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
            mock_retry.return_value = True
            
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_failure(self):
        """Test failed retry of failed dispatch."""
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
            mock_retry.return_value = False
            
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_with_exception(self):
        """Test retry of failed dispatch with exception."""
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
            mock_retry.side_effect = Exception('Retry error')
            
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_called_once()
    
    def test_retry_failed_dispatch_log_not_found(self):
        """Test retry with non-existent delivery log."""
        with self.assertRaises(WebhookDeliveryLog.DoesNotExist):
            retry_failed_dispatch.delay('123e4567-e89b-12d3-a456-426614174000')
    
    def test_retry_failed_dispatch_exhausted(self):
        """Test retry with exhausted delivery log."""
        self.delivery_log.status = DeliveryStatus.EXHAUSTED
        self.delivery_log.save()
        
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
            result = retry_failed_dispatch.delay(self.delivery_log.id)
            
            self.assertTrue(result.successful())
            mock_retry.assert_not_called()
    
    def test_retry_failed_dispatch_not_ready(self):
        """Test retry with delivery log not ready for retry."""
        self.delivery_log.next_retry_at = timezone.now() + timezone.timedelta(hours=1)
        self.delivery_log.save()
        
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        # Create exhausted delivery log
        self.exhausted_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.EXHAUSTED,
            response_code=500,
            attempt_number=3,
            max_attempts=3,
            created_at=timezone.now() - timezone.timedelta(days=10),
            created_by=self.user,
        )
        # Create non-exhausted delivery log
        self.active_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            created_at=timezone.now() - timezone.timedelta(days=10),
            created_by=self.user,
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
        self.exhausted_log.created_at = timezone.now() - timezone.timedelta(days=1)
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        # Create consecutive failed health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user,
            )
    
    def test_auto_suspend_endpoints_success(self):
        """Test successful auto-suspension of endpoints."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
            mock_suspend.return_value = {'suspended': True}
            
            result = auto_suspend_endpoints.delay(consecutive_failures=3)
            
            self.assertTrue(result.successful())
            mock_suspend.assert_called_once()
    
    def test_auto_suspend_endpoints_no_failures(self):
        """Test auto-suspension with no consecutive failures."""
        # Delete health logs
        WebhookHealthLog.objects.filter(endpoint=self.endpoint).delete()
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
            result = auto_suspend_endpoints.delay(consecutive_failures=3)
            
            self.assertTrue(result.successful())
            mock_suspend.assert_not_called()
    
    def test_auto_suspend_endpoints_already_suspended(self):
        """Test auto-suspension with already suspended endpoint."""
        self.endpoint.status = WebhookStatus.SUSPENDED
        self.endpoint.save()
        
        with patch('api.webhooks.services.analytics.HealthMonitorService.auto_suspend_unhealthy_endpoint') as mock_suspend:
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
    
    def test_health_check_task_success(self):
        """Test successful health check task."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {
                'is_healthy': True,
                'status_code': 200,
                'response_time_ms': 150
            }
            
            result = health_check_tasks.check_endpoint_health.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_health_check_task_failure(self):
        """Test health check task failure."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {
                'is_healthy': False,
                'status_code': 500,
                'response_time_ms': 5000,
                'error': 'Server error'
            }
            
            result = health_check_tasks.check_endpoint_health.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_health_check_task_exception(self):
        """Test health check task with exception."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.side_effect = Exception('Health check error')
            
            result = health_check_tasks.check_endpoint_health.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_health_check_task_endpoint_not_found(self):
        """Test health check task with non-existent endpoint."""
        with self.assertRaises(WebhookEndpoint.DoesNotExist):
            health_check_tasks.check_endpoint_health.delay('123e4567-e89b-12d3-a456-426614174000')
    
    def test_health_check_all_endpoints_success(self):
        """Test health check of all endpoints."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.check_all_endpoints_health') as mock_health:
            mock_health.return_value = [
                {'endpoint_id': self.endpoint.id, 'is_healthy': True}
            ]
            
            result = health_check_tasks.check_all_endpoints_health.delay()
            
            self.assertTrue(result.successful())
            mock_health.assert_called_once()
    
    def test_schedule_health_check_success(self):
        """Test scheduling health check."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.schedule_health_check') as mock_schedule:
            mock_schedule.return_value = {'scheduled': True, 'task_id': 'task-123'}
            
            result = health_check_tasks.schedule_health_check.delay(
                endpoint_id=self.endpoint.id,
                interval_minutes=5
            )
            
            self.assertTrue(result.successful())
            mock_schedule.assert_called_once()


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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        # Create delivery logs for analytics
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
    
    def test_generate_daily_analytics_success(self):
        """Test successful daily analytics generation."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.generate_daily_analytics') as mock_analytics:
            mock_analytics.return_value = []
            
            result = analytics_tasks.generate_daily_analytics.delay(
                endpoint_id=self.endpoint.id,
                days=7
            )
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called_once()
    
    def test_generate_daily_analytics_all_endpoints(self):
        """Test daily analytics generation for all endpoints."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.generate_daily_analytics') as mock_analytics:
            mock_analytics.return_value = []
            
            result = analytics_tasks.generate_daily_analytics_all_endpoints.delay(days=7)
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called()
    
    def test_generate_event_statistics_success(self):
        """Test successful event statistics generation."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.calculate_event_type_analytics') as mock_analytics:
            mock_analytics.return_value = {}
            
            result = analytics_tasks.generate_event_statistics.delay(
                endpoint_id=self.endpoint.id,
                days=7
            )
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called_once()
    
    def test_generate_event_statistics_all_endpoints(self):
        """Test event statistics generation for all endpoints."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.calculate_event_type_analytics') as mock_analytics:
            mock_analytics.return_value = {}
            
            result = analytics_tasks.generate_event_statistics_all_endpoints.delay(days=7)
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called()
    
    def test_calculate_performance_metrics_success(self):
        """Test successful performance metrics calculation."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.calculate_performance_metrics') as mock_analytics:
            mock_analytics.return_value = {}
            
            result = analytics_tasks.calculate_performance_metrics.delay(
                endpoint_id=self.endpoint.id,
                days=7
            )
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called_once()
    
    def test_calculate_performance_metrics_all_endpoints(self):
        """Test performance metrics calculation for all endpoints."""
        with patch('api.webhooks.services.analytics.WebhookAnalyticsService.calculate_performance_metrics') as mock_analytics:
            mock_analytics.return_value = {}
            
            result = analytics_tasks.calculate_performance_metrics_all_endpoints.delay(days=7)
            
            self.assertTrue(result.successful())
            mock_analytics.assert_called()


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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.rate_limit = WebhookRateLimit.objects.create(
            endpoint=self.endpoint,
            window_seconds=60,
            max_requests=100,
            current_count=50,
            reset_at=timezone.now() - timezone.timedelta(hours=1),
            created_by=self.user,
        )
    
    def test_reset_rate_limits_success(self):
        """Test successful rate limit reset."""
        with patch('api.webhooks.services.analytics.RateLimiterService.reset_rate_limit') as mock_reset:
            mock_reset.return_value = True
            
            result = rate_limit_reset_tasks.reset_rate_limits.delay()
            
            self.assertTrue(result.successful())
            mock_reset.assert_called()
    
    def test_reset_rate_limits_endpoint_specific(self):
        """Test rate limit reset for specific endpoint."""
        with patch('api.webhooks.services.analytics.RateLimiterService.reset_rate_limit') as mock_reset:
            mock_reset.return_value = True
            
            result = rate_limit_reset_tasks.reset_rate_limit.delay(self.endpoint.id)
            
            self.assertTrue(result.successful())
            mock_reset.assert_called_once()
    
    def test_cleanup_expired_rate_limits_success(self):
        """Test successful cleanup of expired rate limits."""
        with patch('api.webhooks.services.analytics.RateLimiterService.cleanup_expired_rate_limits') as mock_cleanup:
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        self.replay = WebhookReplay.objects.create(
            original_log=self.original_log,
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
            created_by=self.user,
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
            batch_id='REPLAY-BATCH-123',
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
                created_by=self.user,
            )
            for i in range(3)
        ]
        
        with patch('api.webhooks.services.replay.ReplayService.create_replay_batch') as mock_create:
            mock_create.return_value = Mock(id='batch-123')
            
            result = replay_tasks.create_replay_batch.delay(
                delivery_log_ids=[log.id for log in delivery_logs],
                replayed_by=self.user.id,
                reason='Batch replay'
            )
            
            self.assertTrue(result.successful())
            mock_create.assert_called_once()
    
    def test_cleanup_old_replays_success(self):
        """Test successful cleanup of old replays."""
        with patch('api.webhooks.services.replay.ReplayService.cleanup_old_replays') as mock_cleanup:
            mock_cleanup.return_value = {'cleaned_count': 5}
            
            result = replay_tasks.cleanup_old_replays.delay(days=30)
            
            self.assertTrue(result.successful())
            mock_cleanup.assert_called_once()
    
    def test_cleanup_old_replay_batches_success(self):
        """Test successful cleanup of old replay batches."""
        with patch('api.webhooks.services.replay.ReplayService.cleanup_old_replay_batches') as mock_cleanup:
            mock_cleanup.return_value = {'cleaned_count': 3}
            
            result = replay_tasks.cleanup_old_replay_batches.delay(days=30)
            
            self.assertTrue(result.successful())
            mock_cleanup.assert_called_once()


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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
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
            created_by=self.user,
        )
        
        # Create recent delivery log
        recent_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            created_at=timezone.now() - timedelta(days=1),
            created_by=self.user,
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
            created_by=self.user,
        )
        
        # Create recent health log
        recent_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timedelta(days=1),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user,
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
            created_by=self.user,
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
            created_by=self.user,
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
        """Test successful archiving of old data."""
        with patch('api.webhooks.services.cleanup.ArchiveService.archive_delivery_logs') as mock_archive:
            mock_archive.return_value = {'archived_count': 100}
            
            result = cleanup_tasks.archive_old_data.delay(days=30)
            
            self.assertTrue(result.successful())
            mock_archive.assert_called_once()


# Additional task tests can be added here for any remaining tasks

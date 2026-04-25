"""Test Health Monitor for Webhooks System

This module contains tests for the webhook health monitor
including endpoint health checks, monitoring, and alerting.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..services.analytics import HealthMonitorService
from ..models import (
    WebhookEndpoint, WebhookHealthLog, WebhookDeliveryLog,
    WebhookAnalytics, WebhookRetryAnalysis
)
from ..constants import (
    WebhookStatus, DeliveryStatus, HttpMethod
)

User = get_user_model()


class HealthMonitorServiceTest(TestCase):
    """Test cases for HealthMonitorService."""
    
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
        self.health_monitor = HealthMonitorService()
    
    def test_check_endpoint_health_success(self):
        """Test successful endpoint health check."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            health_status = self.health_monitor.check_endpoint_health(self.endpoint)
            
            self.assertTrue(health_status['is_healthy'])
            self.assertEqual(health_status['status_code'], 200)
            self.assertEqual(health_status['response_time_ms'], 100)
            self.assertIsNone(health_status['error'])
    
    def test_check_endpoint_health_failure(self):
        """Test endpoint health check failure."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            health_status = self.health_monitor.check_endpoint_health(self.endpoint)
            
            self.assertFalse(health_status['is_healthy'])
            self.assertEqual(health_status['status_code'], 500)
            self.assertEqual(health_status['response_time_ms'], 100)
            self.assertIsNone(health_status['error'])
    
    def test_check_endpoint_health_timeout(self):
        """Test endpoint health check timeout."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('Connection timeout')
            
            health_status = self.health_monitor.check_endpoint_health(self.endpoint)
            
            self.assertFalse(health_status['is_healthy'])
            self.assertIsNone(health_status['status_code'])
            self.assertIsNone(health_status['response_time_ms'])
            self.assertIn('Connection timeout', health_status['error'])
    
    def test_check_endpoint_health_with_custom_timeout(self):
        """Test endpoint health check with custom timeout."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            health_status = self.health_monitor.check_endpoint_health(
                self.endpoint,
                timeout_seconds=10
            )
            
            self.assertTrue(health_status['is_healthy'])
            mock_get.assert_called_once_with(
                self.endpoint.url,
                timeout=10,
                headers={'User-Agent': 'Webhooks-Health-Check/1.0'},
                verify=self.endpoint.verify_ssl
            )
    
    def test_check_endpoint_health_with_custom_headers(self):
        """Test endpoint health check with custom headers."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            custom_headers = {'X-Custom-Header': 'test-value'}
            health_status = self.health_monitor.check_endpoint_health(
                self.endpoint,
                headers=custom_headers
            )
            
            self.assertTrue(health_status['is_healthy'])
            mock_get.assert_called_once()
            
            # Check that custom headers were included
            call_args = mock_get.call_args
            self.assertIn('X-Custom-Header', call_args[1]['headers'])
    
    def test_check_endpoint_health_with_ssl_verification_disabled(self):
        """Test endpoint health check with SSL verification disabled."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            verify_ssl=False,
            created_by=self.user,
        )
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            health_status = self.health_monitor.check_endpoint_health(endpoint)
            
            self.assertTrue(health_status['is_healthy'])
            mock_get.assert_called_once()
            
            # Check that SSL verification was disabled
            call_args = mock_get.call_args
            self.assertFalse(call_args[1]['verify'])
    
    def test_check_endpoint_health_creates_log(self):
        """Test that health check creates health log."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            self.health_monitor.check_endpoint_health(self.endpoint)
            
            # Check that health log was created
            health_log = WebhookHealthLog.objects.get(endpoint=self.endpoint)
            self.assertTrue(health_log.is_healthy)
            self.assertEqual(health_log.status_code, 200)
            self.assertEqual(health_log.response_time_ms, 100)
            self.assertIsNone(health_log.error)
    
    def test_check_endpoint_health_creates_error_log(self):
        """Test that health check creates error log on failure."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('Connection error')
            
            self.health_monitor.check_endpoint_health(self.endpoint)
            
            # Check that health log was created
            health_log = WebhookHealthLog.objects.get(endpoint=self.endpoint)
            self.assertFalse(health_log.is_healthy)
            self.assertIsNone(health_log.status_code)
            self.assertIsNone(health_log.response_time_ms)
            self.assertIn('Connection error', health_log.error)
    
    def test_get_endpoint_health_summary(self):
        """Test getting endpoint health summary."""
        # Create health logs
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=10),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=5),
            is_healthy=True,
            response_time_ms=150,
            status_code=200,
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=2),
            is_healthy=False,
            response_time_ms=5000,
            status_code=500,
            error='Server error',
            created_by=self.user
        )
        
        summary = self.health_monitor.get_endpoint_health_summary(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(summary['total_checks'], 3)
        self.assertEqual(summary['healthy_checks'], 2)
        self.assertEqual(summary['unhealthy_checks'], 1)
        self.assertEqual(summary['uptime_percentage'], 66.67)
        self.assertEqual(summary['avg_response_time_ms'], 1750.0)
        self.assertEqual(summary['last_check_status'], 'unhealthy')
    
    def test_get_endpoint_health_summary_no_logs(self):
        """Test getting endpoint health summary with no logs."""
        summary = self.health_monitor.get_endpoint_health_summary(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(summary['total_checks'], 0)
        self.assertEqual(summary['healthy_checks'], 0)
        self.assertEqual(summary['unhealthy_checks'], 0)
        self.assertEqual(summary['uptime_percentage'], 0.0)
        self.assertIsNone(summary['avg_response_time_ms'])
        self.assertIsNone(summary['last_check_status'])
    
    def test_get_endpoint_health_summary_all_healthy(self):
        """Test getting endpoint health summary with all healthy checks."""
        # Create healthy logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 10),
                is_healthy=True,
                response_time_ms=100 + i * 10,
                status_code=200,
                created_by=self.user
            )
        
        summary = self.health_monitor.get_endpoint_health_summary(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(summary['total_checks'], 5)
        self.assertEqual(summary['healthy_checks'], 5)
        self.assertEqual(summary['unhealthy_checks'], 0)
        self.assertEqual(summary['uptime_percentage'], 100.0)
        self.assertEqual(summary['avg_response_time_ms'], 120.0)
        self.assertEqual(summary['last_check_status'], 'healthy')
    
    def test_get_endpoint_health_summary_all_unhealthy(self):
        """Test getting endpoint health summary with all unhealthy checks."""
        # Create unhealthy logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 10),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user
            )
        
        summary = self.health_monitor.get_endpoint_health_summary(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(summary['total_checks'], 5)
        self.assertEqual(summary['healthy_checks'], 0)
        self.assertEqual(summary['unhealthy_checks'], 5)
        self.assertEqual(summary['uptime_percentage'], 0.0)
        self.assertEqual(summary['avg_response_time_ms'], 5000.0)
        self.assertEqual(summary['last_check_status'], 'unhealthy')
    
    def test_check_all_endpoints_health(self):
        """Test checking health of all endpoints."""
        # Create additional endpoint
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            results = self.health_monitor.check_all_endpoints_health()
            
            self.assertEqual(len(results), 2)
            self.assertTrue(all(result['is_healthy'] for result in results))
            self.assertEqual(mock_get.call_count, 2)
    
    def test_check_all_endpoints_health_with_failures(self):
        """Test checking health of all endpoints with failures."""
        # Create additional endpoint
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        with patch('requests.get') as mock_get:
            # First endpoint succeeds, second fails
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.elapsed.total_seconds.return_value = 0.1
            
            mock_response_failure = Mock()
            mock_response_failure.status_code = 500
            mock_response_failure.elapsed.total_seconds.return_value = 0.1
            
            mock_get.side_effect = [mock_response_success, mock_response_failure]
            
            results = self.health_monitor.check_all_endpoints_health()
            
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0]['is_healthy'])
            self.assertFalse(results[1]['is_healthy'])
            self.assertEqual(mock_get.call_count, 2)
    
    def test_get_system_health_overview(self):
        """Test getting system health overview."""
        # Create multiple endpoints
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        endpoint3 = WebhookEndpoint.objects.create(
            url='https://example3.com/webhook',
            secret='test-secret-key-3',
            status=WebhookStatus.DISABLED,
            created_by=self.user,
        )
        
        # Create health logs
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=10),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=endpoint2,
            checked_at=timezone.now() - timezone.timedelta(minutes=5),
            is_healthy=False,
            response_time_ms=5000,
            status_code=500,
            error='Server error',
            created_by=self.user
        )
        
        overview = self.health_monitor.get_system_health_overview()
        
        self.assertEqual(overview['total_endpoints'], 3)
        self.assertEqual(overview['active_endpoints'], 2)
        self.assertEqual(overview['healthy_endpoints'], 1)
        self.assertEqual(overview['unhealthy_endpoints'], 1)
        self.assertEqual(overview['overall_uptime_percentage'], 50.0)
        self.assertEqual(overview['avg_response_time_ms'], 2550.0)
    
    def test_get_endpoint_health_trends(self):
        """Test getting endpoint health trends."""
        # Create health logs over time
        for i in range(24):  # 24 hours of data
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(hours=i),
                is_healthy=i % 3 != 0,  # 2 out of 3 are healthy
                response_time_ms=100 + i * 10,
                status_code=200 if i % 3 != 0 else 500,
                created_by=self.user
            )
        
        trends = self.health_monitor.get_endpoint_health_trends(
            self.endpoint,
            hours=24
        )
        
        self.assertEqual(len(trends), 24)
        self.assertEqual(trends[-1]['healthy_checks'], 16)
        self.assertEqual(trends[-1]['unhealthy_checks'], 8)
        self.assertEqual(trends[-1]['uptime_percentage'], 66.67)
    
    def test_auto_suspend_unhealthy_endpoint(self):
        """Test auto-suspending unhealthy endpoint."""
        # Create consecutive unhealthy health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user
            )
        
        result = self.health_monitor.auto_suspend_unhealthy_endpoint(
            self.endpoint,
            consecutive_failures=3
        )
        
        self.assertTrue(result['suspended'])
        
        # Check that endpoint was suspended
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.SUSPENDED)
    
    def test_auto_suspend_unhealthy_endpoint_not_enough_failures(self):
        """Test auto-suspending unhealthy endpoint with not enough failures."""
        # Create consecutive unhealthy health logs
        for i in range(2):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user
            )
        
        result = self.health_monitor.auto_suspend_unhealthy_endpoint(
            self.endpoint,
            consecutive_failures=3
        )
        
        self.assertFalse(result['suspended'])
        
        # Check that endpoint was not suspended
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.ACTIVE)
    
    def test_auto_suspend_unhealthy_endpoint_already_suspended(self):
        """Test auto-suspending already suspended endpoint."""
        self.endpoint.status = WebhookStatus.SUSPENDED
        self.endpoint.save()
        
        result = self.health_monitor.auto_suspend_unhealthy_endpoint(
            self.endpoint,
            consecutive_failures=3
        )
        
        self.assertFalse(result['suspended'])
        self.assertIn('already suspended', result['reason'])
    
    def test_get_endpoint_health_alerts(self):
        """Test getting endpoint health alerts."""
        # Create health logs with issues
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=10),
            is_healthy=False,
            response_time_ms=5000,
            status_code=500,
            error='Server error',
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=5),
            is_healthy=False,
            response_time_ms=10000,
            status_code=503,
            error='Service unavailable',
            created_by=self.user
        )
        
        alerts = self.health_monitor.get_endpoint_health_alerts(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]['type'], 'consecutive_failures')
        self.assertEqual(alerts[1]['type'], 'high_response_time')
    
    def test_get_endpoint_health_alerts_no_alerts(self):
        """Test getting endpoint health alerts with no alerts."""
        # Create healthy health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 10),
                is_healthy=True,
                response_time_ms=100,
                status_code=200,
                created_by=self.user
            )
        
        alerts = self.health_monitor.get_endpoint_health_alerts(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(len(alerts), 0)
    
    def test_schedule_health_check(self):
        """Test scheduling health check."""
        with patch('api.webhooks.tasks.health_check_tasks.schedule_health_check') as mock_task:
            mock_task.return_value = Mock(id='task-123')
            
            result = self.health_monitor.schedule_health_check(
                self.endpoint,
                interval_minutes=5
            )
            
            self.assertTrue(result['scheduled'])
            self.assertEqual(result['task_id'], 'task-123')
            mock_task.assert_called_once()
    
    def test_cancel_health_check(self):
        """Test canceling health check."""
        with patch('api.webhooks.tasks.health_check_tasks.cancel_health_check') as mock_task:
            mock_task.return_value = True
            
            result = self.health_monitor.cancel_health_check(
                self.endpoint,
                task_id='task-123'
            )
            
            self.assertTrue(result['cancelled'])
            mock_task.assert_called_once()
    
    def test_get_endpoint_health_metrics(self):
        """Test getting endpoint health metrics."""
        # Create health logs with various response times
        response_times = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]
        
        for i, response_time in enumerate(response_times):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=True,
                response_time_ms=response_time,
                status_code=200,
                created_by=self.user
            )
        
        metrics = self.health_monitor.get_endpoint_health_metrics(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(metrics['min_response_time_ms'], 100)
        self.assertEqual(metrics['max_response_time_ms'], 550)
        self.assertEqual(metrics['avg_response_time_ms'], 325.0)
        self.assertEqual(metrics['median_response_time_ms'], 325)
        self.assertEqual(metrics['p95_response_time_ms'], 525)
        self.assertEqual(metrics['p99_response_time_ms'], 545)
    
    def test_get_endpoint_health_metrics_no_data(self):
        """Test getting endpoint health metrics with no data."""
        metrics = self.health_monitor.get_endpoint_health_metrics(
            self.endpoint,
            hours=1
        )
        
        self.assertIsNone(metrics['min_response_time_ms'])
        self.assertIsNone(metrics['max_response_time_ms'])
        self.assertIsNone(metrics['avg_response_time_ms'])
        self.assertIsNone(metrics['median_response_time_ms'])
        self.assertIsNone(metrics['p95_response_time_ms'])
        self.assertIsNone(metrics['p99_response_time_ms'])
    
    def test_get_endpoint_health_score(self):
        """Test getting endpoint health score."""
        # Create health logs with mixed results
        for i in range(10):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=i < 8,  # 8 out of 10 are healthy
                response_time_ms=100 + i * 50,
                status_code=200 if i < 8 else 500,
                created_by=self.user
            )
        
        score = self.health_monitor.get_endpoint_health_score(
            self.endpoint,
            hours=1
        )
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertGreater(score, 70)  # Should be > 70% healthy
    
    def test_get_endpoint_health_score_perfect(self):
        """Test getting endpoint health score with perfect health."""
        # Create all healthy health logs
        for i in range(10):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=True,
                response_time_ms=100,
                status_code=200,
                created_by=self.user
            )
        
        score = self.health_monitor.get_endpoint_health_score(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(score, 100.0)
    
    def test_get_endpoint_health_score_zero(self):
        """Test getting endpoint health score with zero health."""
        # Create all unhealthy health logs
        for i in range(10):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user
            )
        
        score = self.health_monitor.get_endpoint_health_score(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(score, 0.0)
    
    def test_get_endpoint_health_score_no_data(self):
        """Test getting endpoint health score with no data."""
        score = self.health_monitor.get_endpoint_health_score(
            self.endpoint,
            hours=1
        )
        
        self.assertIsNone(score)
    
    def test_update_endpoint_health_status(self):
        """Test updating endpoint health status."""
        # Create health logs
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=10),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(minutes=5),
            is_healthy=False,
            response_time_ms=5000,
            status_code=500,
            error='Server error',
            created_by=self.user
        )
        
        self.health_monitor.update_endpoint_health_status(self.endpoint)
        
        # Check that endpoint status was updated based on health
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.SUSPENDED)
    
    def test_update_endpoint_health_status_healthy(self):
        """Test updating endpoint health status when healthy."""
        # Create healthy health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=True,
                response_time_ms=100,
                status_code=200,
                created_by=self.user
            )
        
        # Start with suspended status
        self.endpoint.status = WebhookStatus.SUSPENDED
        self.endpoint.save()
        
        self.health_monitor.update_endpoint_health_status(self.endpoint)
        
        # Check that endpoint status was updated to active
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status, WebhookStatus.ACTIVE)
    
    def test_cleanup_old_health_logs(self):
        """Test cleanup of old health logs."""
        # Create health logs at different times
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(days=10),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user
        )
        
        WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            checked_at=timezone.now() - timezone.timedelta(days=1),
            is_healthy=True,
            response_time_ms=100,
            status_code=200,
            created_by=self.user
        )
        
        result = self.health_monitor.cleanup_old_health_logs(days=7)
        
        self.assertEqual(result['cleaned_count'], 1)
        
        # Check that only recent log remains
        remaining_logs = WebhookHealthLog.objects.filter(endpoint=self.endpoint)
        self.assertEqual(remaining_logs.count(), 1)
    
    def test_get_health_check_recommendations(self):
        """Test getting health check recommendations."""
        # Create health logs with issues
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
                created_by=self.user
            )
        
        recommendations = self.health_monitor.get_health_check_recommendations(
            self.endpoint,
            hours=1
        )
        
        self.assertIn('consecutive_failures', recommendations)
        self.assertIn('high_failure_rate', recommendations)
        self.assertIn('slow_response_times', recommendations)
    
    def test_get_health_check_recommendations_healthy(self):
        """Test getting health check recommendations for healthy endpoint."""
        # Create healthy health logs
        for i in range(5):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timezone.timedelta(minutes=i * 5),
                is_healthy=True,
                response_time_ms=100,
                status_code=200,
                created_by=self.user
            )
        
        recommendations = self.health_monitor.get_health_check_recommendations(
            self.endpoint,
            hours=1
        )
        
        self.assertEqual(recommendations, [])
    
    def test_health_check_performance(self):
        """Test health check performance."""
        import time
        
        # Create multiple endpoints
        endpoints = []
        for i in range(10):
            endpoint = WebhookEndpoint.objects.create(
                url=f'https://example{i}.com/webhook',
                secret=f'test-secret-key-{i}',
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
            endpoints.append(endpoint)
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response
            
            start_time = time.time()
            
            results = self.health_monitor.check_all_endpoints_health()
            
            end_time = time.time()
            
            self.assertEqual(len(results), 10)
            self.assertTrue(all(result['is_healthy'] for result in results))
            self.assertLess(end_time - start_time, 5.0)  # Should complete in < 5 seconds
            self.assertEqual(mock_get.call_count, 10)

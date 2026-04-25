"""Test Analytics for Webhooks System

This module contains tests for the webhook analytics service
including metrics calculation, aggregation, and reporting.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from ..services.analytics import WebhookAnalyticsService
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit
)
from ..constants import (
    WebhookStatus, DeliveryStatus, HttpMethod
)

User = get_user_model()


class WebhookAnalyticsServiceTest(TestCase):
    """Test cases for WebhookAnalyticsService."""
    
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
        self.analytics_service = WebhookAnalyticsService()
    
    def test_calculate_endpoint_analytics_success(self):
        """Test successful endpoint analytics calculation."""
        # Create delivery logs
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
        
        analytics = self.analytics_service.calculate_endpoint_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_sent'], 10)
        self.assertEqual(analytics['success_count'], 8)
        self.assertEqual(analytics['failed_count'], 2)
        self.assertEqual(analytics['success_rate'], 80.0)
        self.assertEqual(analytics['avg_response_time_ms'], 145.0)
        self.assertEqual(analytics['min_response_time_ms'], 100)
        self.assertEqual(analytics['max_response_time_ms'], 190)
    
    def test_calculate_endpoint_analytics_no_logs(self):
        """Test endpoint analytics calculation with no logs."""
        analytics = self.analytics_service.calculate_endpoint_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_sent'], 0)
        self.assertEqual(analytics['success_count'], 0)
        self.assertEqual(analytics['failed_count'], 0)
        self.assertEqual(analytics['success_rate'], 0.0)
        self.assertIsNone(analytics['avg_response_time_ms'])
        self.assertIsNone(analytics['min_response_time_ms'])
        self.assertIsNone(analytics['max_response_time_ms'])
    
    def test_calculate_endpoint_analytics_with_filters(self):
        """Test endpoint analytics calculation with filters."""
        # Create delivery logs with different event types
        for i in range(10):
            event_type = 'user.created' if i < 6 else 'user.updated'
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type=event_type,
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100,
                created_at=timezone.now() - timedelta(hours=i),
                created_by=self.user,
            )
        
        analytics = self.analytics_service.calculate_endpoint_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now(),
            event_type_filter='user.created'
        )
        
        self.assertEqual(analytics['total_sent'], 6)
        self.assertEqual(analytics['success_count'], 6)
        self.assertEqual(analytics['failed_count'], 0)
        self.assertEqual(analytics['success_rate'], 100.0)
    
    def test_generate_daily_analytics(self):
        """Test generating daily analytics."""
        # Create delivery logs for multiple days
        for day in range(3):
            for i in range(5):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS if i < 4 else DeliveryStatus.FAILED,
                    response_code=200 if i < 4 else 500,
                    duration_ms=100 + i * 10,
                    created_at=timezone.now() - timedelta(days=day),
                    created_by=self.user,
                )
        
        analytics_records = self.analytics_service.generate_daily_analytics(
            endpoint=self.endpoint,
            days=3
        )
        
        self.assertEqual(len(analytics_records), 3)
        
        # Check that analytics records were created
        for record in analytics_records:
            self.assertEqual(record.endpoint, self.endpoint)
            self.assertEqual(record.total_sent, 5)
            self.assertEqual(record.success_count, 4)
            self.assertEqual(record.failed_count, 1)
            self.assertEqual(record.success_rate, 80.0)
    
    def test_generate_daily_analytics_existing_record(self):
        """Test generating daily analytics with existing record."""
        # Create existing analytics record
        existing_analytics = WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date(),
            total_sent=5,
            success_count=4,
            failed_count=1,
            avg_latency_ms=120.0,
            created_by=self.user
        )
        
        # Create new delivery logs
        for i in range(3):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=150,
                created_at=timezone.now(),
                created_by=self.user,
            )
        
        analytics_records = self.analytics_service.generate_daily_analytics(
            endpoint=self.endpoint,
            days=1
        )
        
        self.assertEqual(len(analytics_records), 1)
        
        # Check that existing record was updated
        updated_analytics = analytics_records[0]
        self.assertEqual(updated_analytics.id, existing_analytics.id)
        self.assertEqual(updated_analytics.total_sent, 8)  # 5 + 3
        self.assertEqual(updated_analytics.success_count, 7)  # 4 + 3
    
    def test_calculate_event_type_analytics(self):
        """Test calculating event type analytics."""
        # Create delivery logs for different event types
        event_types = ['user.created', 'user.updated', 'user.deleted']
        for event_type in event_types:
            for i in range(5):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type=event_type,
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS if i < 4 else DeliveryStatus.FAILED,
                    response_code=200 if i < 4 else 500,
                    duration_ms=100 + i * 10,
                    created_at=timezone.now() - timedelta(hours=i),
                    created_by=self.user,
                )
        
        analytics = self.analytics_service.calculate_event_type_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(len(analytics), 3)
        
        for event_type, stats in analytics.items():
            self.assertEqual(stats['total_sent'], 5)
            self.assertEqual(stats['success_count'], 4)
            self.assertEqual(stats['failed_count'], 1)
            self.assertEqual(stats['success_rate'], 80.0)
    
    def test_calculate_event_type_analytics_no_logs(self):
        """Test calculating event type analytics with no logs."""
        analytics = self.analytics_service.calculate_event_type_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics, {})
    
    def test_calculate_hourly_analytics(self):
        """Test calculating hourly analytics."""
        # Create delivery logs for different hours
        for hour in range(24):
            for i in range(2):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS if i == 0 else DeliveryStatus.FAILED,
                    response_code=200 if i == 0 else 500,
                    duration_ms=100 + i * 10,
                    created_at=timezone.now() - timedelta(hours=hour),
                    created_by=self.user,
                )
        
        analytics = self.analytics_service.calculate_hourly_analytics(
            endpoint=self.endpoint,
            hours=24
        )
        
        self.assertEqual(len(analytics), 24)
        
        for hour, stats in analytics.items():
            self.assertEqual(stats['total_sent'], 2)
            self.assertEqual(stats['success_count'], 1)
            self.assertEqual(stats['failed_count'], 1)
            self.assertEqual(stats['success_rate'], 50.0)
    
    def test_calculate_response_time_distribution(self):
        """Test calculating response time distribution."""
        response_times = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
        
        for response_time in response_times:
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=response_time,
                created_at=timezone.now() - timedelta(minutes=1),
                created_by=self.user,
            )
        
        distribution = self.analytics_service.calculate_response_time_distribution(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(distribution['total_requests'], 10)
        self.assertEqual(distribution['min_response_time_ms'], 50)
        self.assertEqual(distribution['max_response_time_ms'], 500)
        self.assertEqual(distribution['avg_response_time_ms'], 275.0)
        self.assertEqual(distribution['median_response_time_ms'], 275)
        self.assertEqual(distribution['p95_response_time_ms'], 475)
        self.assertEqual(distribution['p99_response_time_ms'], 495)
    
    def test_calculate_response_time_distribution_no_logs(self):
        """Test calculating response time distribution with no logs."""
        distribution = self.analytics_service.calculate_response_time_distribution(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(distribution['total_requests'], 0)
        self.assertIsNone(distribution['min_response_time_ms'])
        self.assertIsNone(distribution['max_response_time_ms'])
        self.assertIsNone(distribution['avg_response_time_ms'])
        self.assertIsNone(distribution['median_response_time_ms'])
        self.assertIsNone(distribution['p95_response_time_ms'])
        self.assertIsNone(distribution['p99_response_time_ms'])
    
    def test_calculate_error_rate_analytics(self):
        """Test calculating error rate analytics."""
        # Create delivery logs with different error codes
        error_codes = [200, 200, 200, 400, 401, 403, 404, 500, 502, 503]
        
        for error_code in error_codes:
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345},
                status=DeliveryStatus.SUCCESS if error_code == 200 else DeliveryStatus.FAILED,
                response_code=error_code,
                duration_ms=100,
                created_at=timezone.now() - timedelta(minutes=1),
                created_by=self.user,
            )
        
        analytics = self.analytics_service.calculate_error_rate_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_requests'], 10)
        self.assertEqual(analytics['success_count'], 3)
        self.assertEqual(analytics['error_count'], 7)
        self.assertEqual(analytics['error_rate'], 70.0)
        
        # Check error breakdown
        error_breakdown = analytics['error_breakdown']
        self.assertEqual(error_breakdown['400'], 1)
        self.assertEqual(error_breakdown['401'], 1)
        self.assertEqual(error_breakdown['403'], 1)
        self.assertEqual(error_breakdown['404'], 1)
        self.assertEqual(error_breakdown['500'], 1)
        self.assertEqual(error_breakdown['502'], 1)
        self.assertEqual(error_breakdown['503'], 1)
    
    def test_calculate_error_rate_analytics_no_errors(self):
        """Test calculating error rate analytics with no errors."""
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100,
                created_at=timezone.now() - timedelta(minutes=1),
                created_by=self.user,
            )
        
        analytics = self.analytics_service.calculate_error_rate_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_requests'], 5)
        self.assertEqual(analytics['success_count'], 5)
        self.assertEqual(analytics['error_count'], 0)
        self.assertEqual(analytics['error_rate'], 0.0)
        self.assertEqual(analytics['error_breakdown'], {})
    
    def test_calculate_throughput_analytics(self):
        """Test calculating throughput analytics."""
        # Create delivery logs over time
        for hour in range(24):
            for i in range(5):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS,
                    response_code=200,
                    duration_ms=100,
                    created_at=timezone.now() - timedelta(hours=hour),
                    created_by=self.user,
                )
        
        analytics = self.analytics_service.calculate_throughput_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_requests'], 120)
        self.assertEqual(analytics['avg_requests_per_hour'], 5.0)
        self.assertEqual(analytics['max_requests_per_hour'], 5)
        self.assertEqual(analytics['min_requests_per_hour'], 5)
        self.assertEqual(analytics['avg_requests_per_minute'], 0.08333333333333333)
    
    def test_calculate_throughput_analytics_variable_throughput(self):
        """Test calculating throughput analytics with variable throughput."""
        # Create delivery logs with variable throughput
        for hour in range(24):
            requests_per_hour = 2 + (hour % 4)  # 2-5 requests per hour
            for i in range(requests_per_hour):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS,
                    response_code=200,
                    duration_ms=100,
                    created_at=timezone.now() - timedelta(hours=hour),
                    created_by=self.user,
                )
        
        analytics = self.analytics_service.calculate_throughput_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_requests'], 72)
        self.assertEqual(analytics['avg_requests_per_hour'], 3.0)
        self.assertEqual(analytics['max_requests_per_hour'], 5)
        self.assertEqual(analytics['min_requests_per_hour'], 2)
    
    def test_calculate_throughput_analytics_no_logs(self):
        """Test calculating throughput analytics with no logs."""
        analytics = self.analytics_service.calculate_throughput_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(analytics['total_requests'], 0)
        self.assertEqual(analytics['avg_requests_per_hour'], 0.0)
        self.assertEqual(analytics['max_requests_per_hour'], 0)
        self.assertEqual(analytics['min_requests_per_hour'], 0)
        self.assertEqual(analytics['avg_requests_per_minute'], 0.0)
    
    def test_calculate_endpoint_health_metrics(self):
        """Test calculating endpoint health metrics."""
        # Create health logs
        for i in range(10):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                checked_at=timezone.now() - timedelta(hours=i),
                is_healthy=i < 8,  # 8 out of 10 are healthy
                response_time_ms=100 + i * 10,
                status_code=200 if i < 8 else 500,
                created_by=self.user,
            )
        
        metrics = self.analytics_service.calculate_endpoint_health_metrics(
            endpoint=self.endpoint,
            hours=24
        )
        
        self.assertEqual(metrics['total_checks'], 10)
        self.assertEqual(metrics['healthy_checks'], 8)
        self.assertEqual(metrics['unhealthy_checks'], 2)
        self.assertEqual(metrics['uptime_percentage'], 80.0)
        self.assertEqual(metrics['avg_response_time_ms'], 145.0)
        self.assertEqual(metrics['min_response_time_ms'], 100)
        self.assertEqual(metrics['max_response_time_ms'], 190)
    
    def test_calculate_endpoint_health_metrics_no_logs(self):
        """Test calculating endpoint health metrics with no logs."""
        metrics = self.analytics_service.calculate_endpoint_health_metrics(
            endpoint=self.endpoint,
            hours=24
        )
        
        self.assertEqual(metrics['total_checks'], 0)
        self.assertEqual(metrics['healthy_checks'], 0)
        self.assertEqual(metrics['unhealthy_checks'], 0)
        self.assertEqual(metrics['uptime_percentage'], 0.0)
        self.assertIsNone(metrics['avg_response_time_ms'])
        self.assertIsNone(metrics['min_response_time_ms'])
        self.assertIsNone(metrics['max_response_time_ms'])
    
    def test_calculate_system_overview_analytics(self):
        """Test calculating system overview analytics."""
        # Create multiple endpoints
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        # Create delivery logs for both endpoints
        for endpoint in [self.endpoint, endpoint2]:
            for i in range(5):
                WebhookDeliveryLog.objects.create(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS if i < 4 else DeliveryStatus.FAILED,
                    response_code=200 if i < 4 else 500,
                    duration_ms=100,
                    created_at=timezone.now() - timedelta(minutes=i),
                    created_by=self.user,
                )
        
        overview = self.analytics_service.calculate_system_overview_analytics(
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(overview['total_endpoints'], 2)
        self.assertEqual(overview['total_requests'], 10)
        self.assertEqual(overview['total_successes'], 8)
        self.assertEqual(overview['total_failures'], 2)
        self.assertEqual(overview['overall_success_rate'], 80.0)
        self.assertEqual(overview['avg_response_time_ms'], 100.0)
    
    def test_calculate_system_overview_analytics_no_endpoints(self):
        """Test calculating system overview analytics with no endpoints."""
        overview = self.analytics_service.calculate_system_overview_analytics(
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(overview['total_endpoints'], 0)
        self.assertEqual(overview['total_requests'], 0)
        self.assertEqual(overview['total_successes'], 0)
        self.assertEqual(overview['total_failures'], 0)
        self.assertEqual(overview['overall_success_rate'], 0.0)
        self.assertIsNone(overview['avg_response_time_ms'])
    
    def test_generate_analytics_report(self):
        """Test generating analytics report."""
        # Create delivery logs
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
        
        report = self.analytics_service.generate_analytics_report(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertIn('summary', report)
        self.assertIn('endpoint_analytics', report)
        self.assertIn('event_type_analytics', report)
        self.assertIn('hourly_analytics', report)
        self.assertIn('response_time_distribution', report)
        self.assertIn('error_rate_analytics', report)
        self.assertIn('throughput_analytics', report)
        self.assertIn('health_metrics', report)
        
        # Check summary
        summary = report['summary']
        self.assertEqual(summary['total_requests'], 10)
        self.assertEqual(summary['success_rate'], 80.0)
        self.assertEqual(summary['avg_response_time_ms'], 145.0)
    
    def test_generate_analytics_report_multiple_endpoints(self):
        """Test generating analytics report for multiple endpoints."""
        # Create additional endpoint
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        # Create delivery logs for both endpoints
        for endpoint in [self.endpoint, endpoint2]:
            for i in range(5):
                WebhookDeliveryLog.objects.create(
                    endpoint=endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS,
                    response_code=200,
                    duration_ms=100,
                    created_at=timezone.now() - timedelta(minutes=i),
                    created_by=self.user,
                )
        
        report = self.analytics_service.generate_analytics_report(
            endpoints=[self.endpoint, endpoint2],
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertIn('summary', report)
        self.assertIn('endpoint_analytics', report)
        self.assertEqual(len(report['endpoint_analytics']), 2)
        
        # Check summary
        summary = report['summary']
        self.assertEqual(summary['total_requests'], 10)
        self.assertEqual(summary['success_rate'], 100.0)
    
    def test_export_analytics_data(self):
        """Test exporting analytics data."""
        # Create delivery logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100,
                created_at=timezone.now() - timedelta(hours=i),
                created_by=self.user,
            )
        
        export_data = self.analytics_service.export_analytics_data(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now(),
            format='json'
        )
        
        self.assertIsInstance(export_data, str)
        self.assertIn('total_requests', export_data)
        self.assertIn('success_rate', export_data)
    
    def test_export_analytics_data_csv(self):
        """Test exporting analytics data as CSV."""
        # Create delivery logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100,
                created_at=timezone.now() - timedelta(hours=i),
                created_by=self.user,
            )
        
        export_data = self.analytics_service.export_analytics_data(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now(),
            format='csv'
        )
        
        self.assertIsInstance(export_data, str)
        self.assertIn('Date', export_data)
        self.assertIn('Total Requests', export_data)
        self.assertIn('Success Rate', export_data)
    
    def test_calculate_trend_analytics(self):
        """Test calculating trend analytics."""
        # Create delivery logs over multiple days
        for day in range(7):
            requests_per_day = 5 + (day % 3)  # 5-7 requests per day
            for i in range(requests_per_day):
                WebhookDeliveryLog.objects.create(
                    endpoint=self.endpoint,
                    event_type='user.created',
                    payload={'user_id': 12345 + i},
                    status=DeliveryStatus.SUCCESS if i < (requests_per_day - 1) else DeliveryStatus.FAILED,
                    response_code=200 if i < (requests_per_day - 1) else 500,
                    duration_ms=100,
                    created_at=timezone.now() - timedelta(days=day),
                    created_by=self.user,
                )
        
        trends = self.analytics_service.calculate_trend_analytics(
            endpoint=self.endpoint,
            days=7
        )
        
        self.assertEqual(len(trends), 7)
        self.assertIn('trend_direction', trends[0])
        self.assertIn('trend_percentage', trends[0])
    
    def test_calculate_trend_analytics_no_logs(self):
        """Test calculating trend analytics with no logs."""
        trends = self.analytics_service.calculate_trend_analytics(
            endpoint=self.endpoint,
            days=7
        )
        
        self.assertEqual(trends, {})
    
    def test_calculate_performance_metrics(self):
        """Test calculating performance metrics."""
        # Create delivery logs with varying response times
        response_times = [50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400, 425, 450, 475, 500]
        
        for response_time in response_times:
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=response_time,
                created_at=timezone.now() - timedelta(minutes=1),
                created_by=self.user,
            )
        
        metrics = self.analytics_service.calculate_performance_metrics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertEqual(metrics['min_response_time_ms'], 50)
        self.assertEqual(metrics['max_response_time_ms'], 500)
        self.assertEqual(metrics['avg_response_time_ms'], 275.0)
        self.assertEqual(metrics['median_response_time_ms'], 275)
        self.assertEqual(metrics['p95_response_time_ms'], 475)
        self.assertEqual(metrics['p99_response_time_ms'], 495)
        self.assertEqual(metrics['std_deviation'], 129.9)
    
    def test_calculate_performance_metrics_no_logs(self):
        """Test calculating performance metrics with no logs."""
        metrics = self.analytics_service.calculate_performance_metrics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        self.assertIsNone(metrics['min_response_time_ms'])
        self.assertIsNone(metrics['max_response_time_ms'])
        self.assertIsNone(metrics['avg_response_time_ms'])
        self.assertIsNone(metrics['median_response_time_ms'])
        self.assertIsNone(metrics['p95_response_time_ms'])
        self.assertIsNone(metrics['p99_response_time_ms'])
        self.assertIsNone(metrics['std_deviation'])
    
    def test_analytics_performance(self):
        """Test analytics calculation performance."""
        import time
        
        # Create large dataset
        for i in range(1000):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS if i % 10 < 8 else DeliveryStatus.FAILED,
                response_code=200 if i % 10 < 8 else 500,
                duration_ms=100 + (i % 100),
                created_at=timezone.now() - timedelta(minutes=i),
                created_by=self.user,
            )
        
        start_time = time.time()
        
        analytics = self.analytics_service.calculate_endpoint_analytics(
            endpoint=self.endpoint,
            date_from=timezone.now() - timedelta(days=1),
            date_to=timezone.now()
        )
        
        end_time = time.time()
        
        self.assertEqual(analytics['total_sent'], 1000)
        self.assertEqual(analytics['success_count'], 800)
        self.assertEqual(analytics['failed_count'], 200)
        self.assertEqual(analytics['success_rate'], 80.0)
        
        # Should complete in reasonable time (less than 2 seconds)
        self.assertLess(end_time - start_time, 2.0)
    
    def test_analytics_concurrent_safety(self):
        """Test analytics calculation concurrent safety."""
        import threading
        
        # Create delivery logs
        for i in range(100):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100,
                created_at=timezone.now() - timedelta(minutes=i),
                created_by=self.user,
            )
        
        results = []
        
        def calculate_analytics():
            analytics = self.analytics_service.calculate_endpoint_analytics(
                endpoint=self.endpoint,
                date_from=timezone.now() - timedelta(days=1),
                date_to=timezone.now()
            )
            results.append(analytics)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=calculate_analytics)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All calculations should succeed and return same results
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result['total_sent'] == 100 for result in results))
        self.assertTrue(all(result['success_rate'] == 100.0 for result in results))

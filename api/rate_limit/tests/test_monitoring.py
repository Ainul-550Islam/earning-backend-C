"""
Comprehensive monitoring tests for rate_limit module.

This test file covers all monitoring services, alert generation,
notification systems, metric collection, dashboard integration,
and alert routing.
"""

import json
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import time

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.monitoring import RateLimitMonitoringService
from api.rate_limit.alerts import RateLimitAlertManager
from api.rate_limit.metrics import RateLimitMetricsCollector
from api.rate_limit.notifications import RateLimitNotificationService

User = get_user_model()


class RateLimitMonitoringServiceTest(TestCase):
    """Test cases for RateLimitMonitoringService"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.monitoring_service = RateLimitMonitoringService()
        
        # Create test rate limit config
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
        # Create test rate limit logs
        for i in range(50):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/test/',
                method='GET',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0',
                status_code=200 if i < 45 else 429,
                is_allowed=i < 45
            )
            
    def test_collect_system_metrics(self):
        """Test system metrics collection"""
        metrics = self.monitoring_service.collect_system_metrics()
        
        # Verify metric structure
        self.assertIn('timestamp', metrics)
        self.assertIn('total_requests', metrics)
        self.assertIn('blocked_requests', metrics)
        self.assertIn('allowed_requests', metrics)
        self.assertIn('block_rate', metrics)
        self.assertIn('active_users', metrics)
        self.assertIn('active_configs', metrics)
        self.assertIn('system_health', metrics)
        
        # Verify metric values
        self.assertEqual(metrics['total_requests'], 50)
        self.assertEqual(metrics['blocked_requests'], 5)
        self.assertEqual(metrics['allowed_requests'], 45)
        self.assertEqual(metrics['block_rate'], 0.1)  # 5/50 = 0.1
        self.assertGreaterEqual(metrics['active_users'], 1)
        self.assertGreaterEqual(metrics['active_configs'], 1)
        
    def test_collect_user_metrics(self):
        """Test user-specific metrics collection"""
        user_metrics = self.monitoring_service.collect_user_metrics(
            self.regular_user.id
        )
        
        # Verify metric structure
        self.assertIn('user_id', user_metrics)
        self.assertIn('total_requests', user_metrics)
        self.assertIn('blocked_requests', user_metrics)
        self.assertIn('allowed_requests', user_metrics)
        self.assertIn('block_rate', user_metrics)
        self.assertIn('top_endpoints', user_metrics)
        self.assertIn('risk_level', user_metrics)
        
        # Verify metric values
        self.assertEqual(user_metrics['user_id'], self.regular_user.id)
        self.assertEqual(user_metrics['total_requests'], 50)
        self.assertEqual(user_metrics['blocked_requests'], 5)
        self.assertEqual(user_metrics['allowed_requests'], 45)
        self.assertEqual(user_metrics['block_rate'], 0.1)
        
    def test_collect_endpoint_metrics(self):
        """Test endpoint-specific metrics collection"""
        endpoint_metrics = self.monitoring_service.collect_endpoint_metrics(
            '/api/test/'
        )
        
        # Verify metric structure
        self.assertIn('endpoint', endpoint_metrics)
        self.assertIn('total_requests', endpoint_metrics)
        self.assertIn('blocked_requests', endpoint_metrics)
        self.assertIn('allowed_requests', endpoint_metrics)
        self.assertIn('block_rate', endpoint_metrics)
        self.assertIn('unique_users', endpoint_metrics)
        self.assertIn('average_response_time', endpoint_metrics)
        
        # Verify metric values
        self.assertEqual(endpoint_metrics['endpoint'], '/api/test/')
        self.assertEqual(endpoint_metrics['total_requests'], 50)
        self.assertEqual(endpoint_metrics['blocked_requests'], 5)
        self.assertEqual(endpoint_metrics['allowed_requests'], 45)
        self.assertEqual(endpoint_metrics['block_rate'], 0.1)
        
    def test_detect_anomalies(self):
        """Test anomaly detection in rate limit patterns"""
        # Create anomalous traffic pattern
        for i in range(100):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/anomaly/',
                method='POST',
                ip_address='192.168.1.200',
                user_agent='Bot/1.0',
                status_code=429,
                is_allowed=False
            )
            
        anomalies = self.monitoring_service.detect_anomalies()
        
        # Verify anomaly detection
        self.assertIsInstance(anomalies, list)
        self.assertGreater(len(anomalies), 0)
        
        # Check anomaly structure
        for anomaly in anomalies:
            self.assertIn('type', anomaly)
            self.assertIn('severity', anomaly)
            self.assertIn('description', anomaly)
            self.assertIn('timestamp', anomaly)
            self.assertIn('affected_entities', anomaly)
            
    def test_generate_health_report(self):
        """Test health report generation"""
        health_report = self.monitoring_service.generate_health_report()
        
        # Verify report structure
        self.assertIn('overall_status', health_report)
        self.assertIn('timestamp', health_report)
        self.assertIn('metrics', health_report)
        self.assertIn('alerts', health_report)
        self.assertIn('recommendations', health_report)
        
        # Verify metrics section
        metrics = health_report['metrics']
        self.assertIn('system', metrics)
        self.assertIn('users', metrics)
        self.assertIn('endpoints', metrics)
        self.assertIn('performance', metrics)
        
        # Verify alerts section
        alerts = health_report['alerts']
        self.assertIn('critical', alerts)
        self.assertIn('warning', alerts)
        self.assertIn('info', alerts)
        
    def test_monitor_rate_limit_violations(self):
        """Test monitoring of rate limit violations"""
        violations = self.monitoring_service.monitor_rate_limit_violations(
            timeframe_minutes=60
        )
        
        # Verify violations data
        self.assertIsInstance(violations, list)
        self.assertGreater(len(violations), 0)
        
        # Check violation structure
        for violation in violations:
            self.assertIn('user_id', violation)
            self.assertIn('endpoint', violation)
            self.assertIn('violation_count', violation)
            self.assertIn('first_violation', violation)
            self.assertIn('last_violation', violation)
            self.assertIn('severity', violation)
            
    def test_track_performance_metrics(self):
        """Test performance metrics tracking"""
        performance_metrics = self.monitoring_service.track_performance_metrics()
        
        # Verify performance metrics
        self.assertIn('response_times', performance_metrics)
        self.assertIn('throughput', performance_metrics)
        self.assertIn('error_rates', performance_metrics)
        self.assertIn('resource_usage', performance_metrics)
        
        # Verify response time metrics
        response_times = performance_metrics['response_times']
        self.assertIn('average', response_times)
        self.assertIn('median', response_times)
        self.assertIn('p95', response_times)
        self.assertIn('p99', response_times)
        
    def test_monitor_abuse_patterns(self):
        """Test abuse pattern monitoring"""
        # Create abuse pattern
        for i in range(20):
            AbuseReport.objects.create(
                reporter=self.admin_user,
                reported_ip='192.168.1.150',
                reason='suspicious_activity',
                description=f'Abuse report {i}'
            )
            
        abuse_patterns = self.monitoring_service.monitor_abuse_patterns()
        
        # Verify abuse patterns
        self.assertIsInstance(abuse_patterns, list)
        self.assertGreater(len(abuse_patterns), 0)
        
        # Check pattern structure
        for pattern in abuse_patterns:
            self.assertIn('pattern_type', pattern)
            self.assertIn('severity', pattern)
            self.assertIn('description', pattern)
            self.assertIn('affected_ips', pattern)
            self.assertIn('recommendation', pattern)
            
    def test_monitor_ip_reputation(self):
        """Test IP reputation monitoring"""
        # Create IP block list entries
        IPBlockList.objects.create(
            ip_address='192.168.1.100',
            reason='malicious_activity',
            block_type='permanent',
            created_by=self.admin_user
        )
        IPBlockList.objects.create(
            ip_address='192.168.1.101',
            reason='suspicious_activity',
            block_type='temporary',
            created_by=self.admin_user
        )
        
        ip_reputation = self.monitoring_service.monitor_ip_reputation()
        
        # Verify IP reputation data
        self.assertIsInstance(ip_reputation, dict)
        self.assertIn('blocked_ips', ip_reputation)
        self.assertIn('suspicious_ips', ip_reputation)
        self.assertIn('reputation_scores', ip_reputation)
        
        # Verify blocked IPs
        blocked_ips = ip_reputation['blocked_ips']
        self.assertGreater(len(blocked_ips), 0)
        
    def test_generate_alerts(self):
        """Test alert generation"""
        # Create conditions for alerts
        for i in range(100):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/alert_test/',
                method='GET',
                ip_address='192.168.1.300',
                user_agent='Test-Agent',
                status_code=429,
                is_allowed=False
            )
            
        alerts = self.monitoring_service.generate_alerts()
        
        # Verify alerts
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)
        
        # Check alert structure
        for alert in alerts:
            self.assertIn('alert_type', alert)
            self.assertIn('severity', alert)
            self.assertIn('title', alert)
            self.assertIn('message', alert)
            self.assertIn('timestamp', alert)
            self.assertIn('affected_entities', alert)
            
    def test_monitor_rate_limit_exceptions(self):
        """Test rate limit exceptions monitoring"""
        # Create rate limit exceptions
        RateLimitException.objects.create(
            user=self.regular_user,
            reason='api_client',
            description='API client requires higher limits',
            multiplier=2.0,
            created_by=self.admin_user
        )
        
        exceptions_monitoring = self.monitoring_service.monitor_rate_limit_exceptions()
        
        # Verify exceptions monitoring
        self.assertIsInstance(exceptions_monitoring, dict)
        self.assertIn('active_exceptions', exceptions_monitoring)
        self.assertIn('exception_types', exceptions_monitoring)
        self.assertIn('affected_users', exceptions_monitoring)
        
        # Verify active exceptions
        active_exceptions = exceptions_monitoring['active_exceptions']
        self.assertGreater(len(active_exceptions), 0)
        
    def test_collect_real_time_metrics(self):
        """Test real-time metrics collection"""
        real_time_metrics = self.monitoring_service.collect_real_time_metrics()
        
        # Verify real-time metrics
        self.assertIn('current_time', real_time_metrics)
        self.assertIn('requests_per_second', real_time_metrics)
        self.assertIn('active_connections', real_time_metrics)
        self.assertIn('memory_usage', real_time_metrics)
        self.assertIn('cpu_usage', real_time_metrics)
        
        # Verify RPS calculation
        rps = real_time_metrics['requests_per_second']
        self.assertIsInstance(rps, float)
        self.assertGreaterEqual(rps, 0)
        
    def test_monitor_system_resources(self):
        """Test system resource monitoring"""
        system_resources = self.monitoring_service.monitor_system_resources()
        
        # Verify system resources
        self.assertIn('memory', system_resources)
        self.assertIn('cpu', system_resources)
        self.assertIn('disk', system_resources)
        self.assertIn('network', system_resources)
        
        # Verify memory metrics
        memory = system_resources['memory']
        self.assertIn('total', memory)
        self.assertIn('used', memory)
        self.assertIn('available', memory)
        self.assertIn('usage_percentage', memory)
        
        # Verify CPU metrics
        cpu = system_resources['cpu']
        self.assertIn('usage_percentage', cpu)
        self.assertIn('load_average', cpu)
        
    def test_generate_dashboard_data(self):
        """Test dashboard data generation"""
        dashboard_data = self.monitoring_service.generate_dashboard_data()
        
        # Verify dashboard structure
        self.assertIn('overview', dashboard_data)
        self.assertIn('metrics', dashboard_data)
        self.assertIn('charts', dashboard_data)
        self.assertIn('alerts', dashboard_data)
        self.assertIn('last_updated', dashboard_data)
        
        # Verify overview section
        overview = dashboard_data['overview']
        self.assertIn('total_requests', overview)
        self.assertIn('blocked_requests', overview)
        self.assertIn('active_users', overview)
        self.assertIn('system_health', overview)
        
        # Verify charts section
        charts = dashboard_data['charts']
        self.assertIn('requests_timeline', charts)
        self.assertIn('block_rate_chart', charts)
        self.assertIn('top_endpoints', charts)
        self.assertIn('user_activity', charts)


class RateLimitAlertManagerTest(TestCase):
    """Test cases for RateLimitAlertManager"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.alert_manager = RateLimitAlertManager()
        
    def test_create_alert(self):
        """Test alert creation"""
        alert_data = {
            'alert_type': 'rate_limit_violation',
            'severity': 'high',
            'title': 'High Rate Limit Violation Detected',
            'message': 'User has exceeded rate limit significantly',
            'affected_entities': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/'
            },
            'metadata': {
                'violation_count': 50,
                'timeframe': '1 hour'
            }
        }
        
        alert = self.alert_manager.create_alert(alert_data)
        
        # Verify alert creation
        self.assertIsNotNone(alert.id)
        self.assertEqual(alert.alert_type, 'rate_limit_violation')
        self.assertEqual(alert.severity, 'high')
        self.assertEqual(alert.title, 'High Rate Limit Violation Detected')
        self.assertFalse(alert.is_resolved)
        
    def test_resolve_alert(self):
        """Test alert resolution"""
        # Create alert
        alert_data = {
            'alert_type': 'rate_limit_violation',
            'severity': 'medium',
            'title': 'Test Alert',
            'message': 'Test message',
            'affected_entities': {'user_id': self.regular_user.id}
        }
        
        alert = self.alert_manager.create_alert(alert_data)
        
        # Resolve alert
        resolution = self.alert_manager.resolve_alert(
            alert.id,
            resolved_by=self.admin_user,
            resolution_note='Issue resolved by updating rate limit config'
        )
        
        # Verify resolution
        self.assertTrue(resolution)
        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)
        self.assertEqual(alert.resolved_by, self.admin_user)
        self.assertEqual(alert.resolution_note, 'Issue resolved by updating rate limit config')
        
    def test_get_active_alerts(self):
        """Test retrieval of active alerts"""
        # Create multiple alerts
        for i in range(5):
            alert_data = {
                'alert_type': f'alert_type_{i}',
                'severity': 'medium',
                'title': f'Test Alert {i}',
                'message': f'Test message {i}',
                'affected_entities': {'user_id': self.regular_user.id}
            }
            self.alert_manager.create_alert(alert_data)
            
        # Get active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Verify active alerts
        self.assertEqual(len(active_alerts), 5)
        for alert in active_alerts:
            self.assertFalse(alert.is_resolved)
            
    def test_get_alerts_by_severity(self):
        """Test retrieval of alerts by severity"""
        # Create alerts with different severities
        severities = ['low', 'medium', 'high', 'critical']
        for severity in severities:
            alert_data = {
                'alert_type': 'test_alert',
                'severity': severity,
                'title': f'{severity.title()} Alert',
                'message': f'{severity.title()} severity alert',
                'affected_entities': {'user_id': self.regular_user.id}
            }
            self.alert_manager.create_alert(alert_data)
            
        # Get alerts by severity
        high_alerts = self.alert_manager.get_alerts_by_severity('high')
        critical_alerts = self.alert_manager.get_alerts_by_severity('critical')
        
        # Verify severity filtering
        self.assertEqual(len(high_alerts), 1)
        self.assertEqual(high_alerts[0].severity, 'high')
        self.assertEqual(len(critical_alerts), 1)
        self.assertEqual(critical_alerts[0].severity, 'critical')
        
    def test_auto_resolve_alerts(self):
        """Test automatic alert resolution"""
        # Create alert that should auto-resolve
        alert_data = {
            'alert_type': 'temporary_spike',
            'severity': 'medium',
            'title': 'Temporary Traffic Spike',
            'message': 'Temporary increase in traffic detected',
            'affected_entities': {'endpoint': '/api/test/'},
            'auto_resolve_minutes': 5
        }
        
        alert = self.alert_manager.create_alert(alert_data)
        
        # Simulate time passage
        with patch('django.utils.timezone.now') as mock_now:
            # Set time to 6 minutes after alert creation
            mock_now.return_value = alert.created_at + timedelta(minutes=6)
            
            # Run auto-resolution
            resolved_count = self.alert_manager.auto_resolve_alerts()
            
            # Verify auto-resolution
            self.assertGreaterEqual(resolved_count, 1)
            alert.refresh_from_db()
            self.assertTrue(alert.is_resolved)
            
    def test_alert_aggregation(self):
        """Test alert aggregation"""
        # Create multiple similar alerts
        for i in range(10):
            alert_data = {
                'alert_type': 'rate_limit_violation',
                'severity': 'medium',
                'title': 'Rate Limit Violation',
                'message': f'Violation {i}',
                'affected_entities': {
                    'user_id': self.regular_user.id,
                    'endpoint': '/api/test/'
                }
            }
            self.alert_manager.create_alert(alert_data)
            
        # Aggregate alerts
        aggregated_alerts = self.alert_manager.aggregate_alerts(
            group_by=['alert_type', 'affected_entities.user_id']
        )
        
        # Verify aggregation
        self.assertGreater(len(aggregated_alerts), 0)
        for group in aggregated_alerts:
            self.assertIn('alert_count', group)
            self.assertIn('alerts', group)
            self.assertGreater(group['alert_count'], 1)
            
    def test_alert_notification_routing(self):
        """Test alert notification routing"""
        # Create alert with notification routing
        alert_data = {
            'alert_type': 'critical_violation',
            'severity': 'critical',
            'title': 'Critical Rate Limit Violation',
            'message': 'Critical violation detected',
            'affected_entities': {'user_id': self.regular_user.id},
            'notification_channels': ['email', 'slack', 'webhook']
        }
        
        alert = self.alert_manager.create_alert(alert_data)
        
        # Route notifications
        with patch('api.rate_limit.notifications.RateLimitNotificationService.send_notification') as mock_send:
            mock_send.return_value = True
            
            routed = self.alert_manager.route_alert_notifications(alert.id)
            
            # Verify routing
            self.assertTrue(routed)
            self.assertEqual(mock_send.call_count, 3)  # 3 channels
            
    def test_alert_escalation(self):
        """Test alert escalation"""
        # Create alert that should escalate
        alert_data = {
            'alert_type': 'persistent_violation',
            'severity': 'medium',
            'title': 'Persistent Violation',
            'message': 'Violation continues for extended period',
            'affected_entities': {'user_id': self.regular_user.id},
            'escalation_rules': [
                {'condition': 'unresolved_minutes > 30', 'action': 'increase_severity'},
                {'condition': 'unresolved_minutes > 60', 'action': 'notify_admin'}
            ]
        }
        
        alert = self.alert_manager.create_alert(alert_data)
        
        # Simulate time passage and check escalation
        with patch('django.utils.timezone.now') as mock_now:
            # Set time to 35 minutes after alert creation
            mock_now.return_value = alert.created_at + timedelta(minutes=35)
            
            # Check escalation
            escalated = self.alert_manager.check_alert_escalation(alert.id)
            
            # Verify escalation
            self.assertTrue(escalated)
            alert.refresh_from_db()
            self.assertEqual(alert.severity, 'high')  # Should be escalated


class RateLimitMetricsCollectorTest(TestCase):
    """Test cases for RateLimitMetricsCollector"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.metrics_collector = RateLimitMetricsCollector()
        
    def test_collect_request_metrics(self):
        """Test request metrics collection"""
        # Create test requests
        endpoints = ['/api/test1/', '/api/test2/', '/api/test3/']
        for i, endpoint in enumerate(endpoints):
            for j in range(10):
                RateLimitLog.objects.create(
                    user=self.regular_user,
                    endpoint=endpoint,
                    method='GET',
                    ip_address='192.168.1.100',
                    user_agent='Mozilla/5.0',
                    status_code=200 if j < 8 else 429,
                    is_allowed=j < 8
                )
                
        metrics = self.metrics_collector.collect_request_metrics()
        
        # Verify metrics structure
        self.assertIn('total_requests', metrics)
        self.assertIn('successful_requests', metrics)
        self.assertIn('blocked_requests', metrics)
        self.assertIn('requests_by_endpoint', metrics)
        self.assertIn('requests_by_method', metrics)
        self.assertIn('requests_by_status', metrics)
        
        # Verify endpoint metrics
        endpoint_metrics = metrics['requests_by_endpoint']
        self.assertEqual(len(endpoint_metrics), 3)
        for endpoint in endpoints:
            self.assertIn(endpoint, endpoint_metrics)
            self.assertEqual(endpoint_metrics[endpoint]['total'], 10)
            
    def test_collect_user_metrics(self):
        """Test user metrics collection"""
        # Create multiple users
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'user_{i}',
                email=f'user_{i}@example.com',
                password='pass123'
            )
            users.append(user)
            
        # Create requests for each user
        for user in users:
            for i in range(20):
                RateLimitLog.objects.create(
                    user=user,
                    endpoint='/api/test/',
                    method='GET',
                    ip_address='192.168.1.100',
                    user_agent='Mozilla/5.0',
                    status_code=200 if i < 15 else 429,
                    is_allowed=i < 15
                )
                
        metrics = self.metrics_collector.collect_user_metrics()
        
        # Verify user metrics
        self.assertIn('total_users', metrics)
        self.assertIn('active_users', metrics)
        self.assertIn('users_by_request_count', metrics)
        self.assertIn('users_by_block_rate', metrics)
        
        # Verify user counts
        self.assertEqual(metrics['total_users'], 5)
        self.assertEqual(metrics['active_users'], 5)
        
    def test_collect_time_series_metrics(self):
        """Test time series metrics collection"""
        # Create requests over time
        base_time = timezone.now() - timedelta(hours=2)
        for i in range(120):  # 2 hours of data
            request_time = base_time + timedelta(minutes=i)
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/test/',
                method='GET',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0',
                status_code=200,
                is_allowed=True,
                created_at=request_time
            )
            
        metrics = self.metrics_collector.collect_time_series_metrics(
            interval_minutes=30
        )
        
        # Verify time series structure
        self.assertIn('intervals', metrics)
        self.assertIn('summary', metrics)
        
        # Verify intervals
        intervals = metrics['intervals']
        self.assertEqual(len(intervals), 4)  # 2 hours / 30 minutes = 4 intervals
        
        for interval in intervals:
            self.assertIn('start_time', interval)
            self.assertIn('end_time', interval)
            self.assertIn('request_count', interval)
            self.assertIn('block_rate', interval)
            
    def test_collect_performance_metrics(self):
        """Test performance metrics collection"""
        # Create requests with response times
        response_times = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550]  # ms
        for i, response_time in enumerate(response_times):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/test/',
                method='GET',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0',
                status_code=200,
                is_allowed=True,
                response_time=response_time
            )
            
        metrics = self.metrics_collector.collect_performance_metrics()
        
        # Verify performance metrics
        self.assertIn('response_times', metrics)
        self.assertIn('throughput', metrics)
        self.assertIn('error_rates', metrics)
        
        # Verify response time statistics
        response_times_stats = metrics['response_times']
        self.assertIn('average', response_times_stats)
        self.assertIn('median', response_times_stats)
        self.assertIn('p95', response_times_stats)
        self.assertIn('p99', response_times_stats)
        self.assertIn('min', response_times_stats)
        self.assertIn('max', response_times_stats)
        
        # Verify calculated values
        self.assertEqual(response_times_stats['average'], 325.0)  # (100+550)/2
        self.assertEqual(response_times_stats['min'], 100)
        self.assertEqual(response_times_stats['max'], 550)
        
    def test_collect_geographic_metrics(self):
        """Test geographic metrics collection"""
        # Create requests from different locations
        locations = [
            {'country': 'US', 'city': 'New York'},
            {'country': 'US', 'city': 'Los Angeles'},
            {'country': 'GB', 'city': 'London'},
            {'country': 'DE', 'city': 'Berlin'},
            {'country': 'JP', 'city': 'Tokyo'}
        ]
        
        for location in locations:
            for i in range(10):
                RateLimitLog.objects.create(
                    user=self.regular_user,
                    endpoint='/api/test/',
                    method='GET',
                    ip_address='192.168.1.100',
                    user_agent='Mozilla/5.0',
                    status_code=200,
                    is_allowed=True,
                    country=location['country'],
                    city=location['city']
                )
                
        metrics = self.metrics_collector.collect_geographic_metrics()
        
        # Verify geographic metrics
        self.assertIn('requests_by_country', metrics)
        self.assertIn('requests_by_city', metrics)
        self.assertIn('top_locations', metrics)
        
        # Verify country metrics
        country_metrics = metrics['requests_by_country']
        self.assertEqual(country_metrics['US'], 20)  # 2 cities * 10 requests
        self.assertEqual(country_metrics['GB'], 10)
        self.assertEqual(country_metrics['DE'], 10)
        self.assertEqual(country_metrics['JP'], 10)


class RateLimitMonitoringIntegrationTest(TransactionTestCase):
    """Integration tests for rate limit monitoring"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        self.monitoring_service = RateLimitMonitoringService()
        self.alert_manager = RateLimitAlertManager()
        self.metrics_collector = RateLimitMetricsCollector()
        
    def test_complete_monitoring_workflow(self):
        """Test complete monitoring workflow"""
        # Create rate limit violations
        for i in range(50):
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint='/api/monitoring_test/',
                method='GET',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0',
                status_code=429,
                is_allowed=False
            )
            
        # Collect metrics
        metrics = self.monitoring_service.collect_system_metrics()
        
        # Detect anomalies
        anomalies = self.monitoring_service.detect_anomalies()
        
        # Generate alerts
        alerts = self.monitoring_service.generate_alerts()
        
        # Create alert records
        created_alerts = []
        for alert_data in alerts:
            alert = self.alert_manager.create_alert(alert_data)
            created_alerts.append(alert)
            
        # Verify workflow completeness
        self.assertGreater(metrics['total_requests'], 50)
        self.assertGreater(len(anomalies), 0)
        self.assertGreater(len(alerts), 0)
        self.assertEqual(len(created_alerts), len(alerts))
        
        # Verify alert creation
        for alert in created_alerts:
            self.assertIsNotNone(alert.id)
            self.assertFalse(alert.is_resolved)
            
        # Resolve alerts
        for alert in created_alerts:
            self.alert_manager.resolve_alert(
                alert.id,
                resolved_by=self.admin_user,
                resolution_note='Test resolution'
            )
            
        # Verify resolution
        for alert in created_alerts:
            alert.refresh_from_db()
            self.assertTrue(alert.is_resolved)
            self.assertEqual(alert.resolved_by, self.admin_user)
            
    def test_real_time_monitoring_simulation(self):
        """Test real-time monitoring simulation"""
        import time
        
        # Simulate real-time monitoring
        monitoring_results = []
        
        for i in range(5):
            # Create new requests
            RateLimitLog.objects.create(
                user=self.regular_user,
                endpoint=f'/api/realtime_{i}/',
                method='GET',
                ip_address='192.168.1.100',
                user_agent='Mozilla/5.0',
                status_code=200,
                is_allowed=True
            )
            
            # Collect metrics
            metrics = self.monitoring_service.collect_real_time_metrics()
            monitoring_results.append(metrics)
            
            # Small delay to simulate real-time
            time.sleep(0)
            
        # Verify monitoring results
        self.assertEqual(len(monitoring_results), 5)
        
        # Verify metrics evolution
        for i, result in enumerate(monitoring_results):
            self.assertIn('current_time', result)
            self.assertIn('requests_per_second', result)
            self.assertGreater(result['requests_per_second'], 0)
            
    def test_monitoring_under_load(self):
        """Test monitoring performance under load"""
        import threading
# SQLite compatibility: limit concurrent threads
        import time
        
        # Create large dataset
        def create_requests(start_id, count):
            for i in range(count):
                RateLimitLog.objects.create(
                    user=self.regular_user,
                    endpoint=f'/api/load_test_{start_id + i}/',
                    method='GET',
                    ip_address='192.168.1.100',
                    user_agent='Mozilla/5.0',
                    status_code=429 if i % 10 == 0 else 200,
                    is_allowed=i % 10 != 0
                )
                
        # Create concurrent threads
        threads = []
        for i in range(4):  # 4 threads
            thread = threading.Thread(
                target=create_requests,
                args=(i * 250, 250)  # 250 requests per thread
            )
            threads.append(thread)
            thread.start()
            
        # Wait for completion
        for thread in threads:
            thread.join()
            
        # Test monitoring performance
        start_time = time.time()
        
        metrics = self.monitoring_service.collect_system_metrics()
        anomalies = self.monitoring_service.detect_anomalies()
        alerts = self.monitoring_service.generate_alerts()
        
        end_time = time.time()
        monitoring_time = end_time - start_time
        
        # Verify performance (< 2 seconds for 1000 requests)
        self.assertLess(monitoring_time, 2.0)
        
        # Verify results
        self.assertEqual(metrics['total_requests'], 1000)
        self.assertGreater(len(anomalies), 0)
        self.assertGreater(len(alerts), 0)

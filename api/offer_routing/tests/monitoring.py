"""
Monitoring Tests for Offer Routing System

This module contains unit tests for monitoring functionality,
including health checks, performance monitoring, and alerting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.monitoring import MonitoringService, monitoring_service
from ..exceptions import MonitoringError, ValidationError

User = get_user_model()


class MonitoringServiceTestCase(TestCase):
    """Test cases for MonitoringService."""
    
    def setUp(self):
        """Set up test data."""
        self.monitoring_service = MonitoringService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
    
    def test_check_system_health(self):
        """Test system health check."""
        health_status = self.monitoring_service.check_system_health()
        
        self.assertIsInstance(health_status, dict)
        self.assertIn('overall_status', health_status)
        self.assertIn('checks', health_status)
        self.assertIn('alerts', health_status)
        self.assertIn('timestamp', health_status)
        
        # Check individual health checks
        checks = health_status['checks']
        self.assertIn('database', checks)
        self.assertIn('cache', checks)
        self.assertIn('queue', checks)
        self.assertIn('memory', checks)
        self.assertIn('routing_performance', checks)
        self.assertIn('error_rate', checks)
        
        for check_name, check_result in checks.items():
            self.assertIsInstance(check_result, dict)
            self.assertIn('status', check_result)
            self.assertIn('message', check_result)
    
    def test_check_service_dependencies(self):
        """Test service dependency health check."""
        dependencies = self.monitoring_service.check_service_dependencies()
        
        self.assertIsInstance(dependencies, dict)
        self.assertIn('overall_status', dependencies)
        self.assertIn('dependencies', dependencies)
        self.assertIn('timestamp', dependencies)
        
        # Check individual dependencies
        deps = dependencies['dependencies']
        self.assertIn('database', deps)
        self.assertIn('cache', deps)
        self.assertIn('queue', deps)
        
        for dep_name, dep_result in deps.items():
            self.assertIsInstance(dep_result, dict)
            self.assertIn('status', dep_result)
            self.assertIn('message', dep_result)
            self.assertIn('response_time_ms', dep_result)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        metrics = self.monitoring_service.get_performance_metrics(minutes=60)
        
        self.assertIsInstance(metrics, list)
        
        for metric in metrics:
            self.assertIsInstance(metric, dict)
            self.assertIn('name', metric)
            self.assertIn('value', metric)
            self.assertIn('timestamp', metric)
            self.assertIn('unit', metric)
    
    def test_get_performance_summary(self):
        """Test getting performance summary."""
        summary = self.monitoring_service.get_performance_summary(minutes=60)
        
        self.assertIsInstance(summary, dict)
        self.assertIn('routing_response_time', summary)
        self.assertIn('cache_hit_rate', summary)
        self.assertIn('error_rate', summary)
        self.assertIn('throughput', summary)
        self.assertIn('cpu_usage', summary)
        self.assertIn('memory_usage', summary)
    
    def test_record_performance_metric(self):
        """Test recording performance metric."""
        metric_name = 'test_metric'
        value = 85.5
        tags = {'environment': 'test'}
        
        success = self.monitoring_service.record_performance_metric(
            metric_name, value, tags
        )
        
        self.assertTrue(success)
    
    def test_trigger_alert(self):
        """Test alert triggering."""
        alert_data = {
            'alert_type': 'performance',
            'severity': 'warning',
            'message': 'High response time detected',
            'metric_name': 'routing_response_time',
            'value': 150.0,
            'threshold': 100.0
        }
        
        success = self.monitoring_service.trigger_alert(alert_data)
        
        self.assertTrue(success)
    
    def test_check_database_health(self):
        """Test database health check."""
        health = self.monitoring_service._check_database_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('response_time_ms', health)
        self.assertIn('connection_pool', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_check_cache_health(self):
        """Test cache health check."""
        health = self.monitoring_service._check_cache_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('response_time_ms', health)
        self.assertIn('hit_rate', health)
        self.assertIn('memory_usage', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_check_queue_health(self):
        """Test queue health check."""
        health = self.monitoring_service._check_queue_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('active_tasks', health)
        self.assertIn('pending_tasks', health)
        self.assertIn('failed_tasks', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_check_memory_health(self):
        """Test memory health check."""
        health = self.monitoring_service._check_memory_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('memory_usage', health)
        self.assertIn('available_memory', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_check_routing_performance_health(self):
        """Test routing performance health check."""
        health = self.monitoring_service._check_routing_performance_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('avg_response_time', health)
        self.assertIn('p95_response_time', health)
        self.assertIn('p99_response_time', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_check_error_rate_health(self):
        """Test error rate health check."""
        health = self.monitoring_service._check_error_rate_health()
        
        self.assertIsInstance(health, dict)
        self.assertIn('status', health)
        self.assertIn('message', health)
        self.assertIn('error_rate', health)
        self.assertIn('total_requests', health)
        self.assertIn('error_count', health)
        
        # Status should be one of: healthy, degraded, unhealthy
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'])
    
    def test_get_resource_usage(self):
        """Test getting resource usage."""
        usage = self.monitoring_service._get_resource_usage()
        
        self.assertIsInstance(usage, dict)
        self.assertIn('cpu_usage', usage)
        self.assertIn('memory_usage', usage)
        self.assertIn('disk_usage', usage)
        self.assertIn('network_io', usage)
        self.assertIn('active_connections', usage)
        
        # Values should be numeric
        for key, value in usage.items():
            if key != 'active_connections':
                self.assertIsInstance(value, (int, float))
            else:
                self.assertIsInstance(value, int)
    
    def test_calculate_health_score(self):
        """Test health score calculation."""
        checks = {
            'database': {'status': 'healthy'},
            'cache': {'status': 'healthy'},
            'queue': {'status': 'degraded'},
            'memory': {'status': 'healthy'},
            'routing_performance': {'status': 'healthy'},
            'error_rate': {'status': 'healthy'}
        }
        
        score = self.monitoring_service._calculate_health_score(checks)
        
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # With one degraded check, score should be less than 100
        self.assertLess(score, 100)
    
    def test_determine_overall_health(self):
        """Test overall health determination."""
        # Test with all healthy
        checks = {
            'database': {'status': 'healthy'},
            'cache': {'status': 'healthy'},
            'queue': {'status': 'healthy'},
            'memory': {'status': 'healthy'},
            'routing_performance': {'status': 'healthy'},
            'error_rate': {'status': 'healthy'}
        }
        
        overall = self.monitoring_service._determine_overall_health(checks)
        self.assertEqual(overall, 'healthy')
        
        # Test with one unhealthy
        checks['database']['status'] = 'unhealthy'
        overall = self.monitoring_service._determine_overall_health(checks)
        self.assertEqual(overall, 'unhealthy')
        
        # Test with one degraded
        checks['database']['status'] = 'degraded'
        overall = self.monitoring_service._determine_overall_health(checks)
        self.assertEqual(overall, 'degraded')
    
    def test_generate_health_alerts(self):
        """Test health alert generation."""
        checks = {
            'database': {'status': 'healthy', 'message': 'Database OK'},
            'cache': {'status': 'degraded', 'message': 'Cache hit rate low'},
            'queue': {'status': 'healthy', 'message': 'Queue OK'},
            'memory': {'status': 'unhealthy', 'message': 'Memory usage high'},
            'routing_performance': {'status': 'healthy', 'message': 'Performance OK'},
            'error_rate': {'status': 'healthy', 'message': 'Error rate OK'}
        }
        
        alerts = self.monitoring_service._generate_health_alerts(checks)
        
        self.assertIsInstance(alerts, list)
        
        # Should have alerts for degraded and unhealthy checks
        self.assertGreaterEqual(len(alerts), 2)
        
        for alert in alerts:
            self.assertIsInstance(alert, dict)
            self.assertIn('type', alert)
            self.assertIn('severity', alert)
            self.assertIn('message', alert)
            self.assertIn('timestamp', alert)
    
    def test_get_connection_pool_status(self):
        """Test getting connection pool status."""
        status = self.monitoring_service._get_connection_pool_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('active', status)
        self.assertIn('idle', status)
        self.assertIn('total', status)
        self.assertIn('max_connections', status)
        
        # Values should be numeric
        for key, value in status.items():
            self.assertIsInstance(value, int)
    
    def test_get_cache_statistics(self):
        """Test getting cache statistics."""
        stats = self.monitoring_service._get_cache_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('hit_rate', stats)
        self.assertIn('miss_rate', stats)
        self.assertIn('memory_usage', stats)
        self.assertIn('key_count', stats)
        self.assertIn('evictions', stats)
        
        # Values should be numeric
        for key, value in stats.items():
            self.assertIsInstance(value, (int, float))
    
    def test_get_queue_statistics(self):
        """Test getting queue statistics."""
        stats = self.monitoring_service._get_queue_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('active_tasks', stats)
        self.assertIn('pending_tasks', stats)
        self.assertIn('failed_tasks', stats)
        self.assertIn('worker_status', stats)
        
        # Values should be numeric for counts
        self.assertIsInstance(stats['active_tasks'], int)
        self.assertIsInstance(stats['pending_tasks'], int)
        self.assertIsInstance(stats['failed_tasks'], int)
        
        # Worker status should be a list
        self.assertIsInstance(stats['worker_status'], list)
    
    def test_validate_monitoring_configuration(self):
        """Test monitoring configuration validation."""
        valid_config = {
            'health_check_interval': 300,
            'performance_metrics_interval': 60,
            'alert_thresholds': {
                'response_time': 1000,
                'error_rate': 5.0,
                'memory_usage': 80.0
            },
            'notification_channels': ['email', 'slack']
        }
        
        is_valid, errors = self.monitoring_service._validate_monitoring_configuration(valid_config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid configuration
        invalid_config = {
            'health_check_interval': -1,
            'performance_metrics_interval': 0,
            'alert_thresholds': {
                'response_time': -1000,
                'error_rate': 150.0,
                'memory_usage': 150.0
            },
            'notification_channels': []
        }
        
        is_valid, errors = self.monitoring_service._validate_monitoring_configuration(invalid_config)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class MonitoringIntegrationTestCase(TestCase):
    """Integration tests for monitoring functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        # Check system health
        health_status = monitoring_service.check_system_health()
        
        self.assertIsInstance(health_status, dict)
        self.assertIn('overall_status', health_status)
        
        # Check service dependencies
        dependencies = monitoring_service.check_service_dependencies()
        
        self.assertIsInstance(dependencies, dict)
        self.assertIn('overall_status', dependencies)
        
        # Get performance metrics
        metrics = monitoring_service.get_performance_metrics(minutes=60)
        
        self.assertIsInstance(metrics, list)
        
        # Get performance summary
        summary = monitoring_service.get_performance_summary(minutes=60)
        
        self.assertIsInstance(summary, dict)
        
        # Record test metric
        success = monitoring_service.record_performance_metric(
            'test_metric', 85.5, {'environment': 'test'}
        )
        
        self.assertTrue(success)
        
        # Trigger test alert
        alert_data = {
            'alert_type': 'test',
            'severity': 'info',
            'message': 'Test alert',
            'metric_name': 'test_metric',
            'value': 85.5
        }
        
        success = monitoring_service.trigger_alert(alert_data)
        self.assertTrue(success)
    
    def test_health_check_integration(self):
        """Test health check integration."""
        health_status = monitoring_service.check_system_health()
        
        # Check if all expected checks are present
        expected_checks = [
            'database', 'cache', 'queue', 'memory',
            'routing_performance', 'error_rate'
        ]
        
        for check in expected_checks:
            self.assertIn(check, health_status['checks'])
        
        # Check if overall status is determined correctly
        overall_status = health_status['overall_status']
        self.assertIn(overall_status, ['healthy', 'degraded', 'unhealthy'])
        
        # Check if alerts are generated for issues
        alerts = health_status['alerts']
        self.assertIsInstance(alerts, list)
        
        for alert in alerts:
            self.assertIsInstance(alert, dict)
            self.assertIn('type', alert)
            self.assertIn('severity', alert)
            self.assertIn('message', alert)
    
    def test_performance_monitoring_integration(self):
        """Test performance monitoring integration."""
        # Record multiple metrics
        for i in range(10):
            monitoring_service.record_performance_metric(
                'routing_response_time',
                45.0 + (i * 5),
                {'environment': 'test', 'route': f'route_{i}'}
            )
            
            monitoring_service.record_performance_metric(
                'cache_hit_rate',
                85.0 + (i * 1.5),
                {'environment': 'test', 'cache_type': 'redis'}
            )
        
        # Get performance metrics
        metrics = monitoring_service.get_performance_metrics(minutes=60)
        
        self.assertGreater(len(metrics), 0)
        
        # Get performance summary
        summary = monitoring_service.get_performance_summary(minutes=60)
        
        self.assertIsInstance(summary, dict)
        self.assertIn('routing_response_time', summary)
        self.assertIn('cache_hit_rate', summary)
    
    def test_alert_integration(self):
        """Test alert integration."""
        # Trigger different types of alerts
        alerts = [
            {
                'alert_type': 'performance',
                'severity': 'warning',
                'message': 'High response time',
                'metric_name': 'routing_response_time',
                'value': 150.0,
                'threshold': 100.0
            },
            {
                'alert_type': 'resource',
                'severity': 'critical',
                'message': 'High memory usage',
                'metric_name': 'memory_usage',
                'value': 85.0,
                'threshold': 80.0
            },
            {
                'alert_type': 'error_rate',
                'severity': 'warning',
                'message': 'High error rate',
                'metric_name': 'error_rate',
                'value': 6.0,
                'threshold': 5.0
            }
        ]
        
        for alert_data in alerts:
            success = monitoring_service.trigger_alert(alert_data)
            self.assertTrue(success)
    
    def test_monitoring_performance(self):
        """Test monitoring performance."""
        import time
        
        # Measure health check time
        start_time = time.time()
        
        health_status = monitoring_service.check_system_health()
        
        end_time = time.time()
        health_check_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(health_check_time, 1000)  # Within 1 second
        
        # Measure performance metrics time
        start_time = time.time()
        
        metrics = monitoring_service.get_performance_metrics(minutes=60)
        
        end_time = time.time()
        metrics_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(metrics_time, 500)  # Within 500ms
    
    def test_monitoring_error_handling(self):
        """Test error handling in monitoring."""
        # Test with invalid metric name
        with self.assertRaises(Exception):
            monitoring_service.record_performance_metric(
                '', 85.5, {}
            )
        
        # Test with invalid alert data
        with self.assertRaises(Exception):
            monitoring_service.trigger_alert({})
        
        # Test with invalid time range
        with self.assertRaises(Exception):
            monitoring_service.get_performance_metrics(minutes=-1)
    
    def test_monitoring_configuration(self):
        """Test monitoring configuration."""
        # Test valid configuration
        config = {
            'health_check_interval': 300,
            'performance_metrics_interval': 60,
            'alert_thresholds': {
                'response_time': 1000,
                'error_rate': 5.0,
                'memory_usage': 80.0
            }
        }
        
        is_valid, errors = monitoring_service._validate_monitoring_configuration(config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test invalid configuration
        invalid_config = {
            'health_check_interval': -1,
            'performance_metrics_interval': 0,
            'alert_thresholds': {
                'response_time': -1000,
                'error_rate': 150.0,
                'memory_usage': 150.0
            }
        }
        
        is_valid, errors = monitoring_service._validate_monitoring_configuration(invalid_config)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
        # Check if expected errors are present
        error_messages = [error['message'] for error in errors]
        self.assertIn('health_check_interval must be positive', error_messages)
        self.assertIn('performance_metrics_interval must be positive', error_messages)
        self.assertIn('response_time threshold must be positive', error_messages)
        self.assertIn('error_rate threshold must be between 0 and 100', error_messages)
        self.assertIn('memory_usage threshold must be between 0 and 100', error_messages)

"""
Comprehensive monitoring service testing for fraud_detection module.

This test file covers all monitoring functionality and system health checks
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.core.management import call_command
import time
import psutil
import threading
from datetime import datetime, timedelta

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.monitoring import (
    FraudMonitoringService, SystemHealthMonitor, PerformanceMonitor,
    AlertMonitor, MetricsCollector, AnomalyDetector, HealthChecker
)
from api.fraud_detection.views import FraudMonitoringAPIView
from api.users.models import User

User = get_user_model()


class BaseMonitoringTest(TestCase):
    """Base test class for monitoring testing"""
    
    def setUp(self):
        """Set up common test data"""
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
        
        # Create test fraud data
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
        
        self.fraud_attempt = FraudAttempt.objects.create(
            user=self.regular_user,
            attempt_type='multi_account',
            description='Test fraud attempt',
            detected_by='TestDetector',
            fraud_score=85,
            status='detected'
        )
        
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class FraudMonitoringServiceTest(BaseMonitoringTest):
    """Test cases for FraudMonitoringService"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.monitoring_service = FraudMonitoringService()
    
    def test_get_system_status(self):
        """Test getting overall system status"""
        with patch('api.fraud_detection.monitoring.HealthChecker') as mock_health:
            mock_health.return_value.check_system_health.return_value = {
                'overall_status': 'healthy',
                'components': {
                    'database': 'healthy',
                    'redis': 'healthy',
                    'analysis_engine': 'healthy'
                },
                'timestamp': timezone.now().isoformat()
            }
            
            status = self.monitoring_service.get_system_status()
            
            self.assertEqual(status['overall_status'], 'healthy')
            self.assertIn('components', status)
            self.assertIn('timestamp', status)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        with patch('api.fraud_detection.monitoring.MetricsCollector') as mock_metrics:
            mock_metrics.return_value.collect_metrics.return_value = {
                'processing_time': {
                    'average': 2.3,
                    'p95': 5.1,
                    'p99': 8.7
                },
                'throughput': {
                    'requests_per_second': 125.5,
                    'analyses_per_hour': 4500
                },
                'error_rate': 0.02,
                'memory_usage': {
                    'current': 45.2,
                    'peak': 67.8
                }
            }
            
            metrics = self.monitoring_service.get_performance_metrics()
            
            self.assertIn('processing_time', metrics)
            self.assertIn('throughput', metrics)
            self.assertIn('error_rate', metrics)
            self.assertIn('memory_usage', metrics)
    
    def test_get_fraud_statistics(self):
        """Test getting fraud detection statistics"""
        # Create more test data
        for i in range(10):
            FraudAttempt.objects.create(
                user=self.regular_user,
                attempt_type='vpn_proxy' if i % 2 == 0 else 'click_fraud',
                description=f'Test attempt {i}',
                detected_by='TestDetector',
                fraud_score=70 + i * 3,
                status='detected' if i < 7 else 'confirmed'
            )
        
        stats = self.monitoring_service.get_fraud_statistics()
        
        self.assertIn('total_attempts', stats)
        self.assertIn('attempts_by_type', stats)
        self.assertIn('attempts_by_status', stats)
        self.assertIn('average_fraud_score', stats)
        self.assertIn('high_risk_count', stats)
        
        # Verify counts
        self.assertEqual(stats['total_attempts'], 11)  # 10 new + 1 existing
        self.assertGreater(stats['average_fraud_score'], 0)
    
    def test_get_alert_summary(self):
        """Test getting alert summary"""
        # Create test alerts
        for i in range(5):
            FraudAlert.objects.create(
                alert_type='rule_triggered' if i < 3 else 'pattern_detected',
                priority='high' if i < 2 else 'medium',
                title=f'Test Alert {i}',
                description='Test alert description',
                is_resolved=i < 2
            )
        
        alert_summary = self.monitoring_service.get_alert_summary()
        
        self.assertIn('total_alerts', alert_summary)
        self.assertIn('unresolved_alerts', alert_summary)
        self.assertIn('alerts_by_priority', alert_summary)
        self.assertIn('alerts_by_type', alert_summary)
        
        self.assertEqual(alert_summary['total_alerts'], 5)
        self.assertEqual(alert_summary['unresolved_alerts'], 3)
    
    def test_monitor_fraud_detection_performance(self):
        """Test monitoring fraud detection performance"""
        with patch('api.fraud_detection.monitoring.PerformanceMonitor') as mock_perf:
            mock_perf.return_value.monitor_detection_performance.return_value = {
                'detection_accuracy': 0.94,
                'false_positive_rate': 0.06,
                'average_detection_time': 1.8,
                'rule_performance': {
                    'Test Rule': {
                        'trigger_count': 25,
                        'accuracy': 0.92,
                        'avg_processing_time': 0.8
                    }
                }
            }
            
            perf_data = self.monitoring_service.monitor_fraud_detection_performance()
            
            self.assertIn('detection_accuracy', perf_data)
            self.assertIn('false_positive_rate', perf_data)
            self.assertIn('average_detection_time', perf_data)
            self.assertIn('rule_performance', perf_data)
    
    def test_detect_anomalies(self):
        """Test anomaly detection"""
        with patch('api.fraud_detection.monitoring.AnomalyDetector') as mock_detector:
            mock_detector.return_value.detect_anomalies.return_value = {
                'anomalies_detected': True,
                'anomaly_types': ['spike_in_attempts', 'unusual_pattern'],
                'anomaly_details': [
                    {
                        'type': 'spike_in_attempts',
                        'severity': 'high',
                        'description': 'Unusual spike in fraud attempts',
                        'affected_timeframe': '2023-01-15 14:00-15:00',
                        'metric_value': 150,
                        'baseline_value': 25,
                        'deviation': 5.0
                    }
                ],
                'recommendations': ['investigate_source', 'enhance_monitoring']
            }
            
            anomalies = self.monitoring_service.detect_anomalies()
            
            self.assertTrue(anomalies['anomalies_detected'])
            self.assertIn('anomaly_types', anomalies)
            self.assertIn('anomaly_details', anomalies)
            self.assertIn('recommendations', anomalies)
    
    def test_generate_health_report(self):
        """Test generating comprehensive health report"""
        with patch.multiple(
            'api.fraud_detection.monitoring',
            HealthChecker=MagicMock(),
            MetricsCollector=MagicMock(),
            AnomalyDetector=MagicMock()
        ):
            # Mock health checker
            mock_health = MagicMock()
            mock_health.check_system_health.return_value = {
                'overall_status': 'healthy',
                'components': {'database': 'healthy', 'redis': 'healthy'}
            }
            
            # Mock metrics collector
            mock_metrics = MagicMock()
            mock_metrics.collect_metrics.return_value = {
                'processing_time': {'average': 2.3},
                'throughput': {'requests_per_second': 125.5},
                'error_rate': 0.02
            }
            
            # Mock anomaly detector
            mock_anomaly = MagicMock()
            mock_anomaly.detect_anomalies.return_value = {
                'anomalies_detected': False,
                'anomaly_types': []
            }
            
            report = self.monitoring_service.generate_health_report()
            
            self.assertIn('system_health', report)
            self.assertIn('performance_metrics', report)
            self.assertIn('fraud_statistics', report)
            self.assertIn('anomaly_detection', report)
            self.assertIn('recommendations', report)
            self.assertIn('generated_at', report)


class SystemHealthMonitorTest(BaseMonitoringTest):
    """Test cases for SystemHealthMonitor"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.health_monitor = SystemHealthMonitor()
    
    def test_check_database_health(self):
        """Test database health check"""
        with patch('django.db.connection') as mock_connection:
            mock_connection.cursor.return_value.__enter__.return_value.execute.return_value = None
            
            health = self.health_monitor.check_database_health()
            
            self.assertIn('status', health)
            self.assertIn('response_time', health)
            self.assertIn('connection_pool', health)
            self.assertIn('last_check', health)
            
            # Should be healthy in test environment
            self.assertEqual(health['status'], 'healthy')
    
    def test_check_redis_health(self):
        """Test Redis health check"""
        with patch('django.core.cache.cache') as mock_cache:
            mock_cache.set.return_value = True
            mock_cache.get.return_value = 'test_value'
            
            health = self.health_monitor.check_redis_health()
            
            self.assertIn('status', health)
            self.assertIn('response_time', health)
            self.assertIn('memory_usage', health)
            self.assertIn('connected_clients', health)
            
            self.assertEqual(health['status'], 'healthy')
    
    def test_check_analysis_engine_health(self):
        """Test analysis engine health check"""
        with patch('api.fraud_detection.services.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.health_check.return_value = {
                'status': 'healthy',
                'active_detectors': 5,
                'queue_size': 12,
                'processing_time': 1.2
            }
            
            health = self.health_monitor.check_analysis_engine_health()
            
            self.assertEqual(health['status'], 'healthy')
            self.assertIn('active_detectors', health)
            self.assertIn('queue_size', health)
            self.assertIn('processing_time', health)
    
    def test_check_disk_space_health(self):
        """Test disk space health check"""
        with patch('psutil.disk_usage') as mock_disk:
            mock_disk.return_value = MagicMock()
            mock_disk.return_value.total = 1000000000  # 1GB
            mock_disk.return_value.used = 500000000   # 500MB
            mock_disk.return_value.free = 500000000   # 500MB
            mock_disk.return_value.percent = 50.0
            
            health = self.health_monitor.check_disk_space_health('/tmp')
            
            self.assertIn('status', health)
            self.assertIn('total_space', health)
            self.assertIn('used_space', health)
            self.assertIn('free_space', health)
            self.assertIn('usage_percentage', health)
            
            # Should be healthy with 50% usage
            self.assertEqual(health['status'], 'healthy')
    
    def test_check_memory_health(self):
        """Test memory health check"""
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = MagicMock()
            mock_memory.return_value.total = 8000000000   # 8GB
            mock_memory.return_value.used = 4000000000    # 4GB
            mock_memory.return_value.available = 4000000000  # 4GB
            mock_memory.return_value.percent = 50.0
            
            health = self.health_monitor.check_memory_health()
            
            self.assertIn('status', health)
            self.assertIn('total_memory', health)
            self.assertIn('used_memory', health)
            self.assertIn('available_memory', health)
            self.assertIn('usage_percentage', health)
            
            self.assertEqual(health['status'], 'healthy')
    
    def test_check_cpu_health(self):
        """Test CPU health check"""
        with patch('psutil.cpu_percent') as mock_cpu:
            mock_cpu.return_value = 25.5  # 25.5% CPU usage
            
            health = self.health_monitor.check_cpu_health()
            
            self.assertIn('status', health)
            self.assertIn('cpu_usage', health)
            self.assertIn('cpu_count', health)
            self.assertIn('load_average', health)
            
            self.assertEqual(health['cpu_usage'], 25.5)
    
    def test_get_overall_health_status(self):
        """Test overall health status aggregation"""
        with patch.multiple(
            self.health_monitor,
            check_database_health=MagicMock(return_value={'status': 'healthy'}),
            check_redis_health=MagicMock(return_value={'status': 'healthy'}),
            check_analysis_engine_health=MagicMock(return_value={'status': 'healthy'}),
            check_disk_space_health=MagicMock(return_value={'status': 'healthy'}),
            check_memory_health=MagicMock(return_value={'status': 'healthy'}),
            check_cpu_health=MagicMock(return_value={'status': 'healthy'})
        ):
            overall_health = self.health_monitor.get_overall_health_status()
            
            self.assertEqual(overall_health['overall_status'], 'healthy')
            self.assertIn('components', overall_health)
            self.assertIn('timestamp', overall_health)
            self.assertEqual(len(overall_health['components']), 6)
    
    def test_health_status_with_degraded_component(self):
        """Test health status with degraded component"""
        with patch.multiple(
            self.health_monitor,
            check_database_health=MagicMock(return_value={'status': 'healthy'}),
            check_redis_health=MagicMock(return_value={'status': 'degraded', 'error': 'High latency'}),
            check_analysis_engine_health=MagicMock(return_value={'status': 'healthy'}),
            check_disk_space_health=MagicMock(return_value={'status': 'healthy'}),
            check_memory_health=MagicMock(return_value={'status': 'healthy'}),
            check_cpu_health=MagicMock(return_value={'status': 'healthy'})
        ):
            overall_health = self.health_monitor.get_overall_health_status()
            
            self.assertEqual(overall_health['overall_status'], 'degraded')
            self.assertEqual(overall_health['components']['redis']['status'], 'degraded')


class PerformanceMonitorTest(BaseMonitoringTest):
    """Test cases for PerformanceMonitor"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.performance_monitor = PerformanceMonitor()
    
    def test_measure_processing_time(self):
        """Test processing time measurement"""
        def mock_processing_function():
            time.sleep(0.1)  # Simulate 100ms processing
        
        processing_time = self.performance_monitor.measure_processing_time(
            mock_processing_function
        )
        
        self.assertIsInstance(processing_time, float)
        self.assertGreater(processing_time, 0.09)  # Should be around 100ms
        self.assertLess(processing_time, 0.2)     # But not too much higher
    
    def test_collect_throughput_metrics(self):
        """Test throughput metrics collection"""
        with patch('api.fraud_detection.monitoring.cache') as mock_cache:
            # Mock cache data for throughput calculation
            mock_cache.get.return_value = 100  # Previous count
            mock_cache.set.return_value = True
            
            throughput = self.performance_monitor.collect_throughput_metrics()
            
            self.assertIn('requests_per_second', throughput)
            self.assertIn('analyses_per_hour', throughput)
            self.assertIn('alerts_per_day', throughput)
    
    def test_collect_error_metrics(self):
        """Test error metrics collection"""
        with patch('api.fraud_detection.monitoring.cache') as mock_cache:
            # Mock error counts
            mock_cache.get.return_value = 5
            mock_cache.set.return_value = True
            
            error_metrics = self.performance_monitor.collect_error_metrics()
            
            self.assertIn('error_rate', error_metrics)
            self.assertIn('error_count', error_metrics)
            self.assertIn('error_types', error_metrics)
    
    def test_collect_resource_usage_metrics(self):
        """Test resource usage metrics collection"""
        with patch.multiple(
            'psutil',
            virtual_memory=MagicMock(return_value=MagicMock(percent=45.2, used=4000000000)),
            cpu_percent=MagicMock(return_value=25.5),
            disk_usage=MagicMock(return_value=MagicMock(percent=60.0, used=500000000))
        ):
            resource_metrics = self.performance_monitor.collect_resource_usage_metrics()
            
            self.assertIn('memory_usage', resource_metrics)
            self.assertIn('cpu_usage', resource_metrics)
            self.assertIn('disk_usage', resource_metrics)
            
            self.assertEqual(resource_metrics['memory_usage']['percentage'], 45.2)
            self.assertEqual(resource_metrics['cpu_usage']['percentage'], 25.5)
            self.assertEqual(resource_metrics['disk_usage']['percentage'], 60.0)
    
    def test_monitor_rule_performance(self):
        """Test individual rule performance monitoring"""
        with patch('api.fraud_detection.monitoring.FraudRule.objects') as mock_rule_objects:
            mock_rule = MagicMock()
            mock_rule.name = 'Test Rule'
            mock_rule.trigger_count = 50
            mock_rule.average_processing_time = 0.8
            mock_rule.accuracy = 0.92
            mock_rule_objects.get.return_value = mock_rule
            
            rule_performance = self.performance_monitor.monitor_rule_performance(
                self.fraud_rule.pk
            )
            
            self.assertIn('rule_name', rule_performance)
            self.assertIn('trigger_count', rule_performance)
            self.assertIn('average_processing_time', rule_performance)
            self.assertIn('accuracy', rule_performance)
            self.assertIn('efficiency_score', rule_performance)


class AlertMonitorTest(BaseMonitoringTest):
    """Test cases for AlertMonitor"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.alert_monitor = AlertMonitor()
    
    def test_monitor_alert_levels(self):
        """Test alert level monitoring"""
        # Create alerts with different priorities
        FraudAlert.objects.create(
            alert_type='rule_triggered',
            priority='critical',
            title='Critical Alert',
            description='Critical fraud alert',
            is_resolved=False
        )
        
        FraudAlert.objects.create(
            alert_type='pattern_detected',
            priority='high',
            title='High Priority Alert',
            description='High priority fraud alert',
            is_resolved=False
        )
        
        FraudAlert.objects.create(
            alert_type='threshold_exceeded',
            priority='medium',
            title='Medium Alert',
            description='Medium priority alert',
            is_resolved=False
        )
        
        alert_levels = self.alert_monitor.monitor_alert_levels()
        
        self.assertIn('critical', alert_levels)
        self.assertIn('high', alert_levels)
        self.assertIn('medium', alert_levels)
        self.assertIn('low', alert_levels)
        
        self.assertEqual(alert_levels['critical'], 1)
        self.assertEqual(alert_levels['high'], 1)
        self.assertEqual(alert_levels['medium'], 1)
    
    def test_monitor_alert_resolution_time(self):
        """Test alert resolution time monitoring"""
        # Create resolved alert with known resolution time
        resolved_alert = FraudAlert.objects.create(
            alert_type='rule_triggered',
            priority='high',
            title='Resolved Alert',
            description='Alert that was resolved',
            is_resolved=True,
            resolved_at=timezone.now(),
            created_at=timezone.now() - timedelta(hours=2)
        )
        
        resolution_metrics = self.alert_monitor.monitor_alert_resolution_time()
        
        self.assertIn('average_resolution_time', resolution_metrics)
        self.assertIn('median_resolution_time', resolution_metrics)
        self.assertIn('resolution_by_priority', resolution_metrics)
        
        # Should have at least one resolved alert
        self.assertGreater(resolution_metrics['average_resolution_time'], 0)
    
    def test_monitor_alert_trends(self):
        """Test alert trend monitoring"""
        # Create alerts over time
        base_time = timezone.now() - timedelta(days=7)
        
        for i in range(7):
            alert_date = base_time + timedelta(days=i)
            FraudAlert.objects.create(
                alert_type='rule_triggered',
                priority='high',
                title=f'Alert Day {i}',
                description='Test alert',
                created_at=alert_date
            )
        
        alert_trends = self.alert_monitor.monitor_alert_trends(days=7)
        
        self.assertIn('daily_counts', alert_trends)
        self.assertIn('trend_direction', alert_trends)
        self.assertIn('weekly_average', alert_trends)
        self.assertIn('peak_day', alert_trends)
        
        self.assertEqual(len(alert_trends['daily_counts']), 7)
    
    def test_check_alert_thresholds(self):
        """Test alert threshold checking"""
        # Create many alerts to trigger threshold
        for i in range(15):  # Above default threshold of 10
            FraudAlert.objects.create(
                alert_type='rule_triggered',
                priority='high',
                title=f'Threshold Alert {i}',
                description='Alert for threshold testing',
                is_resolved=False
            )
        
        threshold_check = self.alert_monitor.check_alert_thresholds()
        
        self.assertIn('thresholds_exceeded', threshold_check)
        self.assertIn('total_unresolved', threshold_check)
        self.assertIn('recommendations', threshold_check)
        
        # Should detect threshold exceeded
        self.assertTrue(threshold_check['thresholds_exceeded'])
        self.assertGreater(threshold_check['total_unresolved'], 10)


class MetricsCollectorTest(BaseMonitoringTest):
    """Test cases for MetricsCollector"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.metrics_collector = MetricsCollector()
    
    def test_collect_fraud_detection_metrics(self):
        """Test fraud detection metrics collection"""
        metrics = self.metrics_collector.collect_fraud_detection_metrics()
        
        self.assertIn('total_attempts', metrics)
        self.assertIn('detection_rate', metrics)
        self.assertIn('false_positive_rate', metrics)
        self.assertIn('average_confidence', metrics)
        self.assertIn('rule_effectiveness', metrics)
    
    def test_collect_user_behavior_metrics(self):
        """Test user behavior metrics collection"""
        # Create user risk profiles
        UserRiskProfile.objects.create(
            user=self.regular_user,
            overall_risk_score=75,
            risk_factors={'multiple_accounts': True},
            is_flagged=True
        )
        
        behavior_metrics = self.metrics_collector.collect_user_behavior_metrics()
        
        self.assertIn('total_flagged_users', behavior_metrics)
        self.assertIn('average_risk_score', behavior_metrics)
        self.assertIn('risk_distribution', behavior_metrics)
        self.assertIn('common_risk_factors', behavior_metrics)
    
    def test_collect_system_performance_metrics(self):
        """Test system performance metrics collection"""
        with patch.multiple(
            'psutil',
            virtual_memory=MagicMock(return_value=MagicMock(percent=45.2)),
            cpu_percent=MagicMock(return_value=25.5),
            disk_usage=MagicMock(return_value=MagicMock(percent=60.0))
        ):
            performance_metrics = self.metrics_collector.collect_system_performance_metrics()
            
            self.assertIn('cpu_usage', performance_metrics)
            self.assertIn('memory_usage', performance_metrics)
            self.assertIn('disk_usage', performance_metrics)
            self.assertIn('network_io', performance_metrics)
    
    def test_collect_business_metrics(self):
        """Test business metrics collection"""
        business_metrics = self.metrics_collector.collect_business_metrics()
        
        self.assertIn('fraud_prevention_savings', business_metrics)
        self.assertIn('detection_coverage', business_metrics)
        self.assertIn('operational_efficiency', business_metrics)
        self.assertIn('compliance_metrics', business_metrics)
    
    def test_export_metrics(self):
        """Test metrics export functionality"""
        with patch.object(self.metrics_collector, 'collect_fraud_detection_metrics') as mock_collect:
            mock_collect.return_value = {
                'total_attempts': 100,
                'detection_rate': 0.85,
                'false_positive_rate': 0.05
            }
            
            # Test JSON export
            json_export = self.metrics_collector.export_metrics('json')
            self.assertIsInstance(json_export, str)
            
            # Test CSV export
            csv_export = self.metrics_collector.export_metrics('csv')
            self.assertIsInstance(csv_export, str)
            self.assertIn('total_attempts', csv_export)


class AnomalyDetectorTest(BaseMonitoringTest):
    """Test cases for AnomalyDetector"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.anomaly_detector = AnomalyDetector()
    
    def test_detect_volume_anomalies(self):
        """Test volume anomaly detection"""
        # Mock time series data with anomaly
        time_series_data = [
            {'timestamp': '2023-01-01 10:00', 'value': 10},
            {'timestamp': '2023-01-01 11:00', 'value': 12},
            {'timestamp': '2023-01-01 12:00', 'value': 11},
            {'timestamp': '2023-01-01 13:00', 'value': 150},  # Anomaly
            {'timestamp': '2023-01-01 14:00', 'value': 13},
            {'timestamp': '2023-01-01 15:00', 'value': 10},
        ]
        
        anomalies = self.anomaly_detector.detect_volume_anomalies(time_series_data)
        
        self.assertIsInstance(anomalies, list)
        if anomalies:  # If anomalies detected
            anomaly = anomalies[0]
            self.assertIn('timestamp', anomaly)
            self.assertIn('value', anomaly)
            self.assertIn('severity', anomaly)
            self.assertIn('deviation_score', anomaly)
    
    def test_detect_pattern_anomalies(self):
        """Test pattern anomaly detection"""
        # Mock pattern data
        pattern_data = {
            'login_times': ['09:00', '09:15', '14:30', '02:00', '09:30'],  # 02:00 is unusual
            'device_switching': [1, 0, 0, 5, 1],  # 5 is unusual
            'location_changes': [0, 1, 0, 3, 0]  # 3 is unusual
        }
        
        anomalies = self.anomaly_detector.detect_pattern_anomalies(pattern_data)
        
        self.assertIsInstance(anomalies, list)
        for anomaly in anomalies:
            self.assertIn('pattern_type', anomaly)
            self.assertIn('anomaly_value', anomaly)
            self.assertIn('expected_range', anomaly)
            self.assertIn('confidence', anomaly)
    
    def test_detect_performance_anomalies(self):
        """Test performance anomaly detection"""
        performance_data = {
            'processing_times': [1.2, 1.1, 1.3, 8.5, 1.4],  # 8.5 is anomaly
            'error_rates': [0.01, 0.02, 0.01, 0.15, 0.02],  # 0.15 is anomaly
            'response_times': [200, 180, 220, 1500, 190]  # 1500 is anomaly
        }
        
        anomalies = self.anomaly_detector.detect_performance_anomalies(performance_data)
        
        self.assertIsInstance(anomalies, list)
        for anomaly in anomalies:
            self.assertIn('metric_type', anomaly)
            self.assertIn('current_value', anomaly)
            self.assertIn('baseline_value', anomaly)
            self.assertIn('impact_assessment', anomaly)
    
    def test_calculate_anomaly_score(self):
        """Test anomaly score calculation"""
        test_values = [10, 12, 11, 13, 12, 150, 11, 10]  # 150 is clear anomaly
        
        anomaly_score = self.anomaly_detector.calculate_anomaly_score(test_values)
        
        self.assertIsInstance(anomaly_score, float)
        self.assertGreaterEqual(anomaly_score, 0.0)
        self.assertLessEqual(anomaly_score, 1.0)
        
        # Should detect high anomaly score due to outlier
        self.assertGreater(anomaly_score, 0.5)
    
    def test_get_anomaly_summary(self):
        """Test anomaly summary generation"""
        with patch.multiple(
            self.anomaly_detector,
            detect_volume_anomalies=MagicMock(return_value=[
                {'timestamp': '2023-01-01 13:00', 'severity': 'high'}
            ]),
            detect_pattern_anomalies=MagicMock(return_value=[
                {'pattern_type': 'login_time', 'severity': 'medium'}
            ]),
            detect_performance_anomalies=MagicMock(return_value=[
                {'metric_type': 'processing_time', 'severity': 'low'}
            ])
        ):
            summary = self.anomaly_detector.get_anomaly_summary()
            
            self.assertIn('total_anomalies', summary)
            self.assertIn('severity_distribution', summary)
            self.assertIn('anomaly_types', summary)
            self.assertIn('recommendations', summary)
            
            self.assertEqual(summary['total_anomalies'], 3)
            self.assertEqual(summary['severity_distribution']['high'], 1)
            self.assertEqual(summary['severity_distribution']['medium'], 1)
            self.assertEqual(summary['severity_distribution']['low'], 1)


class FraudMonitoringAPIViewTest(BaseMonitoringTest):
    """Test cases for FraudMonitoringAPIView"""
    
    def test_monitoring_api_overview(self):
        """Test monitoring API overview endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:monitoring-overview')
        
        with patch('api.fraud_detection.monitoring.FraudMonitoringService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_system_status.return_value = {
                'overall_status': 'healthy',
                'components': {'database': 'healthy'}
            }
            mock_instance.get_performance_metrics.return_value = {
                'processing_time': {'average': 2.3}
            }
            mock_instance.get_fraud_statistics.return_value = {
                'total_attempts': 100
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('system_status', data)
            self.assertIn('performance_metrics', data)
            self.assertIn('fraud_statistics', data)
    
    def test_monitoring_api_health_check(self):
        """Test monitoring API health check endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:monitoring-health')
        
        with patch('api.fraud_detection.monitoring.SystemHealthMonitor') as mock_monitor:
            mock_instance = mock_monitor.return_value
            mock_instance.get_overall_health_status.return_value = {
                'overall_status': 'healthy',
                'components': {'database': 'healthy', 'redis': 'healthy'}
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertEqual(data['overall_status'], 'healthy')
            self.assertIn('components', data)
    
    def test_monitoring_api_metrics(self):
        """Test monitoring API metrics endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:monitoring-metrics')
        
        with patch('api.fraud_detection.monitoring.MetricsCollector') as mock_collector:
            mock_instance = mock_collector.return_value
            mock_instance.collect_fraud_detection_metrics.return_value = {
                'total_attempts': 100,
                'detection_rate': 0.85
            }
            mock_instance.collect_system_performance_metrics.return_value = {
                'cpu_usage': {'percentage': 25.5},
                'memory_usage': {'percentage': 45.2}
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('fraud_metrics', data)
            self.assertIn('system_metrics', data)
    
    def test_monitoring_api_anomalies(self):
        """Test monitoring API anomalies endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:monitoring-anomalies')
        
        with patch('api.fraud_detection.monitoring.AnomalyDetector') as mock_detector:
            mock_instance = mock_detector.return_value
            mock_instance.get_anomaly_summary.return_value = {
                'total_anomalies': 2,
                'severity_distribution': {'high': 1, 'medium': 1},
                'recommendations': ['investigate_source']
            }
            
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertEqual(data['total_anomalies'], 2)
            self.assertIn('severity_distribution', data)
            self.assertIn('recommendations', data)
    
    def test_monitoring_api_unauthorized(self):
        """Test monitoring API authorization"""
        url = reverse('frauddetection:monitoring-overview')
        
        # Test without authentication
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test with regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MonitoringIntegrationTest(BaseMonitoringTest):
    """Integration tests for monitoring functionality"""
    
    def test_end_to_end_monitoring_workflow(self):
        """Test complete monitoring workflow"""
        # Step 1: System health check
        health_monitor = SystemHealthMonitor()
        with patch.multiple(
            health_monitor,
            check_database_health=MagicMock(return_value={'status': 'healthy'}),
            check_redis_health=MagicMock(return_value={'status': 'healthy'}),
            check_analysis_engine_health=MagicMock(return_value={'status': 'healthy'})
        ):
            health_status = health_monitor.get_overall_health_status()
            self.assertEqual(health_status['overall_status'], 'healthy')
        
        # Step 2: Performance monitoring
        perf_monitor = PerformanceMonitor()
        with patch('psutil.cpu_percent', return_value=25.5):
            resource_metrics = perf_monitor.collect_resource_usage_metrics()
            self.assertIn('cpu_usage', resource_metrics)
        
        # Step 3: Anomaly detection
        anomaly_detector = AnomalyDetector()
        with patch.object(anomaly_detector, 'detect_volume_anomalies') as mock_detect:
            mock_detect.return_value = [
                {'timestamp': '2023-01-01 13:00', 'severity': 'high'}
            ]
            anomalies = anomaly_detector.get_anomaly_summary()
            self.assertEqual(anomalies['total_anomalies'], 1)
        
        # Step 4: Generate comprehensive report
        monitoring_service = FraudMonitoringService()
        with patch.multiple(
            'api.fraud_detection.monitoring',
            SystemHealthMonitor=MagicMock(),
            PerformanceMonitor=MagicMock(),
            AnomalyDetector=MagicMock()
        ):
            report = monitoring_service.generate_health_report()
            self.assertIn('system_health', report)
            self.assertIn('performance_metrics', report)
            self.assertIn('anomaly_detection', report)
    
    def test_monitoring_alert_integration(self):
        """Test monitoring alert integration"""
        # Create alerts that should trigger monitoring alerts
        for i in range(12):  # Above threshold
            FraudAlert.objects.create(
                alert_type='rule_triggered',
                priority='high',
                title=f'Alert {i}',
                description='Test alert for monitoring',
                is_resolved=False
            )
        
        alert_monitor = AlertMonitor()
        threshold_check = alert_monitor.check_alert_thresholds()
        
        self.assertTrue(threshold_check['thresholds_exceeded'])
        self.assertIn('recommendations', threshold_check)
        
        # Should recommend investigation due to high alert volume
        recommendations = threshold_check['recommendations']
        self.assertTrue(any('investigate' in rec.lower() for rec in recommendations))
    
    def test_monitoring_performance_impact(self):
        """Test monitoring performance impact"""
        monitoring_service = FraudMonitoringService()
        
        # Measure time for monitoring operations
        start_time = time.time()
        
        with patch.multiple(
            'api.fraud_detection.monitoring',
            HealthChecker=MagicMock(),
            MetricsCollector=MagicMock(),
            AnomalyDetector=MagicMock()
        ):
            # Run monitoring operations
            monitoring_service.get_system_status()
            monitoring_service.get_performance_metrics()
            monitoring_service.detect_anomalies()
        
        monitoring_time = time.time() - start_time
        
        # Monitoring should complete quickly (under 1 second for mocked operations)
        self.assertLess(monitoring_time, 1.0)
    
    def test_monitoring_concurrent_access(self):
        """Test monitoring under concurrent access"""
        def monitoring_task():
            monitoring_service = FraudMonitoringService()
            with patch('api.fraud_detection.monitoring.HealthChecker') as mock_health:
                mock_health.return_value.check_system_health.return_value = {
                    'overall_status': 'healthy'
                }
                return monitoring_service.get_system_status()
        
        # Run multiple monitoring tasks concurrently
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda: results.append(monitoring_task()))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All tasks should complete successfully
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertEqual(result['overall_status'], 'healthy')

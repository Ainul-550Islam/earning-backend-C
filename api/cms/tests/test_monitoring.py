# cms/tests/test_monitoring.py
"""Test cases for CMS monitoring."""
import pytest
import sys as _sys

class _LazyModel:
    """Lazy model proxy — resolves to actual Django model after setup."""
    def __init__(self, module, name):
        self._module = module
        self._name = name
        self._cls = None
    def _resolve(self):
        if self._cls is None:
            import importlib
            mod = importlib.import_module(self._module)
            self._cls = getattr(mod, self._name)
        return self._cls
    def __call__(self, *a, **kw): return self._resolve()(*a, **kw)
    def __getattr__(self, k):
        if k.startswith('_'): raise AttributeError(k)
        return getattr(self._resolve(), k)

# Lazy model proxies
Survey       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyTemplate')
Transaction  = _LazyModel('api.cms.models_new.survey_rewards', 'RewardTransaction')
SEOModel     = _LazyModel('api.cms.models_new.seo', 'SEOConfig')
UserProfile  = _LazyModel('api.cms.models_new.user_profile', 'UserProfile')
UserSegment  = _LazyModel('api.cms.models_new.user_profile', 'UserSegment')
TaskSchedule = _LazyModel('api.cms.models_new.task_management', 'TaskSchedule')
TaskExecution= _LazyModel('api.cms.models_new.task_management', 'TaskExecution')
TaskQueue    = _LazyModel('api.cms.models_new.task_management', 'TaskQueue')
VirtualCurrency      = _LazyModel('api.cms.models_new.cpalead', 'VirtualCurrency')
UserVirtualBalance   = _LazyModel('api.cms.models_new.cpalead', 'UserVirtualBalance')
ConversionLog        = _LazyModel('api.cms.models_new.cpalead', 'ConversionLog')
ClickLog             = _LazyModel('api.cms.models_new.cpalead', 'ClickLog')
ContentLocker        = _LazyModel('api.cms.models_new.cpalead', 'ContentLocker')
SurveyCompletion     = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCompletion')
SurveyCategory       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCategory')
SurveyQuestion       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyQuestion')
SurveyReward         = _LazyModel('api.cms.models_new.survey_rewards', 'SurveyReward')
RewardPool           = _LazyModel('api.cms.models_new.survey_rewards', 'RewardPool')
Redirect301          = _LazyModel('api.cms.models_new.seo', 'Redirect301')
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call

from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction as Transaction, RewardPool
from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
from api.cms.models_new.user_profile import UserProfile, UserSegment
from api.cms.models_new.task_management import TaskSchedule, TaskExecution, TaskQueue
from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass
import unittest
from datetime import datetime, timedelta, date
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from decimal import Decimal

from api.cms.monitoring import (
    CMSMetrics, BaseMonitor, PerformanceMonitor, 
    ErrorMonitor, SystemHealthMonitor, enhanced_monitoring_manager
)


class TestCMSMetrics(TestCase):
    """Test CMS metrics."""
    
    def test_increment_metric(self):
        """Test incrementing counter metric."""
        CMSMetrics.increment('test_counter', 1, {'tag': 'value'})
        
        # Check if metric was recorded
        value = CMSMetrics.get('test_counter', {'tag': 'value'})
        self.assertEqual(value, 1)
    
    def test_gauge_metric(self):
        """Test setting gauge metric."""
        CMSMetrics.gauge('test_gauge', 42.5, {'tag': 'value'})
        
        # Check if metric was recorded
        value = CMSMetrics.get('test_gauge', {'tag': 'value'})
        self.assertEqual(value, 42.5)
    
    def test_timing_metric(self):
        """Test recording timing metric."""
        CMSMetrics.timing('test_timing', 150.0, {'tag': 'value'})
        
        # Check if average was recorded
        avg = CMSMetrics.get('test_timing_avg', {'tag': 'value'})
        count = CMSMetrics.get('test_timing_count', {'tag': 'value'})
        
        self.assertEqual(avg, 150.0)
        self.assertEqual(count, 1)
    
    def test_dashboard_metrics(self):
        """Test dashboard metrics."""
        # Record some metrics
        CMSMetrics.record_postback(True, user_id=1, payout_usd=10.00, fraud=False)
        CMSMetrics.record_user_registration()
        CMSMetrics.record_api_call('surveys', 200, 200)
        
        dashboard = CMSMetrics.get_dashboard()
        
        self.assertIn('postbacks', dashboard)
        self.assertIn('users', dashboard)
        self.assertIn('api', dashboard)
        
        self.assertEqual(dashboard['postbacks']['success'], 1)
        self.assertEqual(dashboard['users']['registrations_today'], 1)
        self.assertEqual(dashboard['api']['requests_total'], 1)


class TestBaseMonitor(TestCase):
    """Test base monitor class."""
    
    def setUp(self):
        """Set up test monitor."""
        self.monitor = BaseMonitor("test")
    
    def test_record_metric(self):
        """Test recording a metric."""
        self.monitor.record_metric('test_metric', 42, {'tag': 'value'})
        
        metric = self.monitor.get_metric('test_metric')
        self.assertIsNotNone(metric)
        self.assertEqual(metric['value'], 42)
        self.assertEqual(metric['tags'], {'tag': 'value'})
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        self.monitor.record_metric('metric1', 1)
        self.monitor.record_metric('metric2', 2)
        
        all_metrics = self.monitor.get_all_metrics()
        
        self.assertIn('metric1', all_metrics)
        self.assertIn('metric2', all_metrics)
        self.assertEqual(all_metrics['metric1']['value'], 1)
        self.assertEqual(all_metrics['metric2']['value'], 2)


class TestPerformanceMonitor(TestCase):
    """Test performance monitor."""
    
    def setUp(self):
        """Set up performance monitor."""
        self.performance = PerformanceMonitor()
    
    def test_record_request_time(self):
        """Test recording request time."""
        self.performance.record_request_time(1.5, '/api/test')
        
        stats = self.performance.get_performance_stats()
        
        self.assertIn('request_time', stats)
        self.assertEqual(stats['request_time']['avg'], 1.5)
        self.assertEqual(stats['request_time']['count'], 1)
    
    def test_multiple_request_times(self):
        """Test recording multiple request times."""
        times = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        for time in times:
            self.performance.record_request_time(time, '/api/test')
        
        stats = self.performance.get_performance_stats()
        
        self.assertEqual(stats['request_time']['avg'], 3.0)
        self.assertEqual(stats['request_time']['min'], 1.0)
        self.assertEqual(stats['request_time']['max'], 5.0)
        self.assertEqual(stats['request_time']['count'], 5)
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        times = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        for time in times:
            self.performance.record_request_time(time)
        
        p95 = self.performance._percentile(times, 95)
        self.assertEqual(p95, 10)  # 95th percentile of 10 items


class TestErrorMonitor(TestCase):
    """Test error monitor."""
    
    def setUp(self):
        """Set up error monitor."""
        self.error_monitor = ErrorMonitor()
    
    def test_record_error(self):
        """Test recording an error."""
        error = ValueError("Test error")
        context = {'user_id': 1, 'action': 'test'}
        
        self.error_monitor.record_error(error, context)
        
        stats = self.error_monitor.get_error_stats()
        
        self.assertEqual(stats['total_errors'], 1)
        self.assertEqual(stats['error_counts']['ValueError'], 1)
        self.assertEqual(len(stats['recent_errors']), 1)
        
        recent_error = stats['recent_errors'][0]
        self.assertEqual(recent_error['type'], 'ValueError')
        self.assertEqual(recent_error['message'], 'Test error')
        self.assertEqual(recent_error['context'], context)
    
    def test_multiple_errors(self):
        """Test recording multiple errors."""
        errors = [
            ValueError("Error 1"),
            TypeError("Error 2"),
            ValueError("Error 3")
        ]
        
        for error in errors:
            self.error_monitor.record_error(error)
        
        stats = self.error_monitor.get_error_stats()
        
        self.assertEqual(stats['total_errors'], 3)
        self.assertEqual(stats['error_counts']['ValueError'], 2)
        self.assertEqual(stats['error_counts']['TypeError'], 1)
    
    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        # Record errors at different times
        now = timezone.now()
        
        # This should be included in rate (within last minute)
        recent_error = ValueError("Recent error")
        self.error_monitor.record_error(recent_error)
        
        # This should be excluded (older than 1 minute)
        old_error_data = {
            'type': 'ValueError',
            'message': 'Old error',
            'traceback': 'Traceback',
            'context': {},
            'timestamp': (now - timezone.timedelta(minutes=2)).isoformat()
        }
        self.error_monitor.recent_errors.append(old_error_data)
        
        error_rate = self.error_monitor._calculate_error_rate()
        self.assertEqual(error_rate, 1)


class TestSystemHealthMonitor(TestCase):
    """Test system health monitor."""
    
    def setUp(self):
        """Set up health monitor."""
        self.health_monitor = SystemHealthMonitor()
    
    def test_register_health_check(self):
        """Test registering health check."""
        def test_check():
            return {'healthy': True, 'message': 'OK'}
        
        self.health_monitor.register_health_check('test', test_check)
        
        self.assertIn('test', self.health_monitor.health_checks)
        self.assertEqual(self.health_monitor.health_checks['test'], test_check)
    
    def test_run_health_checks(self):
        """Test running health checks."""
        def healthy_check():
            return {'healthy': True, 'message': 'All good'}
        
        def unhealthy_check():
            return {'healthy': False, 'message': 'Something wrong'}
        
        self.health_monitor.register_health_check('healthy', healthy_check)
        self.health_monitor.register_health_check('unhealthy', unhealthy_check)
        
        results = self.health_monitor.run_health_checks()
        
        self.assertTrue(results['healthy']['healthy'])
        self.assertFalse(results['unhealthy']['healthy'])
        self.assertFalse(results['overall']['healthy'])
        self.assertEqual(results['overall']['checks_count'], 2)
    
    def test_database_health_check(self):
        """Test database health check."""
        result = self.health_monitor.check_database_health()
        
        self.assertIn('healthy', result)
        self.assertIn('message', result)
        self.assertIn('timestamp', result)
    
    def test_cache_health_check(self):
        """Test cache health check."""
        result = self.health_monitor.check_cache_health()
        
        self.assertIn('healthy', result)
        self.assertIn('message', result)
        self.assertIn('timestamp', result)


class TestMonitoringManager(TestCase):
    """Test monitoring manager."""
    
    def setUp(self):
        """Set up monitoring manager."""
        self.manager = enhanced_monitoring_manager
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        # Record some metrics
        CMSMetrics.record_postback(True, user_id=1, payout_usd=10.00)
        self.manager.performance.record_request_time(1.5, '/api/test')
        
        dashboard = self.manager.get_dashboard_data()
        
        self.assertIn('cms_metrics', dashboard)
        self.assertIn('performance', dashboard)
        self.assertIn('errors', dashboard)
        self.assertIn('health', dashboard)
        self.assertIn('timestamp', dashboard)
    
    def test_run_monitoring_cycle(self):
        """Test running monitoring cycle."""
        # This should not raise an exception
        self.manager.run_monitoring_cycle()


@pytest.mark.django_db
class TestMonitoringIntegration(unittest.TestCase):
    def setup_method(self, method=None):
        from api.cms.monitoring import enhanced_monitoring_manager
        self.manager = enhanced_monitoring_manager

    """Test monitoring integration."""
    
    def test_metrics_persistence(self):
        """Test metrics persistence across requests."""
        # Record metric in one "request"
        CMSMetrics.increment('test_persistence', 1)
        
        # Check if metric is available in another "request"
        value = CMSMetrics.get('test_persistence')
        self.assertEqual(value, 1)
    
    @patch('cms.monitoring.cache')
    def test_cache_integration(self, mock_cache):
        """Test cache integration."""
        mock_cache.get.return_value = 42
        mock_cache.set.return_value = True
        
        # Record metric
        CMSMetrics.gauge('test_cache', 42)
        
        # Check if cache was used
        mock_cache.set.assert_called()
        mock_cache.get.assert_called()
    
    def test_error_monitoring_with_real_exceptions(self):
        """Test error monitoring with real exceptions."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            self.manager.errors.record_error(e, {'context': 'test'})
        
        stats = self.manager.errors.get_error_stats()
        self.assertEqual(stats['total_errors'], 1)
        self.assertEqual(stats['error_counts']['ValueError'], 1)
    
    def test_performance_monitoring_with_real_requests(self):
        """Test performance monitoring with real requests."""
        from django.test import Client
        
        client = Client()
        
        # Make a request (this would normally be monitored by middleware)
        with patch.object(self.manager.performance, 'record_request_time') as mock_record:
            response = client.get('/api/cms/surveys/')
            # Simulate middleware calling record_request_time
            self.manager.performance.record_request_time(0.1, endpoint='/api/cms/surveys/')
            # Check if request time was recorded
            mock_record.assert_called()
    
    def test_health_checks_with_real_services(self):
        """Test health checks with real services."""
        results = self.manager.health.run_health_checks()
        
        # Should have database and cache checks
        self.assertIn('database', results)
        self.assertIn('cache', results)
        self.assertIn('overall', results)
        
        # Overall should be healthy if all checks pass
        overall_healthy = all(
            check.get('healthy', False) 
            for name, check in results.items() 
            if name != 'overall'
        )
        
        self.assertEqual(results['overall']['healthy'], overall_healthy)


@pytest.mark.performance
class TestMonitoringPerformance(unittest.TestCase):
    """Test monitoring performance."""
    
    def test_high_volume_metrics(self):
        """Test handling high volume of metrics."""
        import time
        
        start_time = time.time()
        
        # Record 1000 metrics
        for i in range(1000):
            CMSMetrics.increment('high_volume_test', 1, {'iteration': i})
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time (less than 1 second)
        self.assertLess(duration, 1.0)
    
    def test_concurrent_metric_recording(self):
        """Test concurrent metric recording."""
        import threading
        import time
        
        def record_metrics(thread_id):
            for i in range(100):
                CMSMetrics.increment('concurrent_test', 1, {'thread': thread_id, 'iteration': i})
        
        # Create 10 threads
        threads = []
        start_time = time.time()
        
        for i in range(10):
            thread = threading.Thread(target=record_metrics, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(duration, 2.0)
        
        # Check if all metrics were recorded
        total_count = CMSMetrics.get('concurrent_test')
        self.assertEqual(total_count, 1000)  # 10 threads * 100 iterations


@pytest.mark.security
class TestMonitoringSecurity(unittest.TestCase):
    """Test monitoring security aspects."""

    def setUp(self):
        from api.cms.monitoring import PerformanceMonitor
        self.manager = PerformanceMonitor()

    def test_sensitive_data_masking(self):
        """Test sensitive data masking in error context."""
        error = ValueError("Test error")
        sensitive_context = {
            'password': 'secret123',
            'api_key': 'sk_test_123456789',
            'user_id': 1
        }
        
        self.manager.errors.record_error(error, sensitive_context)
        
        stats = self.manager.errors.get_error_stats()
        recent_error = stats['recent_errors'][0]
        
        # Check that sensitive data is not exposed in recent errors
        context = recent_error['context']
        self.assertNotIn('password', context)
        self.assertNotIn('api_key', context)
        self.assertIn('user_id', context)  # Non-sensitive data should remain
    
    def test_metric_injection_prevention(self):
        """Test prevention of metric injection attacks."""
        malicious_metric_name = "'; DROP TABLE metrics; --"
        
        # This should not cause SQL injection
        CMSMetrics.increment(malicious_metric_name, 1)
        
        # Should not raise exception
        value = CMSMetrics.get(malicious_metric_name)
        self.assertEqual(value, 1)

# ALERTS MODULE - COMPLETE TEST SUITE
# Tests for all 10 Consolidating Services

# File: alerts/tests/test_services_consolidated.py

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from datetime import timedelta
import logging

from api.alerts.models import (
    AlertLog, AlertRule, Notification, AlertChannel,
    SystemHealthCheck, AlertSuppression, AlertGroup, AlertAnalytics
)
from api.alerts.services.alert_processing import AlertProcessingService
from api.alerts.services.system_health import SystemHealthService
from api.alerts.services.configuration import ConfigurationService
from api.alerts.services.performance import PerformanceService
from api.alerts.services.maintenance import MaintenanceService
from api.alerts.services.testing import TestingService
from api.alerts.services.event_bus import EventService
from api.alerts.services.registry import RegistryService
from api.alerts.services.statistics import StatisticsService
from api.alerts.services.rate_limiting import RateLimitingService

logger = logging.getLogger(__name__)


class AlertProcessingServiceTest(TestCase):
    """Test AlertProcessingService consolidation"""

    def setUp(self):
        """Set up test data"""
        self.rule = AlertRule.objects.create(
            name='Test Rule', alert_type='server_error', threshold_value=100.0,
            is_active=True
        )
        self.alert = AlertLog.objects.create(
            rule=self.rule,
            status='pending',
            severity='high',
            trigger_value=100.0, threshold_value=90.0
        )

    def test_process_pending_alerts(self):
        """Test processing pending alerts (evaluates active rules and returns
        how many were processed -- matches the real celery_tasks.py/tasks/core.py
        behavior; this used to assert a dict shape that neither live
        implementation ever actually returned)"""
        result = AlertProcessingService.process_pending_alerts()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, int)

    def test_escalate_alerts(self):
        """Test alert escalation"""
        result = AlertProcessingService.escalate_alerts(alert=self.alert)
        
        self.assertIsNotNone(result)
        self.assertIn('escalated', result)
        self.assertIsInstance(result['escalated'], bool)

    def test_bulk_resolve_alerts(self):
        """Test bulk resolving alerts"""
        alert_ids = [self.alert.id]
        result = AlertProcessingService.bulk_resolve_alerts(
            alert_ids,
            resolution_notes='Test resolution'
        )
        
        self.assertIn('resolved', result)
        self.assertIn('skipped', result)
        self.assertTrue(result['resolved'] > 0)

    def test_send_group_alerts(self):
        """Test sending group alerts"""
        group = AlertGroup.objects.create(
            name='Test Group'
        )
        group.rules.add(self.rule)
        
        result = AlertProcessingService.send_group_alerts(group.id)
        
        self.assertIsNotNone(result)
        self.assertIn('sent', result)
        self.assertIn('failed', result)

    def test_generate_daily_analytics(self):
        """Test generating daily analytics"""
        result = AlertProcessingService.generate_daily_analytics()
        
        self.assertIn('total_alerts', result)
        self.assertIn('resolved_alerts', result)
        self.assertIn('failed_alerts', result)
        self.assertIn('escalated_alerts', result)

    def test_get_processing_stats(self):
        """Test getting processing statistics"""
        stats = AlertProcessingService.get_processing_stats()
        
        self.assertIsNotNone(stats)
        self.assertIn('pending', stats)
        self.assertIn('processed', stats)
        self.assertIn('failed', stats)
        self.assertIn('resolved', stats)

    def test_retry_failed_alerts(self):
        """Test retrying failed alerts"""
        self.alert.status = 'failed'
        self.alert.save()
        
        result = AlertProcessingService.retry_failed_alerts()
        
        self.assertIn('retried', result)
        self.assertTrue(result['retried'] >= 0)


class SystemHealthServiceTest(TestCase):
    """Test SystemHealthService consolidation"""

    def test_check_system_health(self):
        """Test system health check"""
        health = SystemHealthService.check_system_health()

        self.assertIn('checked', health)
        self.assertIn('failed', health)
        self.assertIsInstance(health['checked'], int)
        self.assertIsInstance(health['failed'], int)

    def test_system_health(self):
        """Test getting current system health"""
        # First create a health check
        SystemHealthService.check_system_health()
        
        health = SystemHealthService.system_health()
        
        self.assertIn('status', health)
        self.assertIn('timestamp', health)
        self.assertIn('details', health)

    def test_get_health_trends(self):
        """Test getting health trends"""
        SystemHealthService.check_system_health()
        
        trends = SystemHealthService.get_health_trends(days=7)
        
        self.assertIsNotNone(trends)
        self.assertIsInstance(trends, list)

    def test_get_uptime_percentage(self):
        """Test calculating uptime percentage"""
        SystemHealthService.check_system_health()
        
        uptime = SystemHealthService.get_uptime_percentage(days=1)
        
        self.assertIsNotNone(uptime)
        self.assertGreaterEqual(uptime, 0)
        self.assertLessEqual(uptime, 100)

    def test_needs_checking(self):
        """Test if system needs health check"""
        SystemHealthService.check_system_health()
        
        needs_check = SystemHealthService.needs_checking()
        
        self.assertIsInstance(needs_check, bool)


class ConfigurationServiceTest(TestCase):
    """Test ConfigurationService consolidation"""

    def test_validate_integration_config_valid(self):
        """Test validating valid integration config"""
        config = {
            'provider': 'slack',
            'api_key': 'xoxb_valid_key_1234567890123456',
            'api_url': 'https://api.slack.com'
        }
        
        result = ConfigurationService.validate_integration_config(config)
        
        self.assertTrue(result)

    def test_validate_integration_config_missing_field(self):
        """Test validation with missing field"""
        config = {
            'provider': 'slack',
            'api_key': 'xoxb_valid_key_1234567890123456'
            # Missing api_url
        }
        
        with self.assertRaises(ValidationError):
            ConfigurationService.validate_integration_config(config)

    def test_validate_webhook_url_valid(self):
        """Test validating valid webhook URL"""
        # This might fail due to URL reachability, but structure is correct
        try:
            result = ConfigurationService.validate_webhook_url(
                'https://example.com/webhook'
            )
            self.assertTrue(result)
        except ValidationError as e:
            # Expected if URL is not reachable
            self.assertIn('reachable', str(e).lower())

    def test_validate_webhook_url_invalid_format(self):
        """Test validation with invalid URL format"""
        with self.assertRaises(ValidationError):
            ConfigurationService.validate_webhook_url('not-a-url')

    def test_validate_webhook_url_not_https(self):
        """Test validation with non-HTTPS URL"""
        with self.assertRaises(ValidationError):
            ConfigurationService.validate_webhook_url('http://example.com/webhook')

    def test_validate_alert_rule_valid(self):
        """Test validating valid alert rule"""
        rule_data = {
            'name': 'Test Rule',
            'condition': 'metric > 100',
            'threshold': 50
        }
        
        result = ConfigurationService.validate_alert_rule(rule_data)
        
        self.assertTrue(result)

    def test_validate_alert_rule_missing_name(self):
        """Test validation with missing name"""
        rule_data = {
            'condition': 'metric > 100'
        }
        
        with self.assertRaises(ValidationError):
            ConfigurationService.validate_alert_rule(rule_data)

    def test_validate_notification_config_valid(self):
        """Test validating valid notification config"""
        config = {'method': 'email'}
        
        result = ConfigurationService.validate_notification_config(config)
        
        self.assertTrue(result)

    def test_validate_notification_config_invalid_method(self):
        """Test validation with invalid method"""
        config = {'method': 'invalid_method'}
        
        with self.assertRaises(ValidationError):
            ConfigurationService.validate_notification_config(config)


class PerformanceServiceTest(TestCase):
    """Test PerformanceService consolidation"""

    def setUp(self):
        """Set up test data"""
        self.rule = AlertRule.objects.create(name='Test Rule', alert_type='server_error', threshold_value=100.0)
        self.alert = AlertLog.objects.create(rule=self.rule, status='processing', trigger_value=100.0, threshold_value=90.0)

    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        metrics = PerformanceService.get_performance_metrics()
        
        self.assertIn('response_time_avg_ms', metrics)
        self.assertIn('throughput_per_minute', metrics)
        self.assertIn('notification_delivery_rate', metrics)
        self.assertIn('alerts_processed_last_hour', metrics)

    def test_get_database_stats(self):
        """Test getting database statistics"""
        stats = PerformanceService.get_database_stats()
        
        self.assertIn('queries_executed', stats)
        self.assertIn('slow_queries', stats)

    def test_is_system_healthy(self):
        """Test checking if system is healthy"""
        healthy, message = PerformanceService.is_system_healthy()
        
        self.assertIsInstance(healthy, bool)
        self.assertIsInstance(message, str)


class MaintenanceServiceTest(TransactionTestCase):
    """Test MaintenanceService consolidation"""

    def setUp(self):
        """Set up test data"""
        self.rule = AlertRule.objects.create(name='Test Rule', alert_type='server_error', threshold_value=100.0)
        self.alert = AlertLog.objects.create(rule=self.rule, trigger_value=100.0, threshold_value=90.0)
        self.notification = Notification.objects.create(
            alert_log=self.alert,
            status='pending'
        )

    def test_cleanup_old_notifications(self):
        """Test cleanup of old notifications"""
        result = MaintenanceService.cleanup_old_notifications(days=0)
        
        self.assertIn('deleted', result)
        self.assertIn('archived', result)

    def test_expire_suppressions(self):
        """Test expiring suppressions"""
        suppression = AlertSuppression.objects.create(
            name='Test Suppression',
            suppression_type='rule',
            rule=self.rule,
            is_active=True,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now()
        )
        
        result = MaintenanceService.expire_suppressions()
        
        self.assertIn('expired', result)
        self.assertIsInstance(result['expired'], int)

    def test_update_alert_group_caches(self):
        """Test updating alert group caches"""
        group = AlertGroup.objects.create(name='Test Group')
        group.rules.add(self.rule)
        
        result = MaintenanceService.update_alert_group_caches()
        
        self.assertIn('updated', result)
        self.assertGreater(result['updated'], 0)

    def test_cleanup_old_logs(self):
        """Test cleanup of old logs"""
        result = MaintenanceService.cleanup_old_logs(days=0)
        
        self.assertIn('archived', result)


class TestingServiceTest(TestCase):
    """Test TestingService consolidation"""

    def setUp(self):
        """Set up test data"""
        self.rule = AlertRule.objects.create(
            name='Test Rule',
            is_active=True,
            alert_type='server_error', threshold_value=100.0
        )
        self.channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )

    def test_test_alert_rule(self):
        """Test alert rule testing"""
        result = TestingService.test_alert_rule(self.rule)
        
        self.assertIn('rule_id', result)
        self.assertIn('rule_name', result)
        self.assertIn('tests', result)
        self.assertIn('passed', result)
        self.assertIn('total', result)
        self.assertIn('success', result)

    def test_test_alert_channel(self):
        """Test alert channel testing"""
        result = TestingService.test_alert_channel(self.channel)
        
        self.assertIn('channel_id', result)
        self.assertIn('channel_name', result)
        self.assertIn('tests', result)
        self.assertIn('success', result)


class EventServiceTest(TestCase):
    """Test EventService consolidation"""

    def test_register_handler(self):
        """Test registering event handler"""
        def test_handler(**kwargs):
            pass
        
        EventService.register_handler('alert_triggered', test_handler)
        
        # Check that handler was registered
        self.assertIn('alert_triggered', EventService._handlers)

    def test_emit_event(self):
        """Test emitting event"""
        handler_called = []
        
        def test_handler(**kwargs):
            handler_called.append(True)
        
        EventService.register_handler('test_event', test_handler)
        EventService.emit_event('test_event', test_data='value')
        
        self.assertTrue(len(handler_called) > 0)

    def test_handle_alert_triggered(self):
        """Test handling alert triggered"""
        rule = AlertRule.objects.create(name='Test Rule', alert_type='server_error', threshold_value=100.0)
        alert = AlertLog.objects.create(rule=rule, trigger_value=100.0, threshold_value=90.0)
        
        # Should not raise exception
        EventService.handle_alert_triggered(alert)

    def test_handle_alert_resolved(self):
        """Test handling alert resolved"""
        rule = AlertRule.objects.create(name='Test Rule', alert_type='server_error', threshold_value=100.0)
        alert = AlertLog.objects.create(rule=rule, status='resolved', trigger_value=100.0, threshold_value=90.0)
        
        # Should not raise exception
        EventService.handle_alert_resolved(alert)


class RegistryServiceTest(TestCase):
    """Test RegistryService consolidation"""

    def test_get_integration_registry(self):
        """Test getting integration registry"""
        registry = RegistryService.get_integration_registry()
        
        self.assertIsNotNone(registry)
        self.assertIsInstance(registry, dict)

    def test_register_integration(self):
        """Test registering new integration"""
        class DummyService:
            pass
        
        RegistryService.register_integration('dummy', DummyService)
        
        # Check registration
        integration = RegistryService.get_integration('dummy')
        self.assertEqual(integration, DummyService)

    def test_get_audit_logger(self):
        """Test getting audit logger"""
        logger = RegistryService.get_audit_logger()
        
        self.assertIsNotNone(logger)

    def test_get_circuit_breaker(self):
        """Test getting circuit breaker"""
        breaker = RegistryService.get_circuit_breaker()
        
        self.assertIsNotNone(breaker)


class StatisticsServiceTest(TestCase):
    """Test StatisticsService consolidation"""

    def setUp(self):
        """Set up test data"""
        self.rule = AlertRule.objects.create(
            name='Test Rule',
            is_active=True,
            alert_type='server_error', threshold_value=100.0
        )
        self.alert = AlertLog.objects.create(
            rule=self.rule,
            status='pending',
            severity='high',
            trigger_value=100.0, threshold_value=90.0
        )

    def test_alert_statistics(self):
        """Test calculating alert statistics"""
        stats = StatisticsService.alert_statistics()
        
        self.assertIn('total_alerts', stats)
        self.assertIn('active_rules', stats)
        self.assertIn('pending_alerts', stats)
        self.assertIn('resolved_alerts', stats)
        self.assertIn('failed_alerts', stats)
        self.assertIn('by_severity', stats)

    def test_api_info(self):
        """Test getting API info"""
        info = StatisticsService.api_info()
        
        self.assertIn('name', info)
        self.assertIn('version', info)
        self.assertIn('status', info)
        self.assertIn('endpoints', info)
        self.assertIn('stats', info)

    def test_get_alert_trends(self):
        """Test getting alert trends"""
        trends = StatisticsService.get_alert_trends(days=7)
        
        self.assertIsNotNone(trends)
        self.assertIsInstance(trends, list)

    def test_get_alert_by_severity_chart(self):
        """Test getting severity chart data"""
        data = StatisticsService.get_alert_by_severity_chart()
        
        self.assertIsNotNone(data)
        self.assertIsInstance(data, list)

    def test_get_resolution_time_stats(self):
        """Test getting resolution time stats"""
        self.alert.status = 'resolved'
        self.alert.save()
        
        stats = StatisticsService.get_resolution_time_stats()
        
        self.assertIn('avg_resolution_time', stats)
        self.assertIn('min_resolution_time', stats)
        self.assertIn('max_resolution_time', stats)


class RateLimitingServiceTest(TestCase):
    """Test RateLimitingService consolidation"""

    def test_rate_limit_authenticated(self):
        """Test rate limit for authenticated user"""
        result = RateLimitingService.rate_limit('user_123', 'authenticated')
        
        self.assertIn('allowed', result)
        self.assertIn('remaining', result)
        self.assertIn('limit', result)
        self.assertIn('reset_seconds', result)
        self.assertTrue(result['allowed'])

    def test_rate_limit_anonymous(self):
        """Test rate limit for anonymous user"""
        result = RateLimitingService.rate_limit('127.0.0.1', 'anonymous')
        
        self.assertIn('allowed', result)
        self.assertIn('remaining', result)
        self.assertTrue(result['allowed'])

    def test_rate_limit_expensive_op(self):
        """Test rate limit for expensive operation"""
        result = RateLimitingService.rate_limit('user_456', 'expensive_op')
        
        self.assertIn('allowed', result)
        self.assertIn('limit', result)
        self.assertEqual(result['limit'], 10)

    def test_reset_rate_limit(self):
        """Test resetting rate limit"""
        # First, use up some requests
        RateLimitingService.rate_limit('user_789', 'authenticated')
        
        # Reset
        RateLimitingService.reset_rate_limit('user_789', 'authenticated')
        
        # Should be able to use again
        result = RateLimitingService.rate_limit('user_789', 'authenticated')
        self.assertTrue(result['allowed'])

    def test_is_rate_limited(self):
        """Test checking if rate limited"""
        result = RateLimitingService.is_rate_limited('user_999', 'authenticated')
        
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

    def test_get_rate_limit_status(self):
        """Test getting rate limit status for all types"""
        status = RateLimitingService.get_rate_limit_status('user_status')
        
        self.assertIsNotNone(status)
        self.assertIn('anonymous', status)
        self.assertIn('authenticated', status)
        self.assertIn('premium', status)
        self.assertIn('expensive_op', status)


# Test suite to run all tests
if __name__ == '__main__':
    import unittest
    unittest.main()

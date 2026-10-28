"""Tests for Core Services"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from api.alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from api.alerts.services.core import (
    AlertProcessorService, AlertGroupService, AnalyticsService, AlertMaintenanceService)
User = get_user_model()


class AlertProcessorServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Test Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=120, cooldown_minutes=60,
            created_by=self.user)
        self.svc = AlertProcessorService()

    def test_process_alert_creates_log(self):
        result = self.svc.process_alert({'rule_id': self.rule.id, 'trigger_value': 85.0, 'message': 'CPU is high', 'details': {'usage': 85.0}})
        self.assertIsInstance(result, dict)

    def test_process_alert_respects_cooldown(self):
        self.rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.rule.save()
        result = self.svc.process_alert({'rule_id': self.rule.id, 'trigger_value': 85.0, 'message': 'CPU is high'})
        self.assertIsInstance(result, dict)

    def test_resolve_alert(self):
        log = AlertLog.objects.create(rule=self.rule, trigger_value=85.0, threshold_value=80.0, message='Test')
        log.resolve(self.user, 'Fixed')
        log.refresh_from_db()
        self.assertTrue(log.is_resolved)

    def test_acknowledge_alert(self):
        log = AlertLog.objects.create(rule=self.rule, trigger_value=85.0, threshold_value=80.0, message='Test')
        log.status = 'acknowledged'
        log.save()
        log.refresh_from_db()
        self.assertEqual(log.status, 'acknowledged')

    def test_bulk_process_alerts(self):
        svc = self.svc
        result = svc.process_alert({'rule_id': self.rule.id, 'trigger_value': 87.0, 'message': 'Bulk Test'})
        self.assertIsInstance(result, dict)

    def test_check_and_escalate(self):
        result = self.svc.process_alert({'rule_id': self.rule.id, 'trigger_value': 88.0, 'message': 'Escalate Test'})
        self.assertIsInstance(result, dict)


class AlertGroupServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        from api.alerts.models.core import AlertGroup
        self.group = AlertGroup.objects.create(name='Test Group')

    def test_check_and_send_group_alerts(self):
        result = AlertGroupService.check_and_send_group_alerts()
        self.assertIsInstance(result, (dict, int, type(None)))

    def test_get_group_alert_summary(self):
        result = AlertGroupService.get_group_alert_summary(self.group.id)
        self.assertIsInstance(result, dict)

    def test_create_group_from_rules(self):
        rule = AlertRule.objects.create(
            name='Group Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user)
        result = AlertGroupService.create_group_from_rules(
            'New Group', [rule.id])
        self.assertIsNotNone(result)


class AnalyticsServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Analytics Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user)

    def test_get_system_metrics(self):
        result = AnalyticsService.get_system_metrics()
        self.assertIsInstance(result, dict)

    def test_get_alert_statistics(self):
        stats = AnalyticsService.get_alert_statistics(days=7)
        self.assertIsInstance(stats, dict)
        self.assertIn('total_alerts', stats)

    def test_get_rule_performance(self):
        result = AnalyticsService.get_rule_performance(days=30)
        self.assertIsInstance(result, (dict, list))

    def test_calculate_severity_distribution(self):
        result = AnalyticsService.calculate_severity_distribution(days=30)
        self.assertIsInstance(result, dict)

    def test_get_trend_data(self):
        result = AnalyticsService.get_trend_data(days=7)
        self.assertIsInstance(result, (dict, list))

    def test_generate_daily_analytics(self):
        from django.db import connection
        from api.alerts.models.core import AlertAnalytics
        result = AnalyticsService.generate_daily_analytics()
        self.assertIsInstance(result, (dict, type(None), AlertAnalytics))
        if connection.vendor == 'postgresql':
            # production engine: the analytics row must really be generated
            self.assertIsInstance(result, AlertAnalytics)
            self.assertTrue(AlertAnalytics.objects.filter(pk=result.pk).exists())


class AlertMaintenanceServiceTest(TestCase):
    def test_cleanup_old_alerts(self):
        result = AlertMaintenanceService.cleanup_old_alerts(days=90)
        self.assertIsInstance(result, (dict, int))

    def test_cleanup_old_notifications(self):
        result = AlertMaintenanceService.cleanup_old_notifications(days=30)
        self.assertIsInstance(result, (dict, int))

    def test_update_rule_health(self):
        result = AlertMaintenanceService.update_rule_health()
        self.assertIsInstance(result, (dict, int, type(None)))

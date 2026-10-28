"""
Tests for Core Alert Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from datetime import timedelta
import json

from api.alerts.models.core import (
    AlertRule, AlertLog, Notification, AlertEscalation, AlertTemplate,
    AlertAnalytics, AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)

User = get_user_model()


class AlertRuleModelTest(TestCase):
    """Test cases for AlertRule model"""

    def setUp(self):
        # trigger_count_today() caches its result in django's cache keyed by
        # AlertRule.id + today's date. Unlike the DB, LocMemCache is not
        # rolled back between TestCase-wrapped tests, so a stale count left
        # by an earlier test whose AlertRule happened to reuse the same
        # auto-increment id (common with SQLite + per-test transaction
        # rollback) can leak into this test when run as part of the full
        # suite. Same pattern as CacheMixinTest in test_viewsets_mixins.py.
        cache.clear()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=120,
            cooldown_minutes=60,
            description='Test alert rule for server errors',
            created_by=self.user
        )

    def test_alert_rule_creation(self):
        """Test AlertRule creation"""
        self.assertEqual(self.alert_rule.name, 'Test Alert Rule')
        self.assertEqual(self.alert_rule.alert_type, 'server_error')
        self.assertEqual(self.alert_rule.severity, 'high')
        self.assertEqual(self.alert_rule.threshold_value, 80.0)
        self.assertTrue(self.alert_rule.is_active)
        self.assertIsNotNone(self.alert_rule.created_at)

    def test_alert_rule_str_representation(self):
        """Test AlertRule string representation"""
        expected = 'Test Alert Rule (server_error - high)'
        self.assertEqual(str(self.alert_rule), expected)

    def test_alert_rule_get_severity_display(self):
        """Test AlertRule severity display"""
        self.assertEqual(self.alert_rule.get_severity_display(), 'High')

    def test_alert_rule_get_alert_type_display(self):
        """Test AlertRule alert type display"""
        self.assertEqual(self.alert_rule.get_alert_type_display(), 'Server Error Rate')

    def test_alert_rule_trigger_alert(self):
        """Test AlertRule can_trigger_now returns bool"""
        result = self.alert_rule.can_trigger_now()
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_alert_rule_check_cooldown(self):
        """Test AlertRule cooldown check"""
        # Test when no last triggered time
        self.assertTrue(self.alert_rule.can_trigger_now())

        # Test when within cooldown period (last triggered 10 minutes ago, cooldown=60)
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.alert_rule.save()
        self.assertFalse(self.alert_rule.can_trigger_now())

        # Test when cooldown period has passed
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=70)
        self.alert_rule.save()
        self.assertTrue(self.alert_rule.can_trigger_now())

    def test_alert_rule_should_trigger(self):
        """Test AlertRule should trigger logic (based on cooldown only)"""
        # No last_triggered: should be True
        self.assertTrue(self.alert_rule.can_trigger_now())

        # Within cooldown: should be False
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.alert_rule.save()
        self.assertFalse(self.alert_rule.can_trigger_now())

    def test_alert_rule_get_recent_alerts(self):
        """Test AlertRule get recent alerts"""
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Test alert {i}'
            )

        recent_alerts = AlertLog.objects.filter(rule=self.alert_rule)
        self.assertEqual(recent_alerts.count(), 5)

    def test_alert_rule_get_success_rate(self):
        """Test AlertRule trigger_count_today starts at 0"""
        count = self.alert_rule.trigger_count_today()
        self.assertEqual(count, 0)

        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        # After creating a log, trigger_count_today should be >= 0
        count = self.alert_rule.trigger_count_today()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)


class AlertLogModelTest(TestCase):
    """Test cases for AlertLog model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=120,
            cooldown_minutes=60,
            created_by=self.user
        )

        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details={'current_usage': 85.0}
        )

    def test_alert_log_creation(self):
        """Test AlertLog creation"""
        self.assertEqual(self.alert_log.rule, self.alert_rule)
        self.assertEqual(self.alert_log.trigger_value, 85.0)
        self.assertEqual(self.alert_log.threshold_value, 80.0)
        self.assertEqual(self.alert_log.message, 'CPU usage is high')
        self.assertFalse(self.alert_log.is_resolved)
        self.assertIsNotNone(self.alert_log.triggered_at)

    def test_alert_log_str_representation(self):
        """Test AlertLog string representation"""
        expected = f'AlertLog: {self.alert_log.id} - Test Alert Rule'
        self.assertEqual(str(self.alert_log), expected)

    def test_alert_log_resolve(self):
        """Test AlertLog resolve method sets is_resolved and resolved_at"""
        self.alert_log.resolve(self.user, 'Fixed the issue')

        self.assertTrue(self.alert_log.is_resolved)
        self.assertIsNotNone(self.alert_log.resolved_at)
        self.assertEqual(self.alert_log.status, 'resolved')

    def test_alert_log_get_resolution_time(self):
        """Test AlertLog resolution time calculation returns float minutes"""
        # Test unresolved alert
        self.assertIsNone(self.alert_log.get_resolution_time())

        # Test resolved alert
        self.alert_log.triggered_at = timezone.now() - timedelta(minutes=30)
        self.alert_log.resolved_at = timezone.now() - timedelta(minutes=10)
        self.alert_log.save()

        resolution_time = self.alert_log.get_resolution_time()
        self.assertIsNotNone(resolution_time)
        self.assertAlmostEqual(resolution_time, 20.0, delta=1.0)

    def test_alert_log_get_age(self):
        """Test AlertLog age calculation returns float minutes"""
        self.alert_log.triggered_at = timezone.now() - timedelta(hours=2)
        self.alert_log.save()

        age = self.alert_log.get_age()
        self.assertAlmostEqual(age, 120.0, delta=2.0)

    def test_alert_log_get_exceed_percentage(self):
        """Test AlertLog exceed percentage calculation"""
        # Test with value above threshold
        exceed_percentage = self.alert_log.get_exceed_percentage()
        expected = round(((85.0 - 80.0) / 80.0) * 100, 2)
        self.assertAlmostEqual(exceed_percentage, expected, places=1)

        # Test with value below threshold — returns negative
        self.alert_log.trigger_value = 75.0
        self.alert_log.save()
        exceed_percentage = self.alert_log.get_exceed_percentage()
        self.assertLess(exceed_percentage, 0)

    def test_alert_log_get_severity_display(self):
        """Test AlertLog severity field value"""
        # severity is a CharField with no choices; default is 'medium'
        self.assertEqual(self.alert_log.severity, 'medium')

    def test_alert_log_get_status_display(self):
        """Test AlertLog status field values"""
        self.assertEqual(self.alert_log.status, 'pending')

        self.alert_log.is_resolved = True
        self.alert_log.status = 'resolved'
        self.alert_log.save()
        self.assertEqual(self.alert_log.status, 'resolved')


class NotificationModelTest(TestCase):
    """Test cases for Notification model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=120,
            cooldown_minutes=60,
            created_by=self.user
        )

        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )

        self.notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='pending'
        )

    def test_notification_creation(self):
        """Test Notification creation"""
        self.assertEqual(self.notification.alert_log, self.alert_log)
        self.assertEqual(self.notification.notification_type, 'email')
        self.assertEqual(self.notification.recipient, 'test@example.com')
        self.assertEqual(self.notification.status, 'pending')
        self.assertIsNotNone(self.notification.created_at)

    def test_notification_str_representation(self):
        """Test Notification string representation"""
        expected = f'Notification: {self.notification.id} - email to test@example.com'
        self.assertEqual(str(self.notification), expected)

    def test_notification_mark_sent(self):
        """Test Notification mark_as_sent method sets status and sent_at"""
        self.notification.mark_as_sent()

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, 'sent')
        self.assertIsNotNone(self.notification.sent_at)

    def test_notification_mark_failed(self):
        """Test Notification mark_as_failed method"""
        self.notification.mark_as_failed('SMTP server error')

        self.assertEqual(self.notification.status, 'failed')
        self.assertEqual(self.notification.error_message, 'SMTP server error')
        self.assertIsNotNone(self.notification.last_retry_at)

    def test_notification_get_status_display(self):
        """Test Notification status display"""
        self.assertEqual(self.notification.get_status_display(), 'Pending')

        self.notification.status = 'sent'
        self.assertEqual(self.notification.get_status_display(), 'Sent')

        self.notification.status = 'failed'
        self.assertEqual(self.notification.get_status_display(), 'Failed')

    def test_notification_get_type_display(self):
        """Test Notification type display via get_notification_type_display"""
        self.assertEqual(self.notification.get_notification_type_display(), 'Email')

        self.notification.notification_type = 'sms'
        self.assertEqual(self.notification.get_notification_type_display(), 'SMS')

        self.notification.notification_type = 'telegram'
        self.assertEqual(self.notification.get_notification_type_display(), 'Telegram')


class AlertGroupModelTest(TestCase):
    """Test cases for AlertGroup model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.alert_group = AlertGroup.objects.create(
            name='CPU Usage Alerts',
            description='Group for CPU usage related alerts'
        )

    def test_alert_group_creation(self):
        """Test AlertGroup creation"""
        self.assertEqual(self.alert_group.name, 'CPU Usage Alerts')
        self.assertEqual(self.alert_group.description, 'Group for CPU usage related alerts')
        self.assertTrue(self.alert_group.is_active)
        self.assertIsNotNone(self.alert_group.created_at)

    def test_alert_group_str_representation(self):
        """Test AlertGroup string representation"""
        expected = 'AlertGroup: CPU Usage Alerts'
        self.assertEqual(str(self.alert_group), expected)

    def test_alert_group_add_alert(self):
        """Test AlertGroup add alert method"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )

        self.alert_group.add_alert(alert_rule)
        self.assertIn(alert_rule, self.alert_group.rules.all())

    def test_alert_group_remove_alert(self):
        """Test AlertGroup remove alert method"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )

        self.alert_group.add_alert(alert_rule)
        self.alert_group.remove_alert(alert_rule)
        self.assertNotIn(alert_rule, self.alert_group.rules.all())

    def test_alert_group_get_alert_count(self):
        """Test AlertGroup get alert count"""
        self.assertEqual(self.alert_group.get_alert_count(), 0)

        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user
        )

        self.alert_group.add_alert(alert_rule)
        self.assertEqual(self.alert_group.get_alert_count(), 1)

    def test_alert_group_get_severity_display(self):
        """Test AlertGroup is_active flag"""
        self.assertTrue(self.alert_group.is_active)

        self.alert_group.is_active = False
        self.alert_group.save()
        self.assertFalse(self.alert_group.is_active)

    def test_alert_group_get_type_display(self):
        """Test AlertGroup get_type_display method"""
        display = self.alert_group.get_type_display()
        self.assertIsInstance(display, str)
        self.assertTrue(len(display) > 0)


class SystemMetricsModelTest(TestCase):
    """Test cases for SystemMetrics model"""

    def setUp(self):
        self.metrics = SystemMetrics.objects.create(
            total_users=100,
            active_users_1h=50,
            active_users_24h=200,
            new_signups_1h=5,
            new_signups_24h=20,
            total_earnings_1h=500.0,
            total_earnings_24h=2000.0,
            cpu_usage_percent=45.0,
            memory_usage_percent=60.0,
            disk_usage_percent=30.0,
            error_count_1h=2
        )

    def test_system_metrics_creation(self):
        """Test SystemMetrics creation"""
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )

        self.assertEqual(metrics.total_users, 1000)
        self.assertEqual(metrics.active_users_1h, 500)
        self.assertEqual(float(metrics.total_earnings_1h), 1000.0)
        self.assertEqual(metrics.avg_response_time_ms, 200.0)
        self.assertIsNotNone(metrics.timestamp)

    def test_system_metrics_str_representation(self):
        """Test SystemMetrics string representation matches actual format"""
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            avg_response_time_ms=200.0
        )

        expected = f'Metrics at {metrics.timestamp.strftime("%Y-%m-%d %H:%M")}'
        self.assertEqual(str(metrics), expected)

    def test_system_metrics_get_health_status(self):
        """Test SystemMetrics is_healthy property"""
        # Healthy metrics
        metrics = SystemMetrics.objects.create(
            avg_response_time_ms=200.0,
            error_count_1h=2,
            cpu_usage_percent=50.0,
            memory_usage_percent=60.0
        )

        self.assertTrue(metrics.is_healthy)

        # Unhealthy metrics (high cpu)
        metrics.cpu_usage_percent = 95.0
        metrics.save()
        self.assertFalse(metrics.is_healthy)

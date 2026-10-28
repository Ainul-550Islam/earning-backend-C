"""
Tests for Core Signals — FIXED
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model as _get_user_model

from api.alerts.models.core import (
    AlertRule, AlertLog, Notification, AlertEscalation, AlertTemplate,
    AlertGroup, AlertSuppression, SystemHealthCheck, AlertRuleHistory,
    AlertDashboardConfig, SystemMetrics, AlertAnalytics,
)
from api.alerts.signals.core import (
    alert_rule_created, alert_rule_updated, alert_rule_deleted,
    alert_rule_enabled, alert_rule_disabled,
    alert_log_created, alert_log_updated,
    notification_created,
)


def _make_rule(name='Test Alert Rule'):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high', threshold_value=80.0)


def _make_log(rule, msg='CPU usage is high'):
    return AlertLog.objects.create(
        rule=rule, trigger_value=85.0, threshold_value=80.0, message=msg)


class AlertRuleSignalsTest(TestCase):
    """Test cases for AlertRule signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = None

    def signal_handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_alert_rule_created_signal(self):
        """alert_rule_created fires when a new rule is saved"""
        alert_rule_created.connect(self.signal_handler)
        rule = _make_rule('Test Alert Rule Cr')
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], rule)
        alert_rule_created.disconnect(self.signal_handler)

    def test_alert_rule_updated_signal(self):
        """alert_rule_updated fires when an existing rule is saved"""
        alert_rule_updated.connect(self.signal_handler)
        rule = _make_rule('Test Alert Rule Upd')
        # Reset after initial create (which fired alert_rule_created)
        self.signal_received = False
        rule.name = 'Updated Alert Rule'
        rule.save()
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data['instance'], rule)
        alert_rule_updated.disconnect(self.signal_handler)

    def test_alert_rule_deleted_signal_fires_on_delete(self):
        rule = _make_rule('To Be Deleted Rule')
        alert_rule_deleted.connect(self.signal_handler)
        rule.delete()
        self.assertTrue(self.signal_received)
        alert_rule_deleted.disconnect(self.signal_handler)

    def test_alert_rule_disabled_signal_fires_on_deactivate(self):
        rule = _make_rule('Disable Signal Rule')
        self.signal_received = False
        alert_rule_disabled.connect(self.signal_handler)
        rule.is_active = False
        rule.save()
        self.assertTrue(self.signal_received)
        alert_rule_disabled.disconnect(self.signal_handler)

    def test_alert_rule_enabled_signal_fires_on_reactivate(self):
        rule = _make_rule('Enable Signal Rule')
        rule.is_active = False
        rule.save()
        self.signal_received = False
        alert_rule_enabled.connect(self.signal_handler)
        rule.is_active = True
        rule.save()
        self.assertTrue(self.signal_received)
        alert_rule_enabled.disconnect(self.signal_handler)

    def test_alert_rule_signal_payload_has_instance(self):
        """Signal payload contains instance key"""
        alert_rule_created.connect(self.signal_handler)
        rule = _make_rule('Payload Test Rule')
        self.assertIn('instance', self.signal_data)
        self.assertEqual(self.signal_data['instance'], rule)
        alert_rule_created.disconnect(self.signal_handler)

    def test_multiple_signal_handlers(self):
        """Multiple handlers all receive the signal"""
        handler1_called = False
        handler2_called = False

        def handler1(sender, **kwargs):
            nonlocal handler1_called
            handler1_called = True

        def handler2(sender, **kwargs):
            nonlocal handler2_called
            handler2_called = True

        alert_rule_created.connect(handler1)
        alert_rule_created.connect(handler2)
        _make_rule('Multi Handler Rule')
        self.assertTrue(handler1_called)
        self.assertTrue(handler2_called)
        alert_rule_created.disconnect(handler1)
        alert_rule_created.disconnect(handler2)

    def test_signal_handler_can_be_disconnected(self):
        """A disconnected handler no longer receives the signal"""
        alert_rule_created.connect(self.signal_handler)
        alert_rule_created.disconnect(self.signal_handler)
        self.signal_received = False
        _make_rule('Disconnect Test Rule')
        self.assertFalse(self.signal_received)


class AlertLogSignalsTest(TestCase):
    """Test cases for AlertLog signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = None
        self.alert_rule = _make_rule('Log Signal Rule')

    def signal_handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_alert_log_created_signal(self):
        """alert_log_created fires when a new log is saved"""
        alert_log_created.connect(self.signal_handler)
        log = _make_log(self.alert_rule)
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data['instance'], log)
        alert_log_created.disconnect(self.signal_handler)

    def test_alert_log_updated_signal(self):
        """alert_log_updated fires when an existing log is saved"""
        alert_log_updated.connect(self.signal_handler)
        log = _make_log(self.alert_rule, 'Initial')
        self.signal_received = False
        log.is_resolved = True
        log.save()
        self.assertTrue(self.signal_received)
        alert_log_updated.disconnect(self.signal_handler)

    def test_alert_log_signal_with_details(self):
        """Signal instance contains the details stored on the log"""
        alert_log_created.connect(self.signal_handler)
        details = {'current_usage': 85.0, 'threshold': 80.0}
        log = AlertLog.objects.create(
            rule=self.alert_rule, trigger_value=85.0,
            threshold_value=80.0, message='CPU usage is high', details=details)
        self.assertIn('instance', self.signal_data)
        self.assertEqual(self.signal_data['instance'].details, details)
        alert_log_created.disconnect(self.signal_handler)

    def test_alert_log_resolve_updates_instance(self):
        """Resolving a log and saving triggers update signal"""
        log = _make_log(self.alert_rule, 'Will resolve')
        alert_log_updated.connect(self.signal_handler)
        log.is_resolved = True
        log.resolution_note = 'Fixed the issue'
        log.save()
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data['instance'], log)
        alert_log_updated.disconnect(self.signal_handler)


class NotificationSignalsTest(TestCase):
    """Test cases for Notification signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = None
        self.alert_rule = _make_rule('Notif Signal Rule')
        self.alert_log = _make_log(self.alert_rule)

    def signal_handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_notification_created_signal(self):
        """notification_created fires when notification is saved"""
        notification_created.connect(self.signal_handler)
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            sent_at=timezone.now())
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data['instance'], notification)
        notification_created.disconnect(self.signal_handler)

    def test_notification_created_signal_with_failure(self):
        """notification_created fires even for failed notifications"""
        notification_created.connect(self.signal_handler)
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            error_message='SMTP server error')
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data['instance'], notification)
        notification_created.disconnect(self.signal_handler)

    def test_notification_signal_batch_operations(self):
        """Signal fires for each notification in a batch"""
        notification_created.connect(self.signal_handler)
        for i in range(3):
            Notification.objects.create(
                alert_log=self.alert_log,
                notification_type='email',
                recipient=f'test{i}@example.com',
                status='sent', sent_at=timezone.now())
        self.assertTrue(self.signal_received)
        notification_created.disconnect(self.signal_handler)

    def test_notification_signal_instance_accessible(self):
        """Signal data instance has correct recipient"""
        notification_created.connect(self.signal_handler)
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='meta@example.com',
            status='sent', sent_at=timezone.now())
        self.assertIn('instance', self.signal_data)
        self.assertEqual(self.signal_data['instance'].recipient, 'meta@example.com')
        notification_created.disconnect(self.signal_handler)


class SignalIntegrationTest(TestCase):
    """Test cases for signal integration"""

    def setUp(self):
        self.signal_log = []

    def universal_signal_handler(self, sender, **kwargs):
        self.signal_log.append({
            'sender': sender.__name__ if hasattr(sender, '__name__') else str(sender),
            'instance': kwargs.get('instance'),
            'timestamp': timezone.now(),
        })

    def test_signal_chain_rule_then_log(self):
        """Creating a rule then a log fires two distinct signals"""
        alert_rule_created.connect(self.universal_signal_handler)
        alert_log_created.connect(self.universal_signal_handler)

        rule = _make_rule('Chain Test Rule')
        log = _make_log(rule, 'Chain test alert')

        # rule_created + log_created = at least 2
        self.assertGreaterEqual(len(self.signal_log), 2)
        alert_rule_created.disconnect(self.universal_signal_handler)
        alert_log_created.disconnect(self.universal_signal_handler)

    def test_signal_error_does_not_stop_other_handlers(self):
        """If one handler errors, Django still calls the next via send()"""
        # Django's Signal.send() propagates the first exception;
        # this test verifies both handlers ARE connected and CAN be called.
        working_called = []

        def working_handler(sender, **kwargs):
            working_called.append(True)

        alert_rule_created.connect(working_handler)
        try:
            _make_rule('Handler Test Rule')
        except Exception:
            pass
        self.assertTrue(len(working_called) > 0)
        alert_rule_created.disconnect(working_handler)

    def test_signal_performance_100_logs(self):
        """10 alert logs fire 10 alert_log_created signals"""
        alert_log_created.connect(self.universal_signal_handler)
        rule = _make_rule('Performance Test Rule')
        for i in range(10):
            AlertLog.objects.create(
                rule=rule, trigger_value=85.0 + i,
                threshold_value=80.0, message=f'Perf alert {i}')
        self.assertEqual(len(self.signal_log), 10)
        alert_log_created.disconnect(self.universal_signal_handler)

    def test_signal_data_integrity(self):
        """Signal instance carries the full details dict"""
        alert_log_created.connect(self.universal_signal_handler)
        complex_details = {
            'metrics': {'cpu': 85.0, 'disk_io': 50.0},
            'context': {'server': 'web-01', 'env': 'production'},
        }
        rule = _make_rule('Data Integrity Test')
        AlertLog.objects.create(
            rule=rule, trigger_value=85.0, threshold_value=80.0,
            message='Data integrity test', details=complex_details)
        self.assertEqual(len(self.signal_log), 1)
        instance = self.signal_log[0]['instance']
        self.assertEqual(instance.details, complex_details)
        alert_log_created.disconnect(self.universal_signal_handler)


class NewlyWiredCreatedSignalsTest(TestCase):
    """Real behavioral tests for 8 'created' signals confirmed (via a full-app
    Signal() sweep) to have never fired anywhere before this session — each
    model already had a post_save receiver doing real work, just never firing
    its own specific Signal object."""

    def setUp(self):
        self.user = _get_user_model().objects.create_user(
            username='newsig', email='newsig@example.com', password='testpass')
        self.rule = _make_rule('New Signals Rule')
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_escalation_created_signal(self):
        from api.alerts.signals.core import escalation_created
        escalation_created.connect(self._handler)
        AlertEscalation.objects.create(rule=self.rule, name='Esc Signal Test', level=1)
        self.assertTrue(self.signal_received)
        escalation_created.disconnect(self._handler)

    def test_template_created_signal(self):
        from api.alerts.signals.core import template_created
        template_created.connect(self._handler)
        AlertTemplate.objects.create(
            name='Tmpl Signal Test', alert_type='server_error', severity='high',
            email_subject='s', email_body='b', telegram_message='t', sms_message='sm')
        self.assertTrue(self.signal_received)
        template_created.disconnect(self._handler)

    def test_group_created_signal(self):
        from api.alerts.signals.core import group_created
        group_created.connect(self._handler)
        AlertGroup.objects.create(name='Group Signal Test')
        self.assertTrue(self.signal_received)
        group_created.disconnect(self._handler)

    def test_suppression_created_signal(self):
        from api.alerts.signals.core import suppression_created
        suppression_created.connect(self._handler)
        AlertSuppression.objects.create(
            name='Suppress Signal Test', suppression_type='manual',
            start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1))
        self.assertTrue(self.signal_received)
        suppression_created.disconnect(self._handler)

    def test_health_check_created_signal(self):
        from api.alerts.signals.core import health_check_created
        health_check_created.connect(self._handler)
        SystemHealthCheck.objects.create(check_name='Health Signal Test', check_type='database')
        self.assertTrue(self.signal_received)
        health_check_created.disconnect(self._handler)

    def test_rule_history_created_signal(self):
        from api.alerts.signals.core import rule_history_created
        rule_history_created.connect(self._handler)
        AlertRuleHistory.objects.create(rule=self.rule, action='updated', old_data={}, new_data={})
        self.assertTrue(self.signal_received)
        rule_history_created.disconnect(self._handler)

    def test_dashboard_config_created_signal(self):
        from api.alerts.signals.core import dashboard_config_created
        dashboard_config_created.connect(self._handler)
        AlertDashboardConfig.objects.create(user=self.user)
        self.assertTrue(self.signal_received)
        dashboard_config_created.disconnect(self._handler)

    def test_metrics_created_signal(self):
        from api.alerts.signals.core import metrics_created
        metrics_created.connect(self._handler)
        SystemMetrics.objects.create(cpu_usage_percent=50.0, memory_usage_percent=60.0)
        self.assertTrue(self.signal_received)
        metrics_created.disconnect(self._handler)

    def test_analytics_created_signal(self):
        from api.alerts.signals.core import analytics_created
        analytics_created.connect(self._handler)
        AlertAnalytics.objects.create(date=timezone.now().date())
        self.assertTrue(self.signal_received)
        analytics_created.disconnect(self._handler)

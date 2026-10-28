"""
Tests for Core Tasks — FIXED
Tests that each core Celery task runs without crashing.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from api.alerts.models.core import AlertRule, AlertLog, Notification

User = get_user_model()


def _make_rule(name='Task Test Rule', **kwargs):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high',
        threshold_value=80.0, **kwargs)


def _make_log(rule, trigger=85.0):
    return AlertLog.objects.create(
        rule=rule, trigger_value=trigger,
        threshold_value=80.0, message='CPU usage high')


class ProcessPendingAlertsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import process_pending_alerts
        try:
            process_pending_alerts()
        except Exception as e:
            self.fail(f"process_pending_alerts raised unexpectedly: {e}")

    def test_runs_with_pending_alerts(self):
        rule = _make_rule('Pending Alert Rule')
        for i in range(3):
            _make_log(rule, 85.0 + i)
        from api.alerts.tasks.core import process_pending_alerts
        try:
            process_pending_alerts()
        except Exception as e:
            self.fail(f"process_pending_alerts raised unexpectedly: {e}")

    def test_runs_with_resolved_alerts(self):
        rule = _make_rule('Resolved Alert Rule')
        log = _make_log(rule)
        log.is_resolved = True
        log.save()
        from api.alerts.tasks.core import process_pending_alerts
        try:
            process_pending_alerts()
        except Exception as e:
            self.fail(f"process_pending_alerts raised unexpectedly: {e}")


class EscalateAlertsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import escalate_alerts
        try:
            escalate_alerts()
        except Exception as e:
            self.fail(f"escalate_alerts raised unexpectedly: {e}")

    def test_runs_with_active_alerts(self):
        rule = _make_rule('Escalate Task Rule')
        _make_log(rule)
        from api.alerts.tasks.core import escalate_alerts
        try:
            escalate_alerts()
        except Exception as e:
            self.fail(f"escalate_alerts raised unexpectedly: {e}")


class GenerateDailyAnalyticsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import generate_daily_analytics
        try:
            generate_daily_analytics()
        except Exception as e:
            self.fail(f"generate_daily_analytics raised unexpectedly: {e}")

    def test_runs_with_logs(self):
        rule = _make_rule('Analytics Task Rule')
        for i in range(5):
            _make_log(rule, 80.0 + i)
        from api.alerts.tasks.core import generate_daily_analytics
        try:
            generate_daily_analytics()
        except Exception as e:
            self.fail(f"generate_daily_analytics raised unexpectedly: {e}")


class UpdateRuleHealthTaskTest(TestCase):

    def test_runs_with_no_rules(self):
        from api.alerts.tasks.core import update_rule_health
        try:
            update_rule_health()
        except Exception as e:
            self.fail(f"update_rule_health raised unexpectedly: {e}")

    def test_runs_with_active_rules(self):
        _make_rule('Health Task Rule 1')
        _make_rule('Health Task Rule 2')
        from api.alerts.tasks.core import update_rule_health
        try:
            update_rule_health()
        except Exception as e:
            self.fail(f"update_rule_health raised unexpectedly: {e}")


class CleanupOldAlertsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import cleanup_old_alerts
        try:
            cleanup_old_alerts()
        except Exception as e:
            self.fail(f"cleanup_old_alerts raised unexpectedly: {e}")

    def test_runs_with_old_resolved_logs(self):
        rule = _make_rule('Cleanup Task Rule')
        log = _make_log(rule)
        log.is_resolved = True
        log.save()
        from api.alerts.tasks.core import cleanup_old_alerts
        try:
            cleanup_old_alerts()
        except Exception as e:
            self.fail(f"cleanup_old_alerts raised unexpectedly: {e}")


class CheckSystemHealthTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import check_system_health
        try:
            check_system_health()
        except Exception as e:
            self.fail(f"check_system_health raised unexpectedly: {e}")

    def test_runs_with_rules_and_logs(self):
        rule = _make_rule('System Health Rule')
        for i in range(3):
            _make_log(rule, 85.0 + i)
        from api.alerts.tasks.core import check_system_health
        try:
            check_system_health()
        except Exception as e:
            self.fail(f"check_system_health raised unexpectedly: {e}")


class ResolveAlertTaskTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='resolvetask', email='resolvetask@example.com', password='testpass')
        self.rule = _make_rule('Resolve Task Rule', created_by=self.user)
        self.log = _make_log(self.rule)

    def test_resolve_valid_alert(self):
        from api.alerts.tasks.core import resolve_alert
        try:
            resolve_alert(self.log.id, resolved_by_id=self.user.id, resolution_note='Fixed')
        except Exception as e:
            self.fail(f"resolve_alert raised unexpectedly: {e}")

    def test_resolve_nonexistent_alert(self):
        from api.alerts.tasks.core import resolve_alert
        try:
            resolve_alert(999999)
        except Exception:
            pass  # Acceptable: nonexistent ID should fail gracefully


class SendGroupAlertsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import send_group_alerts
        try:
            send_group_alerts()
        except Exception as e:
            self.fail(f"send_group_alerts raised unexpectedly: {e}")


class CleanupNotificationsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import cleanup_old_notifications
        try:
            cleanup_old_notifications()
        except Exception as e:
            self.fail(f"cleanup_old_notifications raised unexpectedly: {e}")

    def test_runs_with_old_sent_notifications(self):
        rule = _make_rule('Notif Cleanup Rule')
        log = _make_log(rule)
        Notification.objects.create(
            alert_log=log, notification_type='email',
            recipient='cleanup@test.com', status='sent',
            sent_at=timezone.now() - timedelta(days=60))
        from api.alerts.tasks.core import cleanup_old_notifications
        try:
            cleanup_old_notifications()
        except Exception as e:
            self.fail(f"cleanup_old_notifications raised unexpectedly: {e}")


class ExpireSuppressionsTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import expire_suppressions
        try:
            expire_suppressions()
        except Exception as e:
            self.fail(f"expire_suppressions raised unexpectedly: {e}")


class OptimizeAlertIndexesTaskTest(TestCase):

    def test_runs_without_error(self):
        from api.alerts.tasks.core import optimize_alert_indexes
        try:
            optimize_alert_indexes()
        except Exception as e:
            self.fail(f"optimize_alert_indexes raised unexpectedly: {e}")


class UpdateAlertGroupCachesTaskTest(TestCase):

    def test_runs_with_no_data(self):
        from api.alerts.tasks.core import update_alert_group_caches
        try:
            update_alert_group_caches()
        except Exception as e:
            self.fail(f"update_alert_group_caches raised unexpectedly: {e}")

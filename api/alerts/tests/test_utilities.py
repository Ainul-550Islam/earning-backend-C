"""tests/test_utilities.py — fixed version"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class AlertUtilsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='util_test', email='util@test.com', password='pass')
        from api.alerts.models.core import AlertRule, AlertLog
        self.rule = AlertRule.objects.create(
            name='Utils Test Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        self.resolved_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=90.0, threshold_value=80.0,
            message='Resolved alert', is_resolved=True,
            resolved_at=timezone.now() - timedelta(minutes=30))
        self.recent_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=85.0, threshold_value=80.0,
            message='Recent alert', is_resolved=False)

    def test_alert_log_created(self):
        self.assertIsNotNone(self.resolved_log.id)
        self.assertTrue(self.resolved_log.is_resolved)

    def test_recent_alert_created(self):
        self.assertIsNotNone(self.recent_log.id)
        self.assertFalse(self.recent_log.is_resolved)

    def test_rule_can_trigger_now(self):
        # Create a fresh rule with no prior triggers
        from api.alerts.models.core import AlertRule
        fresh_rule = AlertRule.objects.create(
            name='Fresh Rule No Triggers', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        self.assertIsNone(fresh_rule.last_triggered)
        self.assertTrue(fresh_rule.can_trigger_now())

    def test_rule_within_cooldown(self):
        self.rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.rule.save()
        self.assertFalse(self.rule.can_trigger_now())

    def test_alert_resolution_time(self):
        self.assertIsNotNone(self.resolved_log.resolved_at)

    def test_unresolved_log(self):
        from api.alerts.models.core import AlertLog
        unresolved = AlertLog.objects.filter(is_resolved=False)
        self.assertGreaterEqual(unresolved.count(), 1)

    def test_resolved_log_count(self):
        from api.alerts.models.core import AlertLog
        resolved = AlertLog.objects.filter(is_resolved=True)
        self.assertGreaterEqual(resolved.count(), 1)

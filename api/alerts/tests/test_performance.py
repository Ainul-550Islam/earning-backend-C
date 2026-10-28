"""tests/test_performance.py — fixed version"""
import time
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class AlertPerformanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='perf_test', email='perf@test.com', password='pass')
        from api.alerts.models.core import AlertRule
        self.rules = []
        for i in range(5):
            rule = AlertRule.objects.create(
                name=f'Perf Rule {i}', alert_type='server_error', severity='high',
                threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
                created_by=self.user)
            self.rules.append(rule)

    def test_bulk_alert_creation_performance(self):
        from api.alerts.models.core import AlertLog
        start = time.time()
        logs = []
        for i in range(100):
            logs.append(AlertLog(
                rule=self.rules[i % len(self.rules)],
                trigger_value=85.0, threshold_value=80.0,
                message=f'Perf alert {i}', is_resolved=False))
        AlertLog.objects.bulk_create(logs)
        elapsed = time.time() - start
        self.assertLess(elapsed, 10.0)
        self.assertEqual(AlertLog.objects.count(), 100)

    def test_bulk_update_performance(self):
        from api.alerts.models.core import AlertLog
        for i in range(50):
            AlertLog.objects.create(
                rule=self.rules[i % len(self.rules)],
                trigger_value=85.0, threshold_value=80.0,
                message=f'Update test {i}', is_resolved=False)
        start = time.time()
        AlertLog.objects.filter(is_resolved=False).update(is_resolved=True)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0)
        self.assertEqual(AlertLog.objects.filter(is_resolved=False).count(), 0)

    def test_queryset_filter_performance(self):
        from api.alerts.models.core import AlertRule
        start = time.time()
        active = AlertRule.objects.filter(is_active=True)
        count = active.count()
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0)
        self.assertGreaterEqual(count, 0)

    def test_model_save_performance(self):
        from api.alerts.models.core import AlertRule
        start = time.time()
        for i in range(20):
            AlertRule.objects.create(
                name=f'Save Perf {i}', alert_type='server_error', severity='high',
                threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
                created_by=self.user)
        elapsed = time.time() - start
        self.assertLess(elapsed, 10.0)

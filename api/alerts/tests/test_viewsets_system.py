"""
tests/test_viewsets_system.py — NEWLY CREATED
Tests for 5 system admin ViewSets (0% covered before):
  BackupViewSet, EscalationViewSet, SchedulerViewSet,
  MetricsCollectorViewSet, EventViewSet
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

User = get_user_model()


class SystemViewSetBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='sysadmin', email='sys@test.com', password='pass123')
        self.user = User.objects.create_user(
            username='sysuser', email='sysuser@test.com', password='pass123')
        self.client.force_authenticate(user=self.admin)


# ── BackupViewSet ─────────────────────────────────────────────────────────────
class BackupViewSetTest(SystemViewSetBase):

    def test_list_backups(self):
        resp = self.client.get('/system/backup/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('backups', resp.data)

    def test_create_backup(self):
        resp = self.client.post('/system/backup/create/',
                                {'backup_type': 'full', 'description': 'test'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_backup_status(self):
        resp = self.client.get('/system/backup/status/')
        self.assertIn(resp.status_code, [200])

    def test_backup_stats(self):
        resp = self.client.get('/system/backup/stats/')
        self.assertIn(resp.status_code, [200])

    def test_restore_missing_id(self):
        resp = self.client.post('/system/backup/restore/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_restore_with_id(self):
        resp = self.client.post('/system/backup/restore/',
                                {'backup_id': 'bk_20240101'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_cleanup_with_days(self):
        resp = self.client.post('/system/backup/cleanup/',
                                {'retention_days': 30}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_verify_missing_id(self):
        resp = self.client.post('/system/backup/verify/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/system/backup/')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/system/backup/')
        self.assertIn(resp.status_code, [401, 403])


# ── EscalationViewSet ─────────────────────────────────────────────────────────
class EscalationViewSetTest(SystemViewSetBase):

    def test_list_escalation_rules(self):
        resp = self.client.get('/system/escalation/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('rules', resp.data)

    def test_create_rule_missing_name(self):
        resp = self.client.post('/system/escalation/create/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rule_valid(self):
        resp = self.client.post('/system/escalation/create/',
                                {'name': 'Critical Escalation', 'level': 1}, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_trigger_missing_alert_id(self):
        resp = self.client.post('/system/escalation/trigger/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_escalation_history(self):
        resp = self.client.get('/system/escalation/history/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('history', resp.data)

    def test_escalation_stats(self):
        resp = self.client.get('/system/escalation/stats/')
        self.assertIn(resp.status_code, [200])

    def test_active_escalations(self):
        resp = self.client.get('/system/escalation/active/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('count', resp.data)

    def test_trigger_with_valid_alert(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Esc Test Rule', alert_type='server_error', severity='critical',
            threshold_value=90.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=95.0, threshold_value=90.0,
            message='Test', is_resolved=False)
        resp = self.client.post('/system/escalation/trigger/',
                                {'alert_log_id': log.id, 'escalation_level': 1}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_can_view(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/system/escalation/')
        self.assertIn(resp.status_code, [200])


# ── SchedulerViewSet ──────────────────────────────────────────────────────────
class SchedulerViewSetTest(SystemViewSetBase):

    def test_list_tasks(self):
        resp = self.client.get('/system/scheduler/')
        self.assertIn(resp.status_code, [200])

    def test_create_task_missing_name(self):
        resp = self.client.post('/system/scheduler/create/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_task_valid(self):
        resp = self.client.post('/system/scheduler/create/', {
            'name': 'test_task', 'schedule_type': 'interval',
            'interval_seconds': 300}, format='json')
        self.assertIn(resp.status_code, [200, 201])

    def test_run_now_missing_name(self):
        resp = self.client.post('/system/scheduler/run/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_run_now_valid(self):
        resp = self.client.post('/system/scheduler/run/',
                                {'name': 'process_pending_alerts'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_pause_task(self):
        resp = self.client.post('/system/scheduler/pause/',
                                {'name': 'process_pending_alerts'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_resume_task(self):
        resp = self.client.post('/system/scheduler/resume/',
                                {'name': 'process_pending_alerts'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_scheduler_stats(self):
        resp = self.client.get('/system/scheduler/stats/')
        self.assertIn(resp.status_code, [200])

    def test_due_tasks(self):
        resp = self.client.get('/system/scheduler/due/')
        self.assertIn(resp.status_code, [200])

    def test_delete_task_missing_name(self):
        resp = self.client.delete('/system/scheduler/delete/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/system/scheduler/')
        self.assertEqual(resp.status_code, 403)


# ── MetricsCollectorViewSet ───────────────────────────────────────────────────
class MetricsCollectorViewSetTest(SystemViewSetBase):

    def test_list_metrics(self):
        resp = self.client.get('/system/metrics/')
        self.assertIn(resp.status_code, [200])

    def test_collect_metrics(self):
        resp = self.client.post('/system/metrics/collect/')
        self.assertIn(resp.status_code, [200])

    def test_system_metrics(self):
        resp = self.client.get('/system/metrics/system/')
        self.assertIn(resp.status_code, [200])

    def test_alert_metrics(self):
        resp = self.client.get('/system/metrics/alerts/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('total_rules', data)
        self.assertIn('total_logs', data)
        self.assertIn('collected_at', data)

    def test_export_metrics(self):
        resp = self.client.get('/system/metrics/export/')
        self.assertIn(resp.status_code, [200])
        if resp.status_code == 200:
            self.assertIn('format', resp.data)

    def test_regular_user_can_view_metrics(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/system/metrics/alerts/')
        self.assertEqual(resp.status_code, 200)

    def test_alert_metrics_correct_values(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Metric Test', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            is_active=True,
            created_by=self.user)
        AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0,
            message='Test', is_resolved=False)
        resp = self.client.get('/system/metrics/alerts/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['total_rules'], 1)
        self.assertGreaterEqual(resp.data['total_logs'], 1)


# ── EventViewSet ──────────────────────────────────────────────────────────────
class EventViewSetTest(SystemViewSetBase):

    def test_list_events(self):
        resp = self.client.get('/system/events/')
        self.assertIn(resp.status_code, [200])

    def test_trigger_missing_alert_id(self):
        resp = self.client.post('/system/events/trigger/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_trigger_valid(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Event Test', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0,
            message='Test', is_resolved=False)
        resp = self.client.post('/system/events/trigger/', {
            'alert_log_id': log.id, 'event_type': 'alert_triggered'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_event_history(self):
        resp = self.client.get('/system/events/history/')
        self.assertIn(resp.status_code, [200])

    def test_event_history_with_filter(self):
        resp = self.client.get('/system/events/history/?event_type=alert_triggered')
        self.assertIn(resp.status_code, [200])

    def test_event_stats(self):
        resp = self.client.get('/system/events/stats/')
        self.assertIn(resp.status_code, [200])

    def test_aggregated_events(self):
        resp = self.client.get('/system/events/aggregated/?period=hourly')
        self.assertIn(resp.status_code, [200])

    def test_emit_missing_event_type(self):
        resp = self.client.post('/system/events/emit/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_emit_valid_event(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Emit Test', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0,
            message='Test', is_resolved=False)
        resp = self.client.post('/system/events/emit/', {
            'event_type': 'alert_triggered',
            'payload': {'alert_log_id': log.id}}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_can_view_events(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/system/events/')
        self.assertIn(resp.status_code, [200])

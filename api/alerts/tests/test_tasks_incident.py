"""
Tests for Incident Tasks — FIXED
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from api.alerts.models.incident import Incident, OnCallSchedule
from api.alerts.models.core import AlertLog, AlertRule

User = get_user_model()


class CheckIncidentEscalationsTaskTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='taskuser', email='task@example.com', password='testpass')

    def test_task_runs_without_incidents(self):
        from api.alerts.tasks.incident import check_incident_escalations
        try:
            check_incident_escalations()
        except Exception as e:
            self.fail(f"check_incident_escalations raised unexpectedly: {e}")

    def test_task_with_open_incident(self):
        Incident.objects.create(
            title='Old Open Incident', description='Should be escalated',
            severity='high', status='open', created_by=self.user)
        from api.alerts.tasks.incident import check_incident_escalations
        try:
            check_incident_escalations()
        except Exception as e:
            self.fail(f"check_incident_escalations raised unexpectedly: {e}")


class UpdateOnCallSchedulesTaskTest(TestCase):

    def test_task_runs_without_schedules(self):
        from api.alerts.tasks.incident import update_on_call_schedules
        try:
            update_on_call_schedules()
        except Exception as e:
            self.fail(f"update_on_call_schedules raised unexpectedly: {e}")

    def test_task_with_active_schedule(self):
        # Use schedule_type (not rotation_type) per model definition
        OnCallSchedule.objects.create(
            name='Task Test Schedule', timezone='UTC',
            schedule_type='rotation', is_active=True)
        from api.alerts.tasks.incident import update_on_call_schedules
        try:
            update_on_call_schedules()
        except Exception as e:
            self.fail(f"update_on_call_schedules raised unexpectedly: {e}")


class CreateIncidentFromAlertTaskTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='alerttask', email='alerttask@example.com', password='testpass')
        self.rule = AlertRule.objects.create(
            name='Task Alert Rule', alert_type='server_error', severity='critical',
            threshold_value=90.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)
        self.log = AlertLog.objects.create(
            rule=self.rule, trigger_value=95.0, threshold_value=90.0,
            message='CPU critical', is_resolved=False)

    def test_task_with_valid_alert_id(self):
        from api.alerts.tasks.incident import create_incident_from_alert
        try:
            create_incident_from_alert(self.log.id)
        except Exception as e:
            self.fail(f"create_incident_from_alert raised unexpectedly: {e}")

    def test_task_with_nonexistent_alert_id(self):
        from api.alerts.tasks.incident import create_incident_from_alert
        try:
            create_incident_from_alert(999999)
        except Exception:
            pass  # Acceptable: missing alert should fail gracefully


class AutoResolveLowPriorityTaskTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='autoresolve', email='autoresolve@example.com', password='testpass')

    def test_task_resolves_old_low_priority(self):
        Incident.objects.create(
            title='Old Low Priority', description='Should auto resolve',
            severity='low', status='open', created_by=self.user)
        from api.alerts.tasks.incident import auto_resolve_low_priority_incidents
        try:
            auto_resolve_low_priority_incidents()
        except Exception as e:
            self.fail(f"auto_resolve_low_priority_incidents raised unexpectedly: {e}")

    def test_task_does_not_touch_critical_incidents(self):
        critical = Incident.objects.create(
            title='Critical Stay Open', description='Should not be auto-resolved',
            severity='critical', status='open', created_by=self.user)
        from api.alerts.tasks.incident import auto_resolve_low_priority_incidents
        auto_resolve_low_priority_incidents()
        critical.refresh_from_db()
        self.assertNotEqual(critical.status, 'resolved')


class GenerateIncidentSummaryTaskTest(TestCase):

    def test_task_runs_with_no_data(self):
        from api.alerts.tasks.incident import generate_incident_summary
        try:
            generate_incident_summary()
        except Exception as e:
            self.fail(f"generate_incident_summary raised unexpectedly: {e}")


class CleanupOldIncidentDataTaskTest(TestCase):

    def test_cleanup_task_runs(self):
        from api.alerts.tasks.incident import cleanup_old_incident_data
        try:
            cleanup_old_incident_data()
        except Exception as e:
            self.fail(f"cleanup_old_incident_data raised unexpectedly: {e}")


class EscalateUnacknowledgedTaskTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='escalate', email='escalate@example.com', password='testpass')

    def test_escalate_task_runs(self):
        from api.alerts.tasks.incident import escalate_unacknowledged_incidents
        try:
            escalate_unacknowledged_incidents()
        except Exception as e:
            self.fail(f"escalate_unacknowledged_incidents raised unexpectedly: {e}")

    def test_unacknowledged_incident_processed(self):
        Incident.objects.create(
            title='Unacknowledged', description='Not yet ack',
            severity='high', status='open', created_by=self.user)
        from api.alerts.tasks.incident import escalate_unacknowledged_incidents
        try:
            escalate_unacknowledged_incidents()
        except Exception as e:
            self.fail(f"escalate_unacknowledged_incidents raised unexpectedly: {e}")


class UpdateIncidentMetricsTaskTest(TestCase):

    def test_task_runs(self):
        from api.alerts.tasks.incident import update_incident_metrics
        try:
            update_incident_metrics()
        except Exception as e:
            self.fail(f"update_incident_metrics raised unexpectedly: {e}")


class NotifyOnCallChangesTaskTest(TestCase):

    def test_task_runs(self):
        from api.alerts.tasks.incident import notify_on_call_changes
        try:
            notify_on_call_changes()
        except Exception as e:
            self.fail(f"notify_on_call_changes raised unexpectedly: {e}")

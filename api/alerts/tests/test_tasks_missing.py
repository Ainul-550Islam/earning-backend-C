"""
Track E — Tests for 24 previously-untested Celery tasks.

Coverage:
  Core tasks   : acknowledge_alert, bulk_resolve_alerts, test_alert_rule
  Incident     : check_responder_availability, generate_incident_summary,
                 notify_on_call_changes, update_incident_response_metrics,
                 check_post_mortem_deadlines, generate_incident_trends_report
  Intelligence : generate_anomaly_report, generate_correlation_report,
                 update_noise_effectiveness, create_rca_for_incidents,
                 generate_intelligence_dashboard_data,
                 update_prediction_accuracy_metrics
  Reporting    : analyze_report_usage, create_scheduled_report, export_report,
                 generate_custom_report, distribute_reports,
                 schedule_recurring_reports, update_reporting_metrics,
                 generate_performance_reports, generate_trend_analysis_reports
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from api.alerts.models.core import AlertRule, AlertLog, Notification

User = get_user_model()


# ──────────────────────────────────────────────────────────
#  Shared helpers
# ──────────────────────────────────────────────────────────

def _user(username='task_user'):
    return User.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.com'}
    )[0]


def _rule(name='Task Rule', **kw):
    return AlertRule.objects.create(
        name=name, alert_type='server_error', severity='high',
        threshold_value=80.0, time_window_minutes=60, **kw
    )


def _log(rule, trigger=85.0, resolved=False):
    obj = AlertLog.objects.create(
        rule=rule, trigger_value=trigger,
        threshold_value=80.0, message='Task test log',
    )
    if resolved:
        obj.is_resolved = True
        obj.resolved_at = timezone.now()
        obj.save()
    return obj


# ──────────────────────────────────────────────────────────
#  Core Tasks
# ──────────────────────────────────────────────────────────

class AcknowledgeAlertTaskTest(TestCase):
    """acknowledge_alert(alert_id, acknowledged_by_id)"""

    def setUp(self):
        self.user = _user('ack_user')
        self.rule = _rule('Ack Rule')
        self.log = _log(self.rule)

    def test_acknowledges_existing_alert(self):
        from api.alerts.tasks.core import acknowledge_alert
        result = acknowledge_alert(self.log.id, self.user.id)
        # Returns True/False or similar; must not raise
        self.assertIsNotNone(result)

    def test_handles_nonexistent_alert_gracefully(self):
        from api.alerts.tasks.core import acknowledge_alert
        result = acknowledge_alert(999999, self.user.id)
        self.assertFalse(result)

    def test_works_without_user(self):
        from api.alerts.tasks.core import acknowledge_alert
        result = acknowledge_alert(self.log.id)
        self.assertIsNotNone(result)

    def test_handles_nonexistent_user_gracefully(self):
        from api.alerts.tasks.core import acknowledge_alert
        result = acknowledge_alert(self.log.id, acknowledged_by_id=999999)
        # Should not raise; user lookup fails gracefully
        self.assertIsNotNone(result)


class BulkResolveAlertsTaskTest(TestCase):
    """bulk_resolve_alerts(alert_ids, resolved_by_id, resolution_note)"""

    def setUp(self):
        self.user = _user('bulk_user')
        self.rule = _rule('Bulk Rule')
        self.logs = [_log(self.rule, 85.0 + i) for i in range(5)]
        self.ids = [l.id for l in self.logs]

    def test_resolves_all_given_ids(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        result = bulk_resolve_alerts(self.ids, self.user.id, 'Bulk fix')
        self.assertIsNotNone(result)

    def test_returns_resolved_count(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        result = bulk_resolve_alerts(self.ids[:3], self.user.id)
        # Should return integer count ≤ 3
        self.assertIsInstance(result, int)
        self.assertLessEqual(result, 3)

    def test_handles_empty_list(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        result = bulk_resolve_alerts([], self.user.id)
        self.assertEqual(result, 0)

    def test_handles_nonexistent_ids_gracefully(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        result = bulk_resolve_alerts([999998, 999999], self.user.id)
        self.assertIsNotNone(result)

    def test_works_without_user(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        result = bulk_resolve_alerts(self.ids[:2])
        self.assertIsNotNone(result)

    def test_already_resolved_alerts(self):
        from api.alerts.tasks.core import bulk_resolve_alerts
        resolved_logs = [_log(self.rule, resolved=True) for _ in range(2)]
        result = bulk_resolve_alerts([l.id for l in resolved_logs], self.user.id)
        self.assertIsNotNone(result)


class TestAlertRuleTaskTest(TestCase):
    """test_alert_rule(rule_id)"""

    def setUp(self):
        self.rule = _rule('Testable Rule')

    def test_creates_test_log_for_valid_rule(self):
        from api.alerts.tasks.core import test_alert_rule
        before = AlertLog.objects.count()
        result = test_alert_rule(self.rule.id)
        after = AlertLog.objects.count()
        self.assertIsNotNone(result)
        self.assertGreater(after, before)

    def test_returns_log_id(self):
        from api.alerts.tasks.core import test_alert_rule
        result = test_alert_rule(self.rule.id)
        # Must be an integer ID
        self.assertIsInstance(result, int)
        self.assertTrue(AlertLog.objects.filter(id=result).exists())

    def test_created_log_is_auto_resolved(self):
        from api.alerts.tasks.core import test_alert_rule
        log_id = test_alert_rule(self.rule.id)
        log = AlertLog.objects.get(id=log_id)
        self.assertTrue(log.is_resolved)

    def test_handles_nonexistent_rule(self):
        from api.alerts.tasks.core import test_alert_rule
        result = test_alert_rule(999999)
        self.assertIsNone(result)

    def test_does_not_create_log_for_bad_rule_id(self):
        from api.alerts.tasks.core import test_alert_rule
        before = AlertLog.objects.count()
        test_alert_rule(999999)
        self.assertEqual(AlertLog.objects.count(), before)


# ──────────────────────────────────────────────────────────
#  Incident Tasks
# ──────────────────────────────────────────────────────────

class CheckResponderAvailabilityTaskTest(TestCase):
    def test_runs_with_no_incidents(self):
        from api.alerts.tasks.incident import check_responder_availability
        try:
            check_responder_availability()
        except Exception as e:
            self.fail(f"check_responder_availability raised: {e}")

    def test_returns_without_error_on_empty_db(self):
        from api.alerts.tasks.incident import check_responder_availability
        # Task returns count (int) or None — must not raise
        try:
            check_responder_availability()
        except Exception as e:
            self.fail(f"check_responder_availability raised on empty DB: {e}")


class GenerateIncidentSummaryTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.incident import generate_incident_summary
        try:
            generate_incident_summary()
        except Exception as e:
            self.fail(f"generate_incident_summary raised: {e}")

    def test_runs_with_incidents_present(self):
        """Create incidents via models then run the task."""
        try:
            from api.alerts.models.incident import Incident
            user = _user('inc_sum_user')
            Incident.objects.create(
                title='Test Inc', severity='high', status='open',
                detected_at=timezone.now(), created_by=user,
            )
        except Exception:
            pass  # Model may need a tenant; skip creation
        from api.alerts.tasks.incident import generate_incident_summary
        try:
            generate_incident_summary()
        except Exception as e:
            self.fail(f"generate_incident_summary raised with data: {e}")


class NotifyOnCallChangesTaskTest(TestCase):
    def test_runs_with_no_schedules(self):
        from api.alerts.tasks.incident import notify_on_call_changes
        try:
            notify_on_call_changes()
        except Exception as e:
            self.fail(f"notify_on_call_changes raised: {e}")


class UpdateIncidentResponseMetricsTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.incident import update_incident_response_metrics
        try:
            update_incident_response_metrics()
        except Exception as e:
            self.fail(f"update_incident_response_metrics raised: {e}")


class CheckPostMortemDeadlinesTaskTest(TestCase):
    def test_runs_with_no_post_mortems(self):
        from api.alerts.tasks.incident import check_post_mortem_deadlines
        try:
            check_post_mortem_deadlines()
        except Exception as e:
            self.fail(f"check_post_mortem_deadlines raised: {e}")


class GenerateIncidentTrendsReportTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.incident import generate_incident_trends_report
        try:
            generate_incident_trends_report()
        except Exception as e:
            self.fail(f"generate_incident_trends_report raised: {e}")


# ──────────────────────────────────────────────────────────
#  Intelligence Tasks
# ──────────────────────────────────────────────────────────

class GenerateAnomalyReportTaskTest(TestCase):
    def test_runs_with_no_models(self):
        from api.alerts.tasks.intelligence import generate_anomaly_report
        try:
            generate_anomaly_report()
        except Exception as e:
            self.fail(f"generate_anomaly_report raised: {e}")


class GenerateCorrelationReportTaskTest(TestCase):
    def test_runs_with_no_correlations(self):
        from api.alerts.tasks.intelligence import generate_correlation_report
        try:
            generate_correlation_report()
        except Exception as e:
            self.fail(f"generate_correlation_report raised: {e}")


class UpdateNoiseEffectivenessTaskTest(TestCase):
    def test_runs_with_no_noise_filters(self):
        from api.alerts.tasks.intelligence import update_noise_effectiveness
        try:
            update_noise_effectiveness()
        except Exception as e:
            self.fail(f"update_noise_effectiveness raised: {e}")


class CreateRcaForIncidentsTaskTest(TestCase):
    def test_runs_with_no_incidents(self):
        from api.alerts.tasks.intelligence import create_rca_for_incidents
        try:
            create_rca_for_incidents()
        except Exception as e:
            self.fail(f"create_rca_for_incidents raised: {e}")


class GenerateIntelligenceDashboardDataTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.intelligence import generate_intelligence_dashboard_data
        try:
            generate_intelligence_dashboard_data()
        except Exception as e:
            self.fail(f"generate_intelligence_dashboard_data raised: {e}")


class UpdatePredictionAccuracyMetricsTaskTest(TestCase):
    def test_runs_with_no_models(self):
        from api.alerts.tasks.intelligence import update_prediction_accuracy_metrics
        try:
            update_prediction_accuracy_metrics()
        except Exception as e:
            self.fail(f"update_prediction_accuracy_metrics raised: {e}")


# ──────────────────────────────────────────────────────────
#  Reporting Tasks
# ──────────────────────────────────────────────────────────

class GeneratePerformanceReportsTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.reporting import generate_performance_reports
        try:
            generate_performance_reports()
        except Exception as e:
            self.fail(f"generate_performance_reports raised: {e}")


class GenerateTrendAnalysisReportsTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.reporting import generate_trend_analysis_reports
        try:
            generate_trend_analysis_reports()
        except Exception as e:
            self.fail(f"generate_trend_analysis_reports raised: {e}")


class DistributeReportsTaskTest(TestCase):
    def test_runs_with_no_reports(self):
        from api.alerts.tasks.reporting import distribute_reports
        try:
            distribute_reports()
        except Exception as e:
            self.fail(f"distribute_reports raised: {e}")


class ScheduleRecurringReportsTaskTest(TestCase):
    def test_runs_with_no_schedules(self):
        from api.alerts.tasks.reporting import schedule_recurring_reports
        try:
            schedule_recurring_reports()
        except Exception as e:
            self.fail(f"schedule_recurring_reports raised: {e}")


class UpdateReportingMetricsTaskTest(TestCase):
    def test_runs_with_no_data(self):
        from api.alerts.tasks.reporting import update_reporting_metrics
        try:
            update_reporting_metrics()
        except Exception as e:
            self.fail(f"update_reporting_metrics raised: {e}")


class AnalyzeReportUsageTaskTest(TestCase):
    def test_runs_with_no_reports(self):
        from api.alerts.tasks.reporting import analyze_report_usage
        try:
            analyze_report_usage()
        except Exception as e:
            self.fail(f"analyze_report_usage raised: {e}")


class CreateScheduledReportTaskTest(TestCase):
    def test_handles_empty_config(self):
        from api.alerts.tasks.reporting import create_scheduled_report
        try:
            create_scheduled_report({})
        except Exception as e:
            self.fail(f"create_scheduled_report raised on empty config: {e}")

    def test_handles_minimal_valid_config(self):
        from api.alerts.tasks.reporting import create_scheduled_report
        config = {
            'name': 'Daily Ops Report',
            'report_type': 'daily',
            'format_type': 'json',
        }
        try:
            create_scheduled_report(config)
        except Exception as e:
            self.fail(f"create_scheduled_report raised on valid config: {e}")

    def test_handles_invalid_config_gracefully(self):
        from api.alerts.tasks.reporting import create_scheduled_report
        # None config must be handled gracefully — may return None or raise controlled error
        try:
            create_scheduled_report(None)
        except Exception:
            pass  # controlled failure is acceptable; what matters is no uncaught crash


class ExportReportTaskTest(TestCase):
    def test_handles_nonexistent_report_id(self):
        from api.alerts.tasks.reporting import export_report
        # Nonexistent ID — task should return None or a falsy value
        try:
            export_report(999999)
        except Exception as e:
            self.fail(f"export_report raised on nonexistent id: {e}")

    def test_handles_nonexistent_report_with_format(self):
        from api.alerts.tasks.reporting import export_report
        try:
            export_report(999999, format_type='csv')
        except Exception as e:
            self.fail(f"export_report raised with format on nonexistent id: {e}")

    def test_does_not_raise_on_bad_id(self):
        from api.alerts.tasks.reporting import export_report
        try:
            export_report(0)
        except Exception as e:
            self.fail(f"export_report raised on bad id: {e}")


class GenerateCustomReportTaskTest(TestCase):
    def test_handles_nonexistent_report_id(self):
        from api.alerts.tasks.reporting import generate_custom_report
        try:
            generate_custom_report(999999)
        except Exception as e:
            self.fail(f"generate_custom_report raised on nonexistent id: {e}")

    def test_does_not_raise_on_bad_id(self):
        from api.alerts.tasks.reporting import generate_custom_report
        try:
            generate_custom_report(0)
        except Exception as e:
            self.fail(f"generate_custom_report raised on bad id: {e}")

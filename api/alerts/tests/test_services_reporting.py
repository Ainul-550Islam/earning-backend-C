"""Tests for Reporting Services"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

User = get_user_model()


class ReportingServiceBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rpt_svc_user', email='rptsvc@test.com', password='pass123')
        from api.alerts.models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach
        from api.alerts.models.core import AlertRule, AlertLog

        self.report = AlertReport.objects.create(
            title='Test Weekly Report', report_type='weekly',
            status='draft', created_by=self.user,
            start_date=timezone.now() - timedelta(days=7),
            end_date=timezone.now())

        self.mttr = MTTRMetric.objects.create(
            name='Weekly MTTR', calculation_period_days=7,
            target_mttr_minutes=60.0, current_mttr_minutes=45.5,
            total_resolved_alerts=10, target_compliance_percentage=85.0)

        self.mttd = MTTDMetric.objects.create(
            name='Weekly MTTD', calculation_period_days=7,
            target_mttd_minutes=15.0, current_mttd_minutes=12.3,
            detection_rate=95.0, false_positive_rate=5.0,
            total_detected_alerts=25)

        self.rule = AlertRule.objects.create(
            name='SLA Rule', alert_type='server_error', severity='high',
            threshold_value=1.0, created_by=self.user)
        self.alert_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=1.0, threshold_value=1.0,
            message='Critical error')

        self.sla_breach = SLABreach.objects.create(
            name='Test SLA Breach', sla_type='response_time',
            severity='high', status='active',
            alert_log=self.alert_log,
            threshold_minutes=30, breach_duration_minutes=90,
            breach_percentage=200.0,
            financial_impact=Decimal('1000.00'),
            preventive_actions=[])


class AlertReportServiceTest(ReportingServiceBase):

    def test_report_created(self):
        from api.alerts.models.reporting import AlertReport
        self.assertIsNotNone(self.report.id)
        self.assertEqual(self.report.status, 'draft')
        self.assertEqual(self.report.report_type, 'weekly')

    def test_mark_report_complete(self):
        self.report.status = 'completed'
        self.report.save()
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'completed')

    def test_report_period_valid(self):
        self.assertLess(self.report.start_date, self.report.end_date)

    def test_generate_daily_report(self):
        from api.alerts.models.reporting import AlertReport
        daily = AlertReport.objects.create(
            title='Daily Report', report_type='daily',
            status='draft', created_by=self.user,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now())
        self.assertEqual(daily.report_type, 'daily')

    def test_report_filter_by_type(self):
        from api.alerts.models.reporting import AlertReport
        weekly = AlertReport.objects.filter(report_type='weekly')
        self.assertGreaterEqual(weekly.count(), 1)

    def test_report_filter_by_status(self):
        from api.alerts.models.reporting import AlertReport
        # Creating an AlertReport auto-triggers synchronous report generation
        # (post_save signal + CELERY_TASK_ALWAYS_EAGER in tests), which
        # immediately advances status to 'completed'/'failed' in the DB
        # regardless of the status passed at creation - so, like
        # test_mark_report_complete above, we explicitly set+save the status
        # we want to filter on rather than relying on the creation-time value.
        self.report.status = 'failed'
        self.report.save()
        failed_reports = AlertReport.objects.filter(status='failed')
        self.assertGreaterEqual(failed_reports.count(), 1)

    def test_schedule_report(self):
        self.report.status = 'scheduled'
        self.report.save()
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'scheduled')

    def test_report_ordering(self):
        from api.alerts.models.reporting import AlertReport
        reports = AlertReport.objects.order_by('-created_at')
        self.assertGreaterEqual(reports.count(), 1)


class MTTRMetricServiceTest(ReportingServiceBase):

    def test_mttr_metric_created(self):
        self.assertIsNotNone(self.mttr.id)
        self.assertEqual(float(self.mttr.current_mttr_minutes), 45.5)

    def test_mttr_positive_value(self):
        self.assertGreater(self.mttr.current_mttr_minutes, 0)

    def test_mttr_total_resolved_alerts(self):
        self.assertEqual(self.mttr.total_resolved_alerts, 10)

    def test_calculate_average_mttr(self):
        from api.alerts.models.reporting import MTTRMetric
        metrics = MTTRMetric.objects.all()
        if metrics.count() > 0:
            avg = sum(m.current_mttr_minutes for m in metrics) / metrics.count()
            self.assertGreater(avg, 0)

    def test_mttr_trend_query(self):
        from api.alerts.models.reporting import MTTRMetric
        recent = MTTRMetric.objects.order_by('-last_calculated')[:5]
        self.assertGreaterEqual(len(list(recent)), 1)

    def test_mttr_is_within_target(self):
        self.assertTrue(self.mttr.is_within_target())
        self.mttr.current_mttr_minutes = 90.0
        self.assertFalse(self.mttr.is_within_target())


class MTTDMetricServiceTest(ReportingServiceBase):

    def test_mttd_metric_created(self):
        self.assertIsNotNone(self.mttd.id)
        self.assertAlmostEqual(float(self.mttd.current_mttd_minutes), 12.3, places=1)

    def test_mttd_total_detected_alerts(self):
        self.assertEqual(self.mttd.total_detected_alerts, 25)

    def test_mttd_positive_value(self):
        self.assertGreater(self.mttd.current_mttd_minutes, 0)

    def test_mttd_is_within_target(self):
        self.assertTrue(self.mttd.is_within_target())

    def test_mttd_detection_efficiency(self):
        efficiency = self.mttd.get_detection_efficiency()
        self.assertAlmostEqual(efficiency, 95.0 - 5.0, places=1)


class SLABreachServiceTest(ReportingServiceBase):

    def test_sla_breach_created(self):
        self.assertIsNotNone(self.sla_breach.id)
        self.assertEqual(self.sla_breach.status, 'active')

    def test_sla_breach_duration_exceeds_threshold(self):
        self.assertGreater(self.sla_breach.breach_duration_minutes,
                           self.sla_breach.threshold_minutes)

    def test_sla_breach_acknowledge(self):
        self.sla_breach.status = 'acknowledged'
        self.sla_breach.save()
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'acknowledged')

    def test_sla_breach_resolve(self):
        self.sla_breach.status = 'resolved'
        self.sla_breach.resolved_at = timezone.now()
        self.sla_breach.save()
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'resolved')

    def test_sla_open_breach_count(self):
        from api.alerts.models.reporting import SLABreach
        open_breaches = SLABreach.objects.filter(status='active')
        self.assertGreaterEqual(open_breaches.count(), 1)

    def test_breach_by_severity(self):
        from api.alerts.models.reporting import SLABreach
        high_sev = SLABreach.objects.filter(severity='high')
        self.assertGreaterEqual(high_sev.count(), 1)

    def test_breach_by_sla_type(self):
        from api.alerts.models.reporting import SLABreach
        response_time_breaches = SLABreach.objects.filter(sla_type='response_time')
        self.assertGreaterEqual(response_time_breaches.count(), 1)

    def test_breach_impact_score(self):
        score = self.sla_breach.get_impact_score()
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

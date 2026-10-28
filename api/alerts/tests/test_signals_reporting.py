"""
Tests for Reporting Signals — FIXED
Covers: report_created, report_updated, sla_breach_detected, mttr_calculated,
        mttd_calculated, report_scheduled signals.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from api.alerts.models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach
from api.alerts.signals.reporting import (
    report_created, report_updated, report_generated, report_distributed,
    report_scheduled, mttr_calculated, mttd_calculated,
    sla_breach_detected, sla_breach_resolved, sla_breach_acknowledged,
    sla_breach_escalated, performance_metric_calculated, trend_analysis_completed,
)

User = get_user_model()


def _make_report(title='Signal Test Report', report_type='daily', **kwargs):
    now = timezone.now()
    return AlertReport.objects.create(
        title=title, report_type=report_type,
        start_date=now - timedelta(days=1), end_date=now, **kwargs)


class ReportSignalsTest(TestCase):
    """Tests for AlertReport signals"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='repsig', email='repsig@example.com', password='testpass')
        self.signal_received = False
        self.signal_data = {}

    def _handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_report_created_signal(self):
        report_created.connect(self._handler)
        report = _make_report(created_by=self.user)
        self.assertTrue(self.signal_received)
        self.assertIn('instance', self.signal_data)
        report_created.disconnect(self._handler)

    def test_report_updated_signal(self):
        report = _make_report(title='Update Report', created_by=self.user)
        report_updated.connect(self._handler)
        self.signal_received = False
        report.title = 'Updated Report'
        report.save()
        self.assertTrue(self.signal_received)
        report_updated.disconnect(self._handler)

    def test_report_generated_signal_fires_on_generate(self):
        report = _make_report(report_type='daily', created_by=self.user)
        report_generated.connect(self._handler)
        report.generate_report()
        self.assertTrue(self.signal_received)
        self.assertEqual(report.status, 'completed')
        report_generated.disconnect(self._handler)

    def test_report_distributed_signal_fires_on_distribute(self):
        report = _make_report(created_by=self.user)
        report_distributed.connect(self._handler)
        report.distribute(recipients=['ops@example.com'])
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data.get('recipients'), ['ops@example.com'])
        report_distributed.disconnect(self._handler)

    def test_report_scheduled_signal_fires_on_schedule(self):
        report = _make_report(created_by=self.user, recurrence_pattern='weekly')
        report_scheduled.connect(self._handler)
        report.schedule_next_run()
        self.assertTrue(self.signal_received)
        report_scheduled.disconnect(self._handler)


class SLABreachSignalsTest(TestCase):
    """Tests for SLABreach signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = {}

    def _handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_sla_breach_detected_signal(self):
        sla_breach_detected.connect(self._handler)
        breach = SLABreach.objects.create(
            sla_name='Signal SLA', breach_type='resolution_time',
            severity='high', status='open',
            target_minutes=30, actual_minutes=90)
        self.assertTrue(self.signal_received)
        self.assertIn('instance', self.signal_data)
        sla_breach_detected.disconnect(self._handler)

    def test_sla_breach_resolved_signal_fires_on_resolve(self):
        breach = SLABreach.objects.create(
            sla_name='Resolve SLA', breach_type='resolution_time',
            severity='high', status='open',
            target_minutes=30, actual_minutes=90)
        sla_breach_resolved.connect(self._handler)
        breach.resolve(user=None, note='Fixed')
        self.assertTrue(self.signal_received)
        sla_breach_resolved.disconnect(self._handler)

    def test_sla_breach_acknowledged_signal_fires_on_acknowledge(self):
        breach = SLABreach.objects.create(
            sla_name='Ack SLA', breach_type='resolution_time',
            severity='high', status='open',
            target_minutes=30, actual_minutes=90)
        sla_breach_acknowledged.connect(self._handler)
        breach.acknowledge(user=None, note='Looking into it')
        self.assertTrue(self.signal_received)
        sla_breach_acknowledged.disconnect(self._handler)

    def test_sla_breach_escalated_signal_fires_on_escalate(self):
        breach = SLABreach.objects.create(
            sla_name='Escalate SLA', breach_type='resolution_time',
            severity='high', status='open',
            target_minutes=30, actual_minutes=90)
        sla_breach_escalated.connect(self._handler)
        breach.escalate(reason='SLA badly missed')
        self.assertTrue(self.signal_received)
        self.assertEqual(self.signal_data.get('reason'), 'SLA badly missed')
        sla_breach_escalated.disconnect(self._handler)


class MTTRSignalsTest(TestCase):
    """Tests for MTTRMetric and MTTDMetric signals"""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_mttr_calculated_signal_fires_on_calculate(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='MTTR Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        now = timezone.now()
        AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0, message='Test',
            is_resolved=True, triggered_at=now - timedelta(minutes=30), resolved_at=now)
        mttr_calculated.connect(self._handler)
        metric = MTTRMetric.objects.create(name='Real MTTR', target_mttr_minutes=30.0)
        metric.calculate_mttr()
        self.assertTrue(self.signal_received)
        mttr_calculated.disconnect(self._handler)

    def test_mttd_calculated_signal_fires_on_calculate(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='MTTD Signal Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30)
        AlertLog.objects.create(
            rule=rule, trigger_value=90.0, threshold_value=80.0, message='Test',
            is_resolved=False)
        mttd_calculated.connect(self._handler)
        metric = MTTDMetric.objects.create(name='Real MTTD', target_mttd_minutes=15.0)
        metric.calculate_mttd()
        self.assertTrue(self.signal_received)
        mttd_calculated.disconnect(self._handler)

    def test_mttr_metric_can_be_created(self):
        metric = MTTRMetric.objects.create(
            name='Test MTTR', target_mttr_minutes=30.0)
        self.assertEqual(metric.name, 'Test MTTR')
        self.assertEqual(metric.target_mttr_minutes, 30.0)

    def test_mttd_metric_can_be_created(self):
        metric = MTTDMetric.objects.create(
            name='Test MTTD', target_mttd_minutes=15.0)
        self.assertEqual(metric.name, 'Test MTTD')
        self.assertEqual(metric.target_mttd_minutes, 15.0)

    def test_mttr_signal_can_be_manually_fired(self):
        mttr_calculated.connect(self._handler)
        metric = MTTRMetric.objects.create(
            name='Manual MTTR Signal', target_mttr_minutes=60.0)
        mttr_calculated.send(sender=MTTRMetric, instance=metric)
        self.assertTrue(self.signal_received)
        mttr_calculated.disconnect(self._handler)


class NewlyWiredReportingSignalsTest(TestCase):
    """Real behavioral tests for performance_metric_calculated and
    trend_analysis_completed, confirmed never fired anywhere before."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='newrepsig', email='newrepsig@example.com', password='testpass')
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_performance_metric_calculated_signal(self):
        report = _make_report(report_type='performance', created_by=self.user)
        performance_metric_calculated.connect(self._handler)
        report.generate_report()
        self.assertTrue(self.signal_received)
        performance_metric_calculated.disconnect(self._handler)

    def test_trend_analysis_completed_signal(self):
        report = _make_report(report_type='trend', created_by=self.user)
        trend_analysis_completed.connect(self._handler)
        report.generate_report()
        self.assertTrue(self.signal_received)
        trend_analysis_completed.disconnect(self._handler)

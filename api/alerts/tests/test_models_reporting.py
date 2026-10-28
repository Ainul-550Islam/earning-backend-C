"""
Tests for Reporting Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from decimal import Decimal

from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach

User = get_user_model()


class AlertReportModelTest(TestCase):
    """Test cases for AlertReport model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_report = AlertReport.objects.create(
            title='Daily Alert Report',
            report_type='daily',
            format_type='json',
            status='completed',
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now(),
            is_recurring=True,
            recurrence_pattern='daily',
            auto_distribute=True,
            recipients=['admin@example.com', 'ops@example.com'],
            included_metrics=['alert_count', 'resolution_rate', 'mttr'],
            rule_filters={'severity': ['high', 'critical']},
            severity_filters=['high', 'critical'],
            status_filters=['resolved', 'pending'],
            summary='Daily summary of alert activity',
            generated_at=timezone.now(),
            generation_duration_ms=1500,
            file_path='/reports/daily_report.json',
            file_size_bytes=1024,
            created_by=self.user
        )

    def test_alert_report_creation(self):
        """Test AlertReport creation"""
        self.assertEqual(self.alert_report.title, 'Daily Alert Report')
        self.assertEqual(self.alert_report.report_type, 'daily')
        self.assertEqual(self.alert_report.format_type, 'json')
        self.assertEqual(self.alert_report.status, 'completed')
        self.assertTrue(self.alert_report.is_recurring)
        self.assertTrue(self.alert_report.auto_distribute)

    def test_alert_report_str_representation(self):
        """Test AlertReport string representation"""
        expected = f'AlertReport: {self.alert_report.title} - daily'
        self.assertEqual(str(self.alert_report), expected)

    def test_alert_report_get_type_display(self):
        """Test AlertReport profile_type property"""
        self.assertEqual(self.alert_report.profile_type, 'Daily')
        self.alert_report.report_type = 'weekly'
        self.assertEqual(self.alert_report.profile_type, 'Weekly')
        self.alert_report.report_type = 'monthly'
        self.assertEqual(self.alert_report.profile_type, 'Monthly')
        self.alert_report.report_type = 'sla'
        self.assertEqual(self.alert_report.profile_type, 'SLA')
        self.alert_report.report_type = 'custom'
        self.assertEqual(self.alert_report.profile_type, 'Custom')

    def test_alert_report_get_format_display(self):
        """Test AlertReport get_format_display method"""
        self.assertEqual(self.alert_report.get_format_display(), 'JSON')
        self.alert_report.format_type = 'pdf'
        self.assertEqual(self.alert_report.get_format_display(), 'PDF')
        self.alert_report.format_type = 'csv'
        self.assertEqual(self.alert_report.get_format_display(), 'CSV')
        self.alert_report.format_type = 'html'
        self.assertEqual(self.alert_report.get_format_display(), 'HTML')

    def test_alert_report_get_status_display(self):
        """Test AlertReport status display via Django choices"""
        self.assertEqual(self.alert_report.get_status_display(), 'Completed')
        self.alert_report.status = 'pending'
        self.assertEqual(self.alert_report.get_status_display(), 'Pending')
        self.alert_report.status = 'generating'
        self.assertEqual(self.alert_report.get_status_display(), 'Generating')
        self.alert_report.status = 'failed'
        self.assertEqual(self.alert_report.get_status_display(), 'Failed')
        self.alert_report.status = 'scheduled'
        self.assertEqual(self.alert_report.get_status_display(), 'Scheduled')

    def test_alert_report_generate(self):
        """Test AlertReport generate method returns correct keys"""
        result = self.alert_report.generate()
        self.assertIsInstance(result, dict)
        self.assertIn('report_id', result)
        self.assertIn('file_path', result)
        self.assertIn('generation_time', result)
        self.assertIn('record_count', result)

    def test_alert_report_distribute(self):
        """Test AlertReport distribute method"""
        result = self.alert_report.distribute()
        self.assertIsInstance(result, dict)
        self.assertIn('sent_count', result)
        self.assertIn('failed_count', result)
        self.assertEqual(result['failed_count'], 0)

    def test_alert_report_schedule_next_run(self):
        """Test AlertReport schedule_next_run sets next_run"""
        self.alert_report.schedule_next_run()
        self.assertIsNotNone(self.alert_report.next_run)
        expected_next_run = timezone.now().date() + timedelta(days=1)
        self.assertEqual(self.alert_report.next_run.date(), expected_next_run)

    def test_alert_report_get_recipients_list(self):
        """Test AlertReport get_recipients_list from JSON field"""
        recipients = self.alert_report.get_recipients_list()
        self.assertIsInstance(recipients, list)
        self.assertIn('admin@example.com', recipients)
        self.assertIn('ops@example.com', recipients)

    def test_alert_report_add_recipient(self):
        """Test AlertReport add_recipient updates JSON field"""
        initial_count = len(self.alert_report.get_recipients_list())
        self.alert_report.add_recipient('new@example.com')
        new_count = len(self.alert_report.get_recipients_list())
        self.assertEqual(new_count, initial_count + 1)
        self.assertIn('new@example.com', self.alert_report.get_recipients_list())

    def test_alert_report_remove_recipient(self):
        """Test AlertReport remove_recipient updates JSON field"""
        initial_count = len(self.alert_report.get_recipients_list())
        self.alert_report.remove_recipient('admin@example.com')
        new_count = len(self.alert_report.get_recipients_list())
        self.assertEqual(new_count, initial_count - 1)
        self.assertNotIn('admin@example.com', self.alert_report.get_recipients_list())

    def test_alert_report_get_file_size_display(self):
        """Test AlertReport get_file_size_display method"""
        display = self.alert_report.get_file_size_display()
        self.assertEqual(display, '1.0 KB')
        self.alert_report.file_size_bytes = 1024 * 1024
        self.alert_report.save()
        display = self.alert_report.get_file_size_display()
        self.assertEqual(display, '1.0 MB')

    def test_alert_report_is_ready_to_generate(self):
        """Test AlertReport is_ready_to_generate"""
        self.alert_report.status = 'completed'
        self.assertTrue(self.alert_report.is_ready_to_generate())
        self.alert_report.status = 'generating'
        self.assertFalse(self.alert_report.is_ready_to_generate())
        self.alert_report.status = 'pending'
        self.assertTrue(self.alert_report.is_ready_to_generate())

    def test_alert_report_get_generation_duration_display(self):
        """Test AlertReport get_generation_duration_display"""
        display = self.alert_report.get_generation_duration_display()
        self.assertEqual(display, '1.5 seconds')
        self.alert_report.generation_duration_ms = None
        self.alert_report.save()
        display = self.alert_report.get_generation_duration_display()
        self.assertEqual(display, 'N/A')


class MTTRMetricModelTest(TestCase):
    """Test cases for MTTRMetric model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.mttr_metric = MTTRMetric.objects.create(
            name='Overall MTTR',
            calculation_period_days=30,
            target_mttr_minutes=60.0,
            current_mttr_minutes=45.0,
            mttr_by_severity={'low': 20.0, 'medium': 35.0, 'high': 55.0, 'critical': 90.0},
            mttr_by_rule={'cpu_alert': 40.0, 'memory_alert': 50.0},
            mttr_trend_7_days=-5.2,
            mttr_trend_30_days=2.1,
            alerts_within_target=85,
            total_resolved_alerts=100,
            target_compliance_percentage=85.0
        )

    def test_mttr_metric_creation(self):
        """Test MTTRMetric creation"""
        self.assertEqual(self.mttr_metric.name, 'Overall MTTR')
        self.assertEqual(self.mttr_metric.target_mttr_minutes, 60.0)
        self.assertEqual(self.mttr_metric.current_mttr_minutes, 45.0)
        self.assertEqual(self.mttr_metric.total_resolved_alerts, 100)

    def test_mttr_metric_str_representation(self):
        """Test MTTRMetric string representation"""
        self.assertEqual(str(self.mttr_metric), 'MTTRMetric: Overall MTTR')

    def test_mttr_metric_calculate(self):
        """Test MTTRMetric calculate returns result dict"""
        result = self.mttr_metric.calculate()
        self.assertIsInstance(result, dict)
        self.assertIn('current_mttr_minutes', result)
        self.assertIn('total_resolved_alerts', result)
        self.assertIn('target_compliance_percentage', result)

    def test_mttr_metric_get_mttr_by_severity(self):
        """Test MTTRMetric get_mttr_by_severity"""
        data = self.mttr_metric.get_mttr_by_severity()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['low'], 20.0)
        self.assertEqual(data['high'], 55.0)

    def test_mttr_metric_get_mttr_by_rule(self):
        """Test MTTRMetric get_mttr_by_rule"""
        data = self.mttr_metric.get_mttr_by_rule()
        self.assertIsInstance(data, dict)
        self.assertEqual(data['cpu_alert'], 40.0)

    def test_mttr_metric_is_within_target(self):
        """Test MTTRMetric is_within_target"""
        self.assertTrue(self.mttr_metric.is_within_target())
        self.mttr_metric.current_mttr_minutes = 70.0
        self.assertFalse(self.mttr_metric.is_within_target())

    def test_mttr_metric_get_improvement_percentage(self):
        """Test MTTRMetric get_improvement_percentage"""
        improvement = self.mttr_metric.get_improvement_percentage()
        expected = ((60.0 - 45.0) / 60.0) * 100
        self.assertAlmostEqual(improvement, expected, places=2)

    def test_mttr_metric_get_trend_display(self):
        """Test MTTRMetric get_trend_display"""
        display = self.mttr_metric.get_trend_display('7_days')
        self.assertIn('improving', display.lower())
        display = self.mttr_metric.get_trend_display('30_days')
        self.assertIn('worsening', display.lower())

    def test_mttr_metric_get_compliance_badge(self):
        """Test MTTRMetric get_compliance_badge"""
        badge = self.mttr_metric.get_compliance_badge()
        self.assertIn('85.0%', badge)
        self.assertIn('good', badge.lower())

    def test_mttr_metric_update_mttr_by_severity(self):
        """Test MTTRMetric update_mttr_by_severity"""
        new_data = {'low': 25.0, 'medium': 40.0, 'high': 60.0, 'critical': 95.0}
        self.mttr_metric.update_mttr_by_severity(new_data)
        updated = self.mttr_metric.get_mttr_by_severity()
        self.assertEqual(updated['low'], 25.0)
        self.assertEqual(updated['critical'], 95.0)


class MTTDMetricModelTest(TestCase):
    """Test cases for MTTDMetric model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.mttd_metric = MTTDMetric.objects.create(
            name='Overall MTTD',
            calculation_period_days=30,
            target_mttd_minutes=15.0,
            current_mttd_minutes=12.0,
            mttd_by_severity={'low': 5.0, 'medium': 10.0, 'high': 15.0, 'critical': 25.0},
            mttd_by_rule={'cpu_alert': 10.0, 'memory_alert': 12.0},
            mttd_trend_7_days=-2.1,
            mttd_trend_30_days=1.5,
            detection_rate=95.0,
            false_positive_rate=5.0,
            target_compliance_percentage=80.0
        )

    def test_mttd_metric_creation(self):
        """Test MTTDMetric creation"""
        self.assertEqual(self.mttd_metric.name, 'Overall MTTD')
        self.assertEqual(self.mttd_metric.target_mttd_minutes, 15.0)
        self.assertEqual(self.mttd_metric.current_mttd_minutes, 12.0)
        self.assertEqual(self.mttd_metric.detection_rate, 95.0)

    def test_mttd_metric_str_representation(self):
        """Test MTTDMetric string representation"""
        self.assertEqual(str(self.mttd_metric), 'MTTDMetric: Overall MTTD')

    def test_mttd_metric_calculate(self):
        """Test MTTDMetric calculate returns result dict"""
        result = self.mttd_metric.calculate()
        self.assertIsInstance(result, dict)
        self.assertIn('current_mttd_minutes', result)
        self.assertIn('detection_rate', result)
        self.assertIn('false_positive_rate', result)

    def test_mttd_metric_get_mttd_by_severity(self):
        """Test MTTDMetric get_mttd_by_severity"""
        data = self.mttd_metric.get_mttd_by_severity()
        self.assertEqual(data['low'], 5.0)
        self.assertEqual(data['high'], 15.0)

    def test_mttd_metric_get_mttd_by_rule(self):
        """Test MTTDMetric get_mttd_by_rule"""
        data = self.mttd_metric.get_mttd_by_rule()
        self.assertEqual(data['cpu_alert'], 10.0)
        self.assertEqual(data['memory_alert'], 12.0)

    def test_mttd_metric_is_within_target(self):
        """Test MTTDMetric is_within_target"""
        self.assertTrue(self.mttd_metric.is_within_target())
        self.mttd_metric.current_mttd_minutes = 20.0
        self.assertFalse(self.mttd_metric.is_within_target())

    def test_mttd_metric_get_detection_quality_badge(self):
        """Test MTTDMetric get_detection_quality_badge"""
        badge = self.mttd_metric.get_detection_quality_badge()
        self.assertIn('95.0%', badge)
        self.assertIn('excellent', badge.lower())

    def test_mttd_metric_get_detection_efficiency(self):
        """Test MTTDMetric get_detection_efficiency"""
        efficiency = self.mttd_metric.get_detection_efficiency()
        self.assertEqual(efficiency, 95.0 - 5.0)

    def test_mttd_metric_update_detection_rates(self):
        """Test MTTDMetric update_detection_rates"""
        self.mttd_metric.update_detection_rates(92.0, 8.0)
        self.mttd_metric.refresh_from_db()
        self.assertEqual(self.mttd_metric.detection_rate, 92.0)
        self.assertEqual(self.mttd_metric.false_positive_rate, 8.0)


class SLABreachModelTest(TestCase):
    """Test cases for SLABreach model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Critical Alert', alert_type='server_error',
            severity='critical', threshold_value=1.0, created_by=self.user
        )
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule, trigger_value=1.0,
            threshold_value=1.0, message='Critical system error'
        )
        self.sla_breach = SLABreach.objects.create(
            name='Critical Response Time Breach',
            sla_type='response_time',
            severity='critical',
            alert_log=self.alert_log,
            threshold_minutes=30,
            breach_duration_minutes=15,
            breach_percentage=50.0,
            status='active',
            escalation_level=1,
            business_impact='Critical services unavailable',
            financial_impact=Decimal('10000.00'),
            customer_impact='All customers affected',
            root_cause='System overload',
            preventive_actions=['Increase system capacity']
        )

    def test_sla_breach_creation(self):
        """Test SLABreach creation"""
        self.assertEqual(self.sla_breach.name, 'Critical Response Time Breach')
        self.assertEqual(self.sla_breach.sla_type, 'response_time')
        self.assertEqual(self.sla_breach.severity, 'critical')
        self.assertEqual(self.sla_breach.threshold_minutes, 30)
        self.assertEqual(self.sla_breach.breach_duration_minutes, 15)
        self.assertEqual(self.sla_breach.breach_percentage, 50.0)

    def test_sla_breach_str_representation(self):
        """Test SLABreach string representation"""
        expected = 'SLABreach: Critical Response Time Breach - critical'
        self.assertEqual(str(self.sla_breach), expected)

    def test_sla_breach_get_type_display(self):
        """Test SLABreach profile_type property"""
        self.assertEqual(self.sla_breach.profile_type, 'Response Time')
        self.sla_breach.sla_type = 'resolution_time'
        self.assertEqual(self.sla_breach.profile_type, 'Resolution Time')
        self.sla_breach.sla_type = 'availability'
        self.assertEqual(self.sla_breach.profile_type, 'Availability')

    def test_sla_breach_get_severity_display(self):
        """Test SLABreach severity display via Django choices"""
        self.assertEqual(self.sla_breach.get_severity_display(), 'Critical')
        self.sla_breach.severity = 'high'
        self.assertEqual(self.sla_breach.get_severity_display(), 'High')

    def test_sla_breach_get_status_display(self):
        """Test SLABreach status display"""
        self.assertEqual(self.sla_breach.get_status_display(), 'Active')
        self.sla_breach.status = 'resolved'
        self.assertEqual(self.sla_breach.get_status_display(), 'Resolved')
        self.sla_breach.status = 'escalated'
        self.assertEqual(self.sla_breach.get_status_display(), 'Escalated')
        self.sla_breach.status = 'acknowledged'
        self.assertEqual(self.sla_breach.get_status_display(), 'Acknowledged')

    def test_sla_breach_acknowledge(self):
        """Test SLABreach acknowledge method"""
        self.sla_breach.acknowledge(self.user, 'Investigating the breach')
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'acknowledged')
        self.assertEqual(self.sla_breach.acknowledged_by, self.user)
        self.assertEqual(self.sla_breach.acknowledgment_note, 'Investigating the breach')
        self.assertIsNotNone(self.sla_breach.acknowledged_at)

    def test_sla_breach_resolve(self):
        """Test SLABreach resolve method"""
        self.sla_breach.resolve(self.user, 'Fixed the issue', 'System capacity increased')
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'resolved')
        self.assertEqual(self.sla_breach.resolved_by, self.user)
        self.assertEqual(self.sla_breach.resolution_note, 'Fixed the issue')
        self.assertEqual(self.sla_breach.resolution_actions, 'System capacity increased')
        self.assertIsNotNone(self.sla_breach.resolved_at)

    def test_sla_breach_escalate(self):
        """Test SLABreach escalate method"""
        initial_level = self.sla_breach.escalation_level
        self.sla_breach.escalate(self.user, 'No response from primary team')
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.escalation_level, initial_level + 1)
        self.assertEqual(self.sla_breach.escalation_reason, 'No response from primary team')
        self.assertIsNotNone(self.sla_breach.escalated_at)

    def test_sla_breach_get_breach_severity(self):
        """Test SLABreach get_breach_severity"""
        severity = self.sla_breach.get_breach_severity()
        self.assertIn(severity, ['low', 'medium', 'high', 'critical'])
        self.sla_breach.breach_percentage = 10.0
        self.assertEqual(self.sla_breach.get_breach_severity(), 'low')
        self.sla_breach.breach_percentage = 150.0
        self.assertEqual(self.sla_breach.get_breach_severity(), 'critical')

    def test_sla_breach_get_duration_display(self):
        """Test SLABreach get_duration_display"""
        display = self.sla_breach.get_duration_display()
        self.assertEqual(display, '15.0 minutes')
        # Test with zero duration (field has NOT NULL constraint)
        self.sla_breach.breach_duration_minutes = 0
        self.sla_breach.save()
        self.assertIsNotNone(self.sla_breach.get_duration_display())

    def test_sla_breach_get_impact_score(self):
        """Test SLABreach get_impact_score returns 0-100 numeric"""
        score = self.sla_breach.get_impact_score()
        self.assertIsInstance(score, (int, float))
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_sla_breach_is_overdue(self):
        """Test SLABreach is_overdue"""
        self.assertTrue(self.sla_breach.is_overdue())
        self.sla_breach.status = 'resolved'
        self.assertFalse(self.sla_breach.is_overdue())

    def test_sla_breach_get_escalation_threshold(self):
        """Test SLABreach get_escalation_threshold returns int >= 0"""
        threshold = self.sla_breach.get_escalation_threshold()
        self.assertIsInstance(threshold, int)
        self.assertGreaterEqual(threshold, 0)

    def test_sla_breach_should_escalate(self):
        """Test SLABreach should_escalate for active vs resolved"""
        self.assertTrue(self.sla_breach.should_escalate())
        self.sla_breach.status = 'resolved'
        self.sla_breach.save()
        self.assertFalse(self.sla_breach.should_escalate())

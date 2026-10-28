"""Tests for Reporting Serializers"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from api.alerts.models.core import AlertRule, AlertLog
from api.alerts.models.reporting import AlertReport, MTTRMetric, MTTDMetric, SLABreach
from api.alerts.serializers.reporting import (
    AlertReportSerializer, MTTRMetricSerializer, MTTDMetricSerializer, SLABreachSerializer,
    AlertReportListSerializer, SLABreachListSerializer)
User = get_user_model()


class AlertReportSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.report = AlertReport.objects.create(
            title='Daily Report', report_type='daily', format_type='json',
            status='completed', start_date=timezone.now() - timezone.timedelta(days=1),
            end_date=timezone.now(), created_by=self.user)

    def test_serializer_read(self):
        data = AlertReportSerializer(self.report).data
        for f in ['id', 'title', 'report_type', 'format_type', 'status',
                  'start_date', 'end_date', 'file_size_display']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = AlertReportListSerializer(self.report).data
        for f in ['id', 'title', 'report_type', 'status', 'format_type', 'created_at']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = AlertReportSerializer(data={
            'title': 'Weekly Report', 'report_type': 'weekly',
            'format_type': 'csv', 'start_date': str(timezone.now()),
            'end_date': str(timezone.now())
        })
        self.assertTrue(s.is_valid(), s.errors)


class MTTRMetricSerializerTest(TestCase):
    def setUp(self):
        self.mttr = MTTRMetric.objects.create(
            name='Overall MTTR', calculation_period_days=30,
            target_mttr_minutes=60.0, current_mttr_minutes=45.0,
            total_resolved_alerts=100, target_compliance_percentage=85.0)

    def test_serializer_read(self):
        data = MTTRMetricSerializer(self.mttr).data
        for f in ['id', 'name', 'target_mttr_minutes', 'current_mttr_minutes',
                  'target_compliance_percentage', 'last_calculated']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = MTTRMetricSerializer(data={
            'name': 'New MTTR', 'calculation_period_days': 7,
            'target_mttr_minutes': 30.0, 'total_resolved_alerts': 50})
        self.assertTrue(s.is_valid(), s.errors)


class MTTDMetricSerializerTest(TestCase):
    def setUp(self):
        self.mttd = MTTDMetric.objects.create(
            name='Overall MTTD', calculation_period_days=30,
            target_mttd_minutes=15.0, current_mttd_minutes=12.0,
            detection_rate=95.0, false_positive_rate=5.0)

    def test_serializer_read(self):
        data = MTTDMetricSerializer(self.mttd).data
        for f in ['id', 'name', 'target_mttd_minutes', 'current_mttd_minutes',
                  'detection_rate', 'last_calculated']:
            self.assertIn(f, data)

    def test_serializer_create(self):
        s = MTTDMetricSerializer(data={
            'name': 'New MTTD', 'calculation_period_days': 7,
            'target_mttd_minutes': 10.0, 'detection_rate': 90.0,
            'false_positive_rate': 10.0})
        self.assertTrue(s.is_valid(), s.errors)


class SLABreachSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Critical Alert', alert_type='server_error', severity='critical',
            threshold_value=1.0, created_by=self.user)
        self.alert_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=1.0, threshold_value=1.0,
            message='Critical error')
        self.breach = SLABreach.objects.create(
            name='Critical Response Breach', sla_type='response_time',
            severity='critical', alert_log=self.alert_log,
            threshold_minutes=30, breach_duration_minutes=15,
            breach_percentage=50.0, status='active',
            financial_impact=Decimal('1000.00'),
            preventive_actions=['Scale up'])

    def test_serializer_read(self):
        data = SLABreachSerializer(self.breach).data
        for f in ['id', 'name', 'sla_type', 'severity', 'status', 'breach_time',
                  'breach_percentage', 'breach_severity', 'duration_minutes']:
            self.assertIn(f, data)

    def test_list_serializer(self):
        data = SLABreachListSerializer(self.breach).data
        for f in ['id', 'name', 'sla_type', 'severity', 'breach_time',
                  'breach_percentage', 'status']:
            self.assertIn(f, data)

"""
Tests for Reporting ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.reporting import (
    AlertReport, MTTRMetric, MTTDMetric, SLABreach
)
from alerts.viewsets.reporting import (
    AlertReportViewSet, MTTRMetricViewSet, MTTDMetricViewSet, SLABreachViewSet,
    ReportingDashboardViewSet
)

User = get_user_model()


class AlertReportViewSetTest(APITestCase):
    """Test cases for AlertReportViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_report = AlertReport.objects.create(
            title='Daily Alert Report',
            report_type='daily',
            format_type='json',
            status='completed',
            start_date=timezone.now().date() - timezone.timedelta(days=1),
            end_date=timezone.now().date(),
            is_recurring=True,
            recurrence_pattern='daily',
            auto_distribute=True,
            recipients=['admin@example.com', 'ops@example.com'],
            created_by=self.user
        )
    
    def test_list_alert_reports(self):
        """Test listing alert reports"""
        url = '/api/alerts/reports/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['report_type'], 'daily')
    
    def test_create_alert_report(self):
        """Test creating alert report"""
        url = '/api/alerts/reports/'
        data = {
            'title': 'Weekly Alert Report',
            'report_type='weekly',
            'format_type='pdf',
            'status='pending',
            'start_date': timezone.now().date() - timezone.timedelta(days=7),
            'end_date': timezone.now().date(),
            'is_recurring=True,
            'recurrence_pattern='weekly',
            'auto_distribute=False,
            'recipients=['team@example.com']
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertReport.objects.count(), 2)
    
    def test_retrieve_alert_report(self):
        """Test retrieving single alert report"""
        url = f'/api/alerts/reports/{self.alert_report.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Daily Alert Report')
    
    def test_generate_report(self):
        """Test generating report"""
        # Create some test data
        for i in range(10):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=AlertRule.objects.get(name=f'Alert {i}'),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Test alert {i}'
            )
        
        url = f'/api/alerts/reports/{self.alert_report.id}/generate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('generation_result', response.data)
        self.assertIn('report_id', response.data)
    
    def test_distribute_report(self):
        """Test distributing report"""
        url = f'/api/alerts/reports/{self.alert_report.id}/distribute/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('distribution_result', response.data)
        self.assertIn('sent_count', response.data)
    
    def test_schedule_next_run(self):
        """Test scheduling next run"""
        url = f'/api/alerts/reports/{self.alert_report.id}/schedule_next_run/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_report.refresh_from_db()
        self.assertIsNotNone(self.alert_report.next_run)
    
    def test_get_reports_by_type(self):
        """Test getting reports by type"""
        url = '/api/alerts/reports/by_type/daily/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_reports_by_status(self):
        """Test getting reports by status"""
        url = '/api/alerts/reports/by_status/completed/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_recent_reports(self):
        """Test getting recent reports"""
        url = '/api/alerts/reports/recent/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recent_reports', response.data)
    
    def test_export_report(self):
        """Test exporting report"""
        url = f'/api/alerts/reports/{self.alert_report.id}/export/'
        data = {
            'export_format': 'csv'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('export_result', response.data)


class MTTRMetricViewSetTest(APITestCase):
    """Test cases for MTTRMetricViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.mttr_metric = MTTRMetric.objects.create(
            name='Overall MTTR',
            calculation_period_days=30,
            target_mttr_minutes=60.0,
            current_mttr_minutes=45.0,
            alerts_within_target=85,
            total_resolved_alerts=100,
            target_compliance_percentage=85.0,
            created_by=self.user
        )
    
    def test_list_mttr_metrics(self):
        """Test listing MTTR metrics"""
        url = '/api/alerts/reports/mttr/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Overall MTTR')
    
    def test_create_mttr_metric(self):
        """Test creating MTTR metric"""
        url = '/api/alerts/reports/mttr/'
        data = {
            'name': 'Critical MTTR',
            'calculation_period_days=7,
            'target_mttr_minutes=30.0,
            'current_mttr_minutes=25.0,
            'alerts_within_target=95,
            'total_resolved_alerts=100,
            'target_compliance_percentage=95.0
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MTTRMetric.objects.count(), 2)
    
    def test_retrieve_mttr_metric(self):
        """Test retrieving single MTTR metric"""
        url = f'/api/alerts/reports/mttr/{self.mttr_metric.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Overall MTTR')
    
    def test_calculate_mttr(self):
        """Test calculating MTTR"""
        # Create some test alert data
        for i in range(50):
            alert_rule = AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            
            alert = AlertLog.objects.create(
                rule=alert_rule,
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Test alert {i}'
            )
            
            # Resolve some alerts
            if i % 3 == 0:
                alert.is_resolved = True
                alert.resolved_at = timezone.now() - timedelta(minutes=i * 2)
                alert.save()
        
        url = f'/api/alerts/reports/mttr/{self.mttr_metric.id}/calculate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('calculation_result', response.data)
        self.assertIn('current_mttr_minutes', response.data)
    
    def test_get_mttr_by_severity(self):
        """Test getting MTTR by severity"""
        url = f'/api/alerts/reports/mttr/{self.mttr_metric.id}/by_severity/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('mttr_by_severity', response.data)
    
    def test_get_mttr_trends(self):
        """Test getting MTTR trends"""
        url = f'/api/alerts/reports/mttr/{self.mttr_metric.id}/trends/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trend_data', response.data)
    
    def test_get_compliance_badge(self):
        """Test getting compliance badge"""
        url = f'/api/alerts/reports/mttr/{self.mttr_metric.id}/compliance_badge/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('badge', response.data)
    
    def test_get_metrics_by_period(self):
        """Test getting metrics by period"""
        url = '/api/alerts/reports/mttr/by_period/30/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('metrics', response.data)


class MTTDMetricViewSetTest(APITestCase):
    """Test cases for MTTDMetricViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.mttd_metric = MTTDMetric.objects.create(
            name='Overall MTTD',
            calculation_period_days=30,
            target_mttd_minutes=15.0,
            current_mttd_minutes=12.0,
            detection_rate=95.0,
            false_positive_rate=5.0,
            target_compliance_percentage=80.0,
            created_by=self.user
        )
    
    def test_list_mttd_metrics(self):
        """Test listing MTTD metrics"""
        url = '/api/alerts/reports/mttd/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_mttd_metric(self):
        """Test creating MTTD metric"""
        url = '/api/alerts/reports/mttd/'
        data = {
            'name': 'Critical MTTD',
            'calculation_period_days=7,
            'target_mttd_minutes=10.0,
            'current_mttd_minutes=8.0,
            'detection_rate=98.0,
            'false_positive_rate=2.0
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MTTDMetric.objects.count(), 2)
    
    def test_retrieve_mttd_metric(self):
        """Test retrieving single MTTD metric"""
        url = f'/api/alerts/reports/mttd/{self.mttd_metric.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Overall MTTD')
    
    def test_calculate_mttd(self):
        """Test calculating MTTD"""
        # Create some test alert data
        for i in range(30):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=AlertRule.objects.get(name=f'Alert {i}'),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Test alert {i}',
                triggered_at=timezone.now() - timedelta(minutes=i)
            )
        
        url = f'/api/alerts/reports/mttd/{self.mttd_metric.id}/calculate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('calculation_result', response.data)
        self.assertIn('current_mttd_minutes', response.data)
    
    def test_get_detection_quality_badge(self):
        """Test getting detection quality badge"""
        url = f'/api/alerts/reports/mttd/{self.mttd_metric.id}/quality_badge/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('badge', response.data)
    
    def test_update_detection_rates(self):
        """Test updating detection rates"""
        url = f'/api/alerts/reports/mttd/{self.mttd_metric.id}/update_rates/'
        data = {
            'detection_rate': 92.0,
            'false_positive_rate': 8.0
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.mttd_metric.refresh_from_db()
        self.assertEqual(self.mttd_metric.detection_rate, 92.0)
        self.assertEqual(self.mttd_metric.false_positive_rate, 8.0)


class SLABreachViewSetTest(APITestCase):
    """Test cases for SLABreachViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Critical Alert',
            alert_type='system_error',
            severity='critical',
            threshold_value=1.0
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1.0,
            threshold_value=1.0,
            message='Critical system error'
        )
        
        self.sla_breach = SLABreach.objects.create(
            name='Critical Response Time Breach',
            sla_type='response_time',
            severity='critical',
            alert_log=self.alert_log,
            threshold_minutes=30,
            breach_time=timezone.now() - timedelta(minutes=45),
            breach_duration_minutes=15,
            breach_percentage=50.0,
            status='active'
        )
    
    def test_list_sla_breaches(self):
        """Test listing SLA breaches"""
        url = '/api/alerts/reports/sla_breaches/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['sla_type'], 'response_time')
    
    def test_create_sla_breach(self):
        """Test creating SLA breach"""
        url = '/api/alerts/reports/sla_breaches/'
        data = {
            'name': 'Resolution Time Breach',
            'sla_type='resolution_time',
            'severity='high',
            'alert_log': self.alert_log.id,
            'threshold_minutes=60,
            'breach_percentage=25.0,
            'status='active'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SLABreach.objects.count(), 2)
    
    def test_retrieve_sla_breach(self):
        """Test retrieving single SLA breach"""
        url = f'/api/alerts/reports/sla_breaches/{self.sla_breach.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Critical Response Time Breach')
    
    def test_acknowledge_sla_breach(self):
        """Test acknowledging SLA breach"""
        url = f'/api/alerts/reports/sla_breaches/{self.sla_breach.id}/acknowledge/'
        data = {
            'acknowledgment_note': 'Investigating the breach'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'acknowledged')
        self.assertEqual(self.sla_breach.acknowledged_by, self.user)
    
    def test_resolve_sla_breach(self):
        """Test resolving SLA breach"""
        url = f'/api/alerts/reports/sla_breaches/{self.sla_breach.id}/resolve/'
        data = {
            'resolution_note': 'Fixed the underlying issue',
            'resolution_actions': 'System capacity increased'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.status, 'resolved')
        self.assertEqual(self.sla_breach.resolved_by, self.user)
    
    def test_escalate_sla_breach(self):
        """Test escalating SLA breach"""
        url = f'/api/alerts/reports/sla_breaches/{self.sla_breach.id}/escalate/'
        data = {
            'escalation_reason': 'No response from primary team'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.sla_breach.refresh_from_db()
        self.assertEqual(self.sla_breach.escalation_level, 1)
        self.assertEqual(self.sla_breach.escalation_reason, 'No response from primary team')
    
    def test_get_breaches_by_severity(self):
        """Test getting breaches by severity"""
        url = '/api/alerts/reports/sla_breaches/by_severity/critical/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_breaches_by_type(self):
        """Test getting breaches by type"""
        url = '/api/alerts/reports/sla_breaches/by_type/response_time/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_breaches(self):
        """Test getting active breaches"""
        url = '/api/alerts/reports/sla_breaches/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_breach_statistics(self):
        """Test getting breach statistics"""
        url = '/api/alerts/reports/sla_breaches/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_breaches', response.data)
        self.assertIn('active_breaches', response.data)
        self.assertIn('resolved_breaches', response.data)
    
    def test_get_breach_impact_score(self):
        """Test getting breach impact score"""
        url = f'/api/alerts/reports/sla_breaches/{self.sla_breach.id}/impact_score/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('impact_score', response.data)


class ReportingDashboardViewSetTest(APITestCase):
    """Test cases for ReportingDashboardViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create some test data
        self.alert_report = AlertReport.objects.create(
            title='Daily Report',
            report_type='daily',
            status='completed',
            created_by=self.user
        )
        
        self.mttr_metric = MTTRMetric.objects.create(
            name='MTTR',
            calculation_period_days=30,
            target_mttr_minutes=60.0,
            current_mttr_minutes=45.0,
            created_by=self.user
        )
        
        self.sla_breach = SLABreach.objects.create(
            name='SLA Breach',
            sla_type='response_time',
            severity='high',
            status='active'
        )
    
    def test_get_dashboard_overview(self):
        """Test getting dashboard overview"""
        url = '/api/alerts/reports/dashboard/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('reports_summary', response.data)
        self.assertIn('mttr_summary', response.data)
        self.assertIn('sla_summary', response.data)
        self.assertIn('performance_metrics', response.data)
    
    def test_get_reports_summary(self):
        """Test getting reports summary"""
        url = '/api/alerts/reports/dashboard/reports_summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_reports', response.data)
        self.assertIn('completed_reports', response.data)
        self.assertIn('pending_reports', response.data)
        self.assertIn('failed_reports', response.data)
    
    def test_get_mttr_summary(self):
        """Test getting MTTR summary"""
        url = '/api/alerts/reports/dashboard/mttr_summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_mttr', response.data)
        self.assertIn('mttr_by_severity', response.data)
        self.assertIn('compliance_rate', response.data)
    
    def test_get_sla_summary(self):
        """Test getting SLA summary"""
        url = '/api/alerts/reports/dashboard/sla_summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_breaches', response.data)
        self.assertIn('active_breaches', response.data)
        self.assertIn('compliance_rate', response.data)
        self.assertIn('breach_trends', response.data)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        url = '/api/alerts/reports/dashboard/performance_metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('report_generation_time', response.data)
        self.assertIn('calculation_time', response.data)
        self.assertIn('data_volume', response.data)
    
    def test_get_recent_reports(self):
        """Test getting recent reports"""
        url = '/api/alerts/reports/dashboard/recent_reports/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recent_reports', response.data)
    
    def test_get_trending_metrics(self):
        """Test getting trending metrics"""
        url = '/api/alerts/reports/dashboard/trending_metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('mttr_trends', response.data)
        self.assertIn('sla_trends', response.data)
        self.assertIn('report_trends', response.data)
    
    def test_get_compliance_dashboard(self):
        """Test getting compliance dashboard"""
        url = '/api/alerts/reports/dashboard/compliance/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('mttr_compliance', response.data)
        self.assertIn('sla_compliance', response.data)
        self.assertIn('overall_compliance', response.data)
    
    def test_export_dashboard_data(self):
        """Test exporting dashboard data"""
        url = '/api/alerts/reports/dashboard/export/'
        data = {
            'export_format': 'csv',
            'include_reports': True,
            'include_mttr': True,
            'include_sla': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('export_result', response.data)
        self.assertIn('file_path', response.data)

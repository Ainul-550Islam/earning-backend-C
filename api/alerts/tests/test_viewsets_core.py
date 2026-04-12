"""
Tests for Core ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.viewsets.core import (
    AlertRuleViewSet, AlertLogViewSet, NotificationViewSet,
    SystemHealthViewSet, AlertOverviewViewSet, AlertMaintenanceViewSet
)

User = get_user_model()


class AlertRuleViewSetTest(APITestCase):
    """Test cases for AlertRuleViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15,
            cooldown_minutes=30,
            description='Test alert rule for CPU usage'
        )
    
    def test_list_alert_rules(self):
        """Test listing alert rules"""
        url = '/api/alerts/rules/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Alert Rule')
    
    def test_create_alert_rule(self):
        """Test creating alert rule"""
        url = '/api/alerts/rules/'
        data = {
            'name': 'New Alert Rule',
            'alert_type': 'memory_usage',
            'severity': 'medium',
            'threshold_value': 85.0,
            'time_window_minutes': 10,
            'cooldown_minutes': 15,
            'description': 'New alert rule for memory usage'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertRule.objects.count(), 2)
        
        new_rule = AlertRule.objects.get(name='New Alert Rule')
        self.assertEqual(new_rule.alert_type, 'memory_usage')
        self.assertEqual(new_rule.severity, 'medium')
    
    def test_retrieve_alert_rule(self):
        """Test retrieving single alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Alert Rule')
        self.assertEqual(response.data['alert_type'], 'cpu_usage')
    
    def test_update_alert_rule(self):
        """Test updating alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/'
        data = {
            'name': 'Updated Alert Rule',
            'severity': 'critical',
            'threshold_value': 90.0
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_rule.refresh_from_db()
        self.assertEqual(self.alert_rule.name, 'Updated Alert Rule')
        self.assertEqual(self.alert_rule.severity, 'critical')
        self.assertEqual(self.alert_rule.threshold_value, 90.0)
    
    def test_delete_alert_rule(self):
        """Test deleting alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AlertRule.objects.count(), 0)
    
    def test_activate_alert_rule(self):
        """Test activating alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_rule.refresh_from_db()
        self.assertTrue(self.alert_rule.is_active)
    
    def test_deactivate_alert_rule(self):
        """Test deactivating alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_rule.refresh_from_db()
        self.assertFalse(self.alert_rule.is_active)
    
    def test_test_alert_rule(self):
        """Test testing alert rule"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/test/'
        data = {
            'test_value': 85.0,
            'message': 'Test alert'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('alert_id', response.data)
        self.assertIn('test_result', response.data)
    
    def test_get_alert_rule_statistics(self):
        """Test getting alert rule statistics"""
        url = f'/api/alerts/rules/{self.alert_rule.id}/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_alerts', response.data)
        self.assertIn('resolution_rate', response.data)
        self.assertIn('avg_resolution_time', response.data)


class AlertLogViewSetTest(APITestCase):
    """Test cases for AlertLogViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details={'current_usage': 85.0}
        )
    
    def test_list_alert_logs(self):
        """Test listing alert logs"""
        url = '/api/alerts/logs/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['message'], 'CPU usage is high')
    
    def test_create_alert_log(self):
        """Test creating alert log"""
        url = '/api/alerts/logs/'
        data = {
            'rule': self.alert_rule.id,
            'trigger_value': 90.0,
            'threshold_value': 80.0,
            'message': 'High CPU usage detected',
            'details': {'current_usage': 90.0}
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertLog.objects.count(), 2)
    
    def test_retrieve_alert_log(self):
        """Test retrieving single alert log"""
        url = f'/api/alerts/logs/{self.alert_log.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'CPU usage is high')
    
    def test_resolve_alert_log(self):
        """Test resolving alert log"""
        url = f'/api/alerts/logs/{self.alert_log.id}/resolve/'
        data = {
            'resolution_note': 'Fixed the CPU issue'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_log.refresh_from_db()
        self.assertTrue(self.alert_log.is_resolved)
        self.assertEqual(self.alert_log.resolution_note, 'Fixed the CPU issue')
    
    def test_acknowledge_alert_log(self):
        """Test acknowledging alert log"""
        url = f'/api/alerts/logs/{self.alert_log.id}/acknowledge/'
        data = {
            'acknowledgment_note': 'Investigating the issue'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_log.refresh_from_db()
        self.assertIsNotNone(self.alert_log.acknowledged_at)
    
    def test_get_alert_logs_by_rule(self):
        """Test getting alert logs by rule"""
        url = f'/api/alerts/logs/by_rule/{self.alert_rule.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_pending_alerts(self):
        """Test getting pending alerts"""
        url = '/api/alerts/logs/pending/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_resolved_alerts(self):
        """Test getting resolved alerts"""
        url = '/api/alerts/logs/resolved/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_get_alert_logs_by_severity(self):
        """Test getting alert logs by severity"""
        url = '/api/alerts/logs/by_severity/high/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_alert_logs_by_date_range(self):
        """Test getting alert logs by date range"""
        start_date = timezone.now().date() - timezone.timedelta(days=1)
        end_date = timezone.now().date()
        
        url = f'/api/alerts/logs/by_date_range/?start_date={start_date}&end_date={end_date}'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class NotificationViewSetTest(APITestCase):
    """Test cases for NotificationViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )
        
        self.notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='pending'
        )
    
    def test_list_notifications(self):
        """Test listing notifications"""
        url = '/api/alerts/notifications/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['notification_type'], 'email')
    
    def test_create_notification(self):
        """Test creating notification"""
        url = '/api/alerts/notifications/'
        data = {
            'alert_log': self.alert_log.id,
            'notification_type': 'sms',
            'recipient': '+1234567890',
            'status': 'pending'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.count(), 2)
    
    def test_retrieve_notification(self):
        """Test retrieving single notification"""
        url = f'/api/alerts/notifications/{self.notification.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['notification_type'], 'email')
    
    def test_mark_notification_sent(self):
        """Test marking notification as sent"""
        url = f'/api/alerts/notifications/{self.notification.id}/mark_sent/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, 'sent')
        self.assertIsNotNone(self.notification.sent_at)
    
    def test_mark_notification_failed(self):
        """Test marking notification as failed"""
        url = f'/api/alerts/notifications/{self.notification.id}/mark_failed/'
        data = {
            'error_message': 'SMTP server error'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, 'failed')
        self.assertEqual(self.notification.error_message, 'SMTP server error')
    
    def test_retry_notification(self):
        """Test retrying notification"""
        url = f'/api/alerts/notifications/{self.notification.id}/retry/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('retry_result', response.data)
    
    def test_get_notifications_by_status(self):
        """Test getting notifications by status"""
        url = '/api/alerts/notifications/by_status/pending/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_notifications_by_type(self):
        """Test getting notifications by type"""
        url = '/api/alerts/notifications/by_type/email/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_failed_notifications(self):
        """Test getting failed notifications"""
        # Create a failed notification
        failed_notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='sms',
            recipient='+1234567890',
            status='failed',
            error_message='SMS gateway error'
        )
        
        url = '/api/alerts/notifications/failed/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class SystemHealthViewSetTest(APITestCase):
    """Test cases for SystemHealthViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_system_health(self):
        """Test getting system health"""
        url = '/api/alerts/health/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_health', response.data)
        self.assertIn('alerts_health', response.data)
        self.assertIn('channels_health', response.data)
        self.assertIn('incidents_health', response.data)
    
    def test_get_health_metrics(self):
        """Test getting health metrics"""
        url = '/api/alerts/health/metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_rules', response.data)
        self.assertIn('active_rules', response.data)
        self.assertIn('total_alerts', response.data)
        self.assertIn('resolved_alerts', response.data)
    
    def test_get_health_history(self):
        """Test getting health history"""
        url = '/api/alerts/health/history/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('history', response.data)
    
    def test_run_health_check(self):
        """Test running health check"""
        url = '/api/alerts/health/check/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('check_result', response.data)
        self.assertIn('timestamp', response.data)
    
    def test_get_alert_rules_health(self):
        """Test getting alert rules health"""
        url = '/api/alerts/health/rules/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_rules', response.data)
        self.assertIn('active_rules', response.data)
        self.assertIn('rules_with_recent_activity', response.data)
    
    def test_get_channels_health(self):
        """Test getting channels health"""
        url = '/api/alerts/health/channels/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_channels', response.data)
        self.assertIn('healthy_channels', response.data)
        self.assertIn('channels_with_recent_health_checks', response.data)
    
    def test_get_incidents_health(self):
        """Test getting incidents health"""
        url = '/api/alerts/health/incidents/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_incidents', response.data)
        self.assertIn('resolved_incidents', response.data)
        self.assertIn('avg_resolution_time', response.data)


class AlertOverviewViewSetTest(APITestCase):
    """Test cases for AlertOverviewViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )
        
        self.system_metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
    
    def test_get_dashboard_overview(self):
        """Test getting dashboard overview"""
        url = '/api/alerts/overview/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('recent_alerts', response.data)
        self.assertIn('system_metrics', response.data)
        self.assertIn('health_status', response.data)
    
    def test_get_alert_summary(self):
        """Test getting alert summary"""
        url = '/api/alerts/overview/summary/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_alerts', response.data)
        self.assertIn('pending_alerts', response.data)
        self.assertIn('resolved_alerts', response.data)
        self.assertIn('resolution_rate', response.data)
    
    def test_get_recent_alerts(self):
        """Test getting recent alerts"""
        url = '/api/alerts/overview/recent_alerts/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_alert_trends(self):
        """Test getting alert trends"""
        url = '/api/alerts/overview/trends/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('daily_trends', response.data)
        self.assertIn('severity_trends', response.data)
    
    def test_get_top_alert_rules(self):
        """Test getting top alert rules"""
        url = '/api/alerts/overview/top_rules/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('top_rules', response.data)
    
    def test_get_system_metrics(self):
        """Test getting system metrics"""
        url = '/api/alerts/overview/metrics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)
        self.assertIn('active_users_1h', response.data)
        self.assertIn('total_earnings_1h', response.data)
        self.assertIn('avg_response_time_ms', response.data)
    
    def test_get_alert_statistics(self):
        """Test getting alert statistics"""
        url = '/api/alerts/overview/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('by_severity', response.data)
        self.assertIn('by_type', response.data)
        self.assertIn('by_status', response.data)


class AlertMaintenanceViewSetTest(APITestCase):
    """Test cases for AlertMaintenanceViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def test_list_maintenance_windows(self):
        """Test listing maintenance windows"""
        url = '/api/alerts/maintenance/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_maintenance_window(self):
        """Test creating maintenance window"""
        url = '/api/alerts/maintenance/'
        data = {
            'title': 'System Maintenance',
            'description': 'Scheduled system maintenance',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timezone.timedelta(hours=2)).isoformat(),
            'maintenance_type': 'scheduled',
            'severity': 'medium',
            'affected_services': ['api', 'database'],
            'is_active': True
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_suppress_alerts_during_maintenance(self):
        """Test suppressing alerts during maintenance"""
        url = '/api/alerts/maintenance/suppress_alerts/'
        data = {
            'maintenance_id': 1,
            'rule_ids': [self.alert_rule.id],
            'suppression_reason': 'Maintenance in progress'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suppressed_count', response.data)
    
    def test_get_maintenance_impact(self):
        """Test getting maintenance impact"""
        url = '/api/alerts/maintenance/impact/'
        data = {
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timezone.timedelta(hours=2)).isoformat(),
            'affected_services': ['api', 'database']
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('affected_rules', response.data)
        self.assertIn('estimated_alerts', response.data)
    
    def test_extend_maintenance_window(self):
        """Test extending maintenance window"""
        url = '/api/alerts/maintenance/1/extend/'
        data = {
            'new_end_time': (timezone.now() + timezone.timedelta(hours=4)).isoformat(),
            'reason': 'Maintenance taking longer than expected'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_complete_maintenance_window(self):
        """Test completing maintenance window"""
        url = '/api/alerts/maintenance/1/complete/'
        data = {
            'completion_note': 'Maintenance completed successfully',
            'actual_end_time': timezone.now().isoformat()
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_maintenance_history(self):
        """Test getting maintenance history"""
        url = '/api/alerts/maintenance/history/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('history', response.data)
    
    def test_get_upcoming_maintenance(self):
        """Test getting upcoming maintenance"""
        url = '/api/alerts/maintenance/upcoming/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('upcoming', response.data)

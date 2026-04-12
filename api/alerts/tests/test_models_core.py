"""
Tests for Core Alert Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import json

from alerts.models.core import (
    AlertRule, AlertLog, Notification, AlertEscalation, AlertTemplate,
    AlertAnalytics, AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)

User = get_user_model()


class AlertRuleModelTest(TestCase):
    """Test cases for AlertRule model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15,
            cooldown_minutes=30,
            description='Test alert rule for CPU usage'
        )
    
    def test_alert_rule_creation(self):
        """Test AlertRule creation"""
        self.assertEqual(self.alert_rule.name, 'Test Alert Rule')
        self.assertEqual(self.alert_rule.alert_type, 'cpu_usage')
        self.assertEqual(self.alert_rule.severity, 'high')
        self.assertEqual(self.alert_rule.threshold_value, 80.0)
        self.assertTrue(self.alert_rule.is_active)
        self.assertIsNotNone(self.alert_rule.created_at)
    
    def test_alert_rule_str_representation(self):
        """Test AlertRule string representation"""
        expected = 'Test Alert Rule (cpu_usage - high)'
        self.assertEqual(str(self.alert_rule), expected)
    
    def test_alert_rule_get_severity_display(self):
        """Test AlertRule severity display"""
        self.assertEqual(self.alert_rule.get_severity_display(), 'High')
    
    def test_alert_rule_get_alert_type_display(self):
        """Test AlertRule alert type display"""
        self.assertEqual(self.alert_rule.get_alert_type_display(), 'CPU Usage')
    
    def test_alert_rule_trigger_alert(self):
        """Test AlertRule trigger alert method"""
        alert = self.alert_rule.trigger_alert(
            trigger_value=85.0,
            message='CPU usage is high',
            details={'current_usage': 85.0, 'threshold': 80.0}
        )
        
        self.assertIsInstance(alert, AlertLog)
        self.assertEqual(alert.rule, self.alert_rule)
        self.assertEqual(alert.trigger_value, 85.0)
        self.assertEqual(alert.threshold_value, 80.0)
        self.assertEqual(alert.message, 'CPU usage is high')
        self.assertFalse(alert.is_resolved)
    
    def test_alert_rule_check_cooldown(self):
        """Test AlertRule cooldown check"""
        # Test when no last triggered time
        self.assertTrue(self.alert_rule.check_cooldown())
        
        # Test when within cooldown period
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.alert_rule.save()
        self.assertFalse(self.alert_rule.check_cooldown())
        
        # Test when cooldown period has passed
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=40)
        self.alert_rule.save()
        self.assertTrue(self.alert_rule.check_cooldown())
    
    def test_alert_rule_should_trigger(self):
        """Test AlertRule should trigger logic"""
        # Test with value above threshold
        self.assertTrue(self.alert_rule.should_trigger(85.0))
        
        # Test with value below threshold
        self.assertFalse(self.alert_rule.should_trigger(75.0))
        
        # Test within cooldown
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.alert_rule.save()
        self.assertFalse(self.alert_rule.should_trigger(85.0))
    
    def test_alert_rule_get_recent_alerts(self):
        """Test AlertRule get recent alerts"""
        # Create some alerts
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Test alert {i}'
            )
        
        recent_alerts = self.alert_rule.get_recent_alerts(hours=24)
        self.assertEqual(recent_alerts.count(), 5)
    
    def test_alert_rule_get_success_rate(self):
        """Test AlertRule success rate calculation"""
        # Create some alerts with different statuses
        for i in range(3):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Test alert {i}',
                is_resolved=i < 2  # First 2 are resolved
            )
        
        success_rate = self.alert_rule.get_success_rate()
        self.assertEqual(success_rate, 66.67)  # 2/3 * 100


class AlertLogModelTest(TestCase):
    """Test cases for AlertLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details={'current_usage': 85.0}
        )
    
    def test_alert_log_creation(self):
        """Test AlertLog creation"""
        self.assertEqual(self.alert_log.rule, self.alert_rule)
        self.assertEqual(self.alert_log.trigger_value, 85.0)
        self.assertEqual(self.alert_log.threshold_value, 80.0)
        self.assertEqual(self.alert_log.message, 'CPU usage is high')
        self.assertFalse(self.alert_log.is_resolved)
        self.assertIsNotNone(self.alert_log.triggered_at)
    
    def test_alert_log_str_representation(self):
        """Test AlertLog string representation"""
        expected = f'AlertLog: {self.alert_log.id} - Test Alert Rule'
        self.assertEqual(str(self.alert_log), expected)
    
    def test_alert_log_resolve(self):
        """Test AlertLog resolve method"""
        self.alert_log.resolve(self.user, 'Fixed the issue')
        
        self.assertTrue(self.alert_log.is_resolved)
        self.assertEqual(self.alert_log.resolved_by, self.user)
        self.assertEqual(self.alert_log.resolution_note, 'Fixed the issue')
        self.assertIsNotNone(self.alert_log.resolved_at)
    
    def test_alert_log_get_resolution_time(self):
        """Test AlertLog resolution time calculation"""
        # Test unresolved alert
        self.assertIsNone(self.alert_log.get_resolution_time())
        
        # Test resolved alert
        self.alert_log.triggered_at = timezone.now() - timedelta(minutes=30)
        self.alert_log.resolved_at = timezone.now() - timedelta(minutes=10)
        self.alert_log.save()
        
        resolution_time = self.alert_log.get_resolution_time()
        self.assertEqual(resolution_time, timedelta(minutes=20))
    
    def test_alert_log_get_age(self):
        """Test AlertLog age calculation"""
        self.alert_log.triggered_at = timezone.now() - timedelta(hours=2)
        self.alert_log.save()
        
        age = self.alert_log.get_age()
        self.assertEqual(age, timedelta(hours=2))
    
    def test_alert_log_get_exceed_percentage(self):
        """Test AlertLog exceed percentage calculation"""
        # Test with value above threshold
        exceed_percentage = self.alert_log.get_exceed_percentage()
        expected = ((85.0 - 80.0) / 80.0) * 100
        self.assertEqual(exceed_percentage, expected)
        
        # Test with value below threshold
        self.alert_log.trigger_value = 75.0
        self.alert_log.save()
        exceed_percentage = self.alert_log.get_exceed_percentage()
        self.assertEqual(exceed_percentage, 0)
    
    def test_alert_log_get_severity_display(self):
        """Test AlertLog severity display"""
        self.assertEqual(self.alert_log.get_severity_display(), 'High')
    
    def test_alert_log_get_status_display(self):
        """Test AlertLog status display"""
        self.assertEqual(self.alert_log.get_status_display(), 'Pending')
        
        self.alert_log.is_resolved = True
        self.alert_log.save()
        self.assertEqual(self.alert_log.get_status_display(), 'Resolved')


class NotificationModelTest(TestCase):
    """Test cases for Notification model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15
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
    
    def test_notification_creation(self):
        """Test Notification creation"""
        self.assertEqual(self.notification.alert_log, self.alert_log)
        self.assertEqual(self.notification.notification_type, 'email')
        self.assertEqual(self.notification.recipient, 'test@example.com')
        self.assertEqual(self.notification.status, 'pending')
        self.assertIsNotNone(self.notification.created_at)
    
    def test_notification_str_representation(self):
        """Test Notification string representation"""
        expected = f'Notification: {self.notification.id} - email to test@example.com'
        self.assertEqual(str(self.notification), expected)
    
    def test_notification_mark_sent(self):
        """Test Notification mark sent method"""
        self.notification.mark_sent()
        
        self.assertEqual(self.notification.status, 'sent')
        self.assertIsNotNone(self.notification.sent_at)
    
    def test_notification_mark_failed(self):
        """Test Notification mark failed method"""
        self.notification.mark_failed('SMTP server error')
        
        self.assertEqual(self.notification.status, 'failed')
        self.assertEqual(self.notification.error_message, 'SMTP server error')
        self.assertIsNotNone(self.notification.failed_at)
    
    def test_notification_get_status_display(self):
        """Test Notification status display"""
        self.assertEqual(self.notification.get_status_display(), 'Pending')
        
        self.notification.status = 'sent'
        self.assertEqual(self.notification.get_status_display(), 'Sent')
        
        self.notification.status = 'failed'
        self.assertEqual(self.notification.get_status_display(), 'Failed')
    
    def test_notification_get_type_display(self):
        """Test Notification type display"""
        self.assertEqual(self.notification.get_type_display(), 'Email')
        
        self.notification.notification_type = 'sms'
        self.assertEqual(self.notification.get_type_display(), 'SMS')
        
        self.notification.notification_type = 'telegram'
        self.assertEqual(self.notification.get_type_display(), 'Telegram')


class AlertGroupModelTest(TestCase):
    """Test cases for AlertGroup model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_group = AlertGroup.objects.create(
            name='CPU Usage Alerts',
            description='Group for CPU usage related alerts',
            group_type='correlation',
            severity='high'
        )
    
    def test_alert_group_creation(self):
        """Test AlertGroup creation"""
        self.assertEqual(self.alert_group.name, 'CPU Usage Alerts')
        self.assertEqual(self.alert_group.group_type, 'correlation')
        self.assertEqual(self.alert_group.severity, 'high')
        self.assertTrue(self.alert_group.is_active)
        self.assertIsNotNone(self.alert_group.created_at)
    
    def test_alert_group_str_representation(self):
        """Test AlertGroup string representation"""
        expected = 'AlertGroup: CPU Usage Alerts (correlation)'
        self.assertEqual(str(self.alert_group), expected)
    
    def test_alert_group_add_alert(self):
        """Test AlertGroup add alert method"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_group.add_alert(alert_rule)
        self.assertIn(alert_rule, self.alert_group.rules.all())
    
    def test_alert_group_remove_alert(self):
        """Test AlertGroup remove alert method"""
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_group.add_alert(alert_rule)
        self.alert_group.remove_alert(alert_rule)
        self.assertNotIn(alert_rule, self.alert_group.rules.all())
    
    def test_alert_group_get_alert_count(self):
        """Test AlertGroup get alert count"""
        self.assertEqual(self.alert_group.get_alert_count(), 0)
        
        alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_group.add_alert(alert_rule)
        self.assertEqual(self.alert_group.get_alert_count(), 1)
    
    def test_alert_group_get_severity_display(self):
        """Test AlertGroup severity display"""
        self.assertEqual(self.alert_group.get_severity_display(), 'High')
    
    def test_alert_group_get_type_display(self):
        """Test AlertGroup type display"""
        self.assertEqual(self.alert_group.get_type_display(), 'Correlation')


class SystemMetricsModelTest(TestCase):
    """Test cases for SystemMetrics model"""
    
    def test_system_metrics_creation(self):
        """Test SystemMetrics creation"""
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
        
        self.assertEqual(metrics.total_users, 1000)
        self.assertEqual(metrics.active_users_1h, 500)
        self.assertEqual(metrics.total_earnings_1h, 1000.0)
        self.assertEqual(metrics.avg_response_time_ms, 200.0)
        self.assertIsNotNone(metrics.timestamp)
    
    def test_system_metrics_str_representation(self):
        """Test SystemMetrics string representation"""
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            avg_response_time_ms=200.0
        )
        
        expected = f'SystemMetrics: {metrics.timestamp}'
        self.assertEqual(str(metrics), expected)
    
    def test_system_metrics_get_health_status(self):
        """Test SystemMetrics health status"""
        # Healthy metrics
        metrics = SystemMetrics.objects.create(
            avg_response_time_ms=200.0,
            error_count_1h=2
        )
        
        health_status = metrics.get_health_status()
        self.assertEqual(health_status, 'healthy')
        
        # Warning metrics
        metrics.avg_response_time_ms=800.0
        metrics.error_count_1h=8
        metrics.save()
        
        health_status = metrics.get_health_status()
        self.assertEqual(health_status, 'warning')
        
        # Critical metrics
        metrics.avg_response_time_ms=1200.0
        metrics.error_count_1h=15
        metrics.save()
        
        health_status = metrics.get_health_status()
        self.assertEqual(health_status, 'critical')

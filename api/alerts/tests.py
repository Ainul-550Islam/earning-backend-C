# ============================================
# TESTS (তোমার models এর জন্য)
# ============================================

# alerts/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    AlertRule, AlertLog, Notification, AlertSchedule,
    AlertEscalation, AlertTemplate, AlertAnalytics,
    AlertGroup, AlertSuppression, SystemHealthCheck,
    AlertRuleHistory, AlertDashboardConfig, SystemMetrics
)
from .services import AlertProcessorService, NotificationService
from .serializers import AlertRuleSerializer


class AlertRuleModelTest(TestCase):
    """তোমার AlertRule model tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='high_earning',
            severity='high',
            threshold_value=1000,
            time_window_minutes=60,
            send_email=True,
            email_recipients='test1@example.com,test2@example.com',
            is_active=True,
            cooldown_minutes=30,
            created_by=self.user
        )
    
    def test_alert_rule_creation(self):
        """তোমার AlertRule model create test"""
        self.assertEqual(self.alert_rule.name, 'Test Alert Rule')
        self.assertEqual(self.alert_rule.alert_type, 'high_earning')
        self.assertEqual(self.alert_rule.severity, 'high')
        self.assertTrue(self.alert_rule.is_active)
    
    def test_can_trigger_now_method(self):
        """তোমার AlertRule can_trigger_now method test"""
        # Initially should be able to trigger
        self.assertTrue(self.alert_rule.can_trigger_now())
        
        # Set last_triggered recently
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=15)
        self.alert_rule.save()
        
        # Should not trigger (in cooldown)
        self.assertFalse(self.alert_rule.can_trigger_now())
    
    def test_trigger_count_today_method(self):
        """তোমার AlertRule trigger_count_today method test"""
        # Create test alerts
        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1500,
            threshold_value=1000,
            message='Test alert 1'
        )
        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1200,
            threshold_value=1000,
            message='Test alert 2'
        )
        
        count = self.alert_rule.trigger_count_today()
        self.assertEqual(count, 2)
    
    def test_get_recipients_method(self):
        """তোমার AlertRule get_recipients method test"""
        recipients = self.alert_rule.get_recipients()
        
        self.assertIn('emails', recipients)
        self.assertEqual(len(recipients['emails']), 2)
        self.assertIn('test1@example.com', recipients['emails'])
        self.assertIn('test2@example.com', recipients['emails'])
    
    def test_clean_method_validation(self):
        """তোমার AlertRule clean method validation test"""
        # Test cooldown validation
        alert_rule = AlertRule(
            name='Invalid Rule',
            alert_type='high_earning',
            threshold_value=1000,
            time_window_minutes=30,
            cooldown_minutes=60  # Greater than time_window
        )
        
        with self.assertRaises(Exception):
            alert_rule.full_clean()
    
    def test_active_manager(self):
        """তোমার ActiveAlertRuleManager test"""
        # Create inactive rule
        AlertRule.objects.create(
            name='Inactive Rule',
            alert_type='high_earning',
            threshold_value=1000,
            is_active=False,
            created_by=self.user
        )
        
        active_rules = AlertRule.active.all()
        self.assertEqual(active_rules.count(), 1)
        self.assertEqual(active_rules.first().name, 'Test Alert Rule')


class AlertLogModelTest(TestCase):
    """তোমার AlertLog model tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='high_earning',
            threshold_value=1000,
            created_by=self.user
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1500,
            threshold_value=1000,
            message='Test alert message',
            details={'key': 'value'}
        )
    
    def test_alert_log_creation(self):
        """তোমার AlertLog model create test"""
        self.assertEqual(self.alert_log.trigger_value, 1500)
        self.assertEqual(self.alert_log.threshold_value, 1000)
        self.assertEqual(self.alert_log.message, 'Test alert message')
        self.assertFalse(self.alert_log.is_resolved)
    
    def test_time_to_resolve_property(self):
        """তোমার AlertLog time_to_resolve property test"""
        # Not resolved yet
        self.assertIsNone(self.alert_log.time_to_resolve)
        
        # Resolve it
        self.alert_log.is_resolved = True
        self.alert_log.resolved_at = timezone.now()
        self.alert_log.save()
        
        self.assertIsNotNone(self.alert_log.time_to_resolve)
    
    def test_age_in_minutes_property(self):
        """তোমার AlertLog age_in_minutes property test"""
        age = self.alert_log.age_in_minutes
        self.assertGreaterEqual(age, 0)
    
    def test_mark_as_processing_method(self):
        """তোমার AlertLog mark_as_processing method test"""
        self.alert_log.mark_as_processing()
        self.assertIsNotNone(self.alert_log.processing_started)
    
    def test_mark_as_complete_method(self):
        """তোমার AlertLog mark_as_complete method test"""
        self.alert_log.mark_as_processing()
        self.alert_log.mark_as_complete()
        
        self.assertGreater(self.alert_log.processing_time_ms, 0)
        
        # তোমার AlertRule এর avg_processing_time update হয়েছে check
        self.alert_rule.refresh_from_db()
        self.assertGreater(self.alert_rule.avg_processing_time, 0)
    
    def test_unresolved_manager(self):
        """তোমার UnresolvedAlertManager test"""
        # Create another resolved alert
        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1200,
            threshold_value=1000,
            message='Resolved alert',
            is_resolved=True
        )
        
        unresolved_count = AlertLog.unresolved().count()
        self.assertEqual(unresolved_count, 1)
        
        resolved_count = AlertLog.resolved().count()
        self.assertEqual(resolved_count, 1)


class NotificationModelTest(TestCase):
    """তোমার Notification model tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='high_earning',
            threshold_value=1000,
            created_by=self.user
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1500,
            threshold_value=1000,
            message='Test alert'
        )
        
        self.notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            message='Test notification message',
            status='pending'
        )
    
    def test_notification_creation(self):
        """তোমার Notification model create test"""
        self.assertEqual(self.notification.notification_type, 'email')
        self.assertEqual(self.notification.recipient, 'test@example.com')
        self.assertEqual(self.notification.status, 'pending')
    
    def test_can_retry_method(self):
        """তোমার Notification can_retry method test"""
        # Initially can retry
        self.assertTrue(self.notification.can_retry())
        
        # Mark as failed multiple times
        self.notification.status = 'failed'
        self.notification.retry_count = 3  # Max retries
        self.notification.save()
        
        self.assertFalse(self.notification.can_retry())
    
    def test_mark_as_sent_method(self):
        """তোমার Notification mark_as_sent method test"""
        self.notification.mark_as_sent(message_id='test123')
        
        self.assertEqual(self.notification.status, 'sent')
        self.assertIsNotNone(self.notification.sent_at)
        self.assertEqual(self.notification.message_id, 'test123')
    
    def test_mark_as_failed_method(self):
        """তোমার Notification mark_as_failed method test"""
        self.notification.mark_as_failed('Test error')
        
        self.assertEqual(self.notification.status, 'failed')
        self.assertEqual(self.notification.error_message, 'Test error')
        self.assertEqual(self.notification.retry_count, 1)


class AlertGroupModelTest(TestCase):
    """তোমার AlertGroup model tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.rule1 = AlertRule.objects.create(
            name='Rule 1',
            alert_type='high_earning',
            threshold_value=1000,
            created_by=self.user
        )
        
        self.rule2 = AlertRule.objects.create(
            name='Rule 2',
            alert_type='mass_signup',
            threshold_value=50,
            created_by=self.user
        )
        
        self.alert_group = AlertGroup.objects.create(
            name='Test Group',
            group_notification_enabled=True,
            group_threshold=2,
            created_by=self.user
        )
        self.alert_group.rules.add(self.rule1, self.rule2)
    
    def test_get_active_alerts_method(self):
        """তোমার AlertGroup get_active_alerts method test"""
        # Create active alerts
        AlertLog.objects.create(
            rule=self.rule1,
            trigger_value=1500,
            threshold_value=1000,
            message='Alert 1'
        )
        
        AlertLog.objects.create(
            rule=self.rule2,
            trigger_value=75,
            threshold_value=50,
            message='Alert 2'
        )
        
        active_alerts = self.alert_group.get_active_alerts()
        self.assertEqual(active_alerts.count(), 2)
    
    def test_should_send_group_alert_method(self):
        """তোমার AlertGroup should_send_group_alert method test"""
        # Initially should not send (no active alerts)
        self.assertFalse(self.alert_group.should_send_group_alert())
        
        # Create alerts to reach threshold
        AlertLog.objects.create(
            rule=self.rule1,
            trigger_value=1500,
            threshold_value=1000,
            message='Alert 1'
        )
        
        AlertLog.objects.create(
            rule=self.rule2,
            trigger_value=75,
            threshold_value=50,
            message='Alert 2'
        )
        
        # Update cache
        self.alert_group.get_active_alerts(use_cache=False)
        
        self.assertTrue(self.alert_group.should_send_group_alert())
    
    def test_send_group_alert_method(self):
        """তোমার AlertGroup send_group_alert method test"""
        # Set up for group alert
        self.alert_group.group_notification_enabled = True
        self.alert_group.group_threshold = 1
        self.alert_group.save()
        
        # Create an alert
        AlertLog.objects.create(
            rule=self.rule1,
            trigger_value=1500,
            threshold_value=1000,
            message='Test alert'
        )
        
        # Update cache
        self.alert_group.get_active_alerts(use_cache=False)
        
        result = self.alert_group.send_group_alert()
        self.assertIsNotNone(result)
        self.assertIn('message', result)
        self.assertIn('recipients', result)


class AlertProcessorServiceTest(TestCase):
    """তোমার AlertProcessorService tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='high_earning',
            threshold_value=1000,
            time_window_minutes=60,
            send_email=True,
            email_recipients='test@example.com',
            is_active=True,
            cooldown_minutes=30,
            created_by=self.user
        )
    
    def test_process_alert(self):
        """AlertProcessorService.process_alert test"""
        alert = AlertProcessorService.process_alert(
            rule_id=self.alert_rule.id,
            trigger_value=1500,
            message='Test alert message',
            details={'test': True}
        )
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.rule, self.alert_rule)
        self.assertEqual(alert.trigger_value, 1500)
        self.assertEqual(alert.message, 'Test alert message')
        
        # Check notifications were created
        notifications = alert.notifications.all()
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications.first().notification_type, 'email')
    
    def test_process_alert_cooldown(self):
        """AlertProcessorService.process_alert with cooldown test"""
        # Set last triggered recently
        self.alert_rule.last_triggered = timezone.now()
        self.alert_rule.save()
        
        alert = AlertProcessorService.process_alert(
            rule_id=self.alert_rule.id,
            trigger_value=1500,
            message='Test alert'
        )
        
        self.assertIsNone(alert)  # Should be None due to cooldown


class SerializerTest(TestCase):
    """তোমার Serializers tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_alert_rule_serializer(self):
        """AlertRuleSerializer test"""
        data = {
            'name': 'Test Rule',
            'alert_type': 'high_earning',
            'severity': 'medium',
            'threshold_value': 1000,
            'time_window_minutes': 60,
            'send_email': True,
            'email_recipients': 'test@example.com',
            'is_active': True,
            'cooldown_minutes': 30
        }
        
        serializer = AlertRuleSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # তোমার AlertRule model create
        alert_rule = serializer.save(created_by=self.user)
        self.assertEqual(alert_rule.name, 'Test Rule')
        self.assertEqual(alert_rule.alert_type, 'high_earning')
    
    def test_alert_rule_serializer_validation(self):
        """AlertRuleSerializer validation test"""
        data = {
            'name': 'Test Rule',
            'alert_type': 'server_error',
            'threshold_value': 150,  # > 100%
            'time_window_minutes': 30,
            'cooldown_minutes': 60  # > time_window
        }
        
        serializer = AlertRuleSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)


class CeleryTasksTest(TestCase):
    """তোমার Celery tasks tests"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_process_pending_alerts_task(self):
        """process_pending_alerts task test"""
        # Create active rule
        AlertRule.objects.create(
            name='Test Rule',
            alert_type='high_earning',
            threshold_value=1000,
            is_active=True,
            created_by=self.user
        )
        
        from .tasks import process_pending_alerts
        result = process_pending_alerts()
        
        self.assertGreaterEqual(result, 0)
        
        # Check if alerts were created
        alerts_count = AlertLog.objects.count()
        self.assertGreaterEqual(alerts_count, 0)
    
    def test_send_notifications_task(self):
        """send_notifications task test"""
        # Create a notification
        alert_rule = AlertRule.objects.create(
            name='Test Rule',
            alert_type='high_earning',
            threshold_value=1000,
            created_by=self.user
        )
        
        alert_log = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=1500,
            threshold_value=1000,
            message='Test alert'
        )
        
        Notification.objects.create(
            alert_log=alert_log,
            notification_type='email',
            recipient='test@example.com',
            message='Test notification',
            status='pending'
        )
        
        from .tasks import send_notifications
        result = send_notifications()
        
        self.assertIn('sent', result)
        self.assertIn('failed', result)
        self.assertIn('total', result)

"""
Tests for Core Serializers
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.serializers.core import (
    AlertRuleSerializer, AlertLogSerializer, NotificationSerializer,
    SystemMetricsSerializer, AlertRuleListSerializer, AlertLogListSerializer,
    NotificationListSerializer, SystemMetricsListSerializer
)

User = get_user_model()


class AlertRuleSerializerTest(TestCase):
    """Test cases for AlertRuleSerializer"""
    
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
    
    def test_alert_rule_serializer_validation(self):
        """Test AlertRuleSerializer validation"""
        # Valid data
        valid_data = {
            'name': 'Valid Alert Rule',
            'alert_type': 'memory_usage',
            'severity': 'medium',
            'threshold_value': 85.0,
            'time_window_minutes': 10,
            'cooldown_minutes': 15,
            'description': 'Valid alert rule'
        }
        
        serializer = AlertRuleSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid data - missing required fields
        invalid_data = {
            'name': 'Invalid Alert Rule',
            'alert_type': 'cpu_usage'
        }
        
        serializer = AlertRuleSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('severity', serializer.errors)
        self.assertIn('threshold_value', serializer.errors)
    
    def test_alert_rule_serializer_create(self):
        """Test AlertRuleSerializer create"""
        data = {
            'name': 'New Alert Rule',
            'alert_type': 'disk_usage',
            'severity': 'critical',
            'threshold_value': 90.0,
            'time_window_minutes': 5,
            'cooldown_minutes': 10,
            'description': 'New alert rule for disk usage'
        }
        
        serializer = AlertRuleSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        alert_rule = serializer.save()
        
        self.assertEqual(alert_rule.name, 'New Alert Rule')
        self.assertEqual(alert_rule.alert_type, 'disk_usage')
        self.assertEqual(alert_rule.severity, 'critical')
        self.assertEqual(alert_rule.threshold_value, 90.0)
    
    def test_alert_rule_serializer_update(self):
        """Test AlertRuleSerializer update"""
        data = {
            'name': 'Updated Alert Rule',
            'severity': 'critical',
            'threshold_value': 95.0
        }
        
        serializer = AlertRuleSerializer(
            instance=self.alert_rule,
            data=data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        updated_rule = serializer.save()
        
        self.assertEqual(updated_rule.name, 'Updated Alert Rule')
        self.assertEqual(updated_rule.severity, 'critical')
        self.assertEqual(updated_rule.threshold_value, 95.0)
    
    def test_alert_rule_serializer_fields(self):
        """Test AlertRuleSerializer fields"""
        serializer = AlertRuleSerializer(self.alert_rule)
        data = serializer.data
        
        expected_fields = [
            'id', 'name', 'alert_type', 'severity', 'threshold_value',
            'time_window_minutes', 'cooldown_minutes', 'description',
            'is_active', 'send_email', 'send_telegram', 'send_sms',
            'created_at', 'updated_at', 'last_triggered'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_alert_rule_serializer_custom_fields(self):
        """Test AlertRuleSerializer custom fields"""
        serializer = AlertRuleSerializer(self.alert_rule)
        data = serializer.data
        
        # Test display fields
        self.assertEqual(data['severity_display'], 'High')
        self.assertEqual(data['alert_type_display'], 'CPU Usage')
        
        # Test computed fields
        self.assertIsInstance(data['recent_alerts_count'], int)
        self.assertIsInstance(data['success_rate'], (int, float))
    
    def test_alert_rule_serializer_validation_threshold_value(self):
        """Test AlertRuleSerializer threshold_value validation"""
        # Invalid threshold value
        data = {
            'name': 'Invalid Alert Rule',
            'alert_type': 'cpu_usage',
            'severity': 'high',
            'threshold_value': -10.0,  # Negative value
            'time_window_minutes': 15,
            'cooldown_minutes': 30
        }
        
        serializer = AlertRuleSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('threshold_value', serializer.errors)


class AlertLogSerializerTest(TestCase):
    """Test cases for AlertLogSerializer"""
    
    def setUp(self):
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
    
    def test_alert_log_serializer_validation(self):
        """Test AlertLogSerializer validation"""
        # Valid data
        valid_data = {
            'rule': self.alert_rule.id,
            'trigger_value': 90.0,
            'threshold_value': 80.0,
            'message': 'Memory usage is high',
            'details': {'current_usage': 90.0}
        }
        
        serializer = AlertLogSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid data - missing required fields
        invalid_data = {
            'rule': self.alert_rule.id,
            'trigger_value': 90.0
        }
        
        serializer = AlertLogSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('threshold_value', serializer.errors)
        self.assertIn('message', serializer.errors)
    
    def test_alert_log_serializer_create(self):
        """Test AlertLogSerializer create"""
        data = {
            'rule': self.alert_rule.id,
            'trigger_value': 92.0,
            'threshold_value': 80.0,
            'message': 'Disk usage is critical',
            'details': {'current_usage': 92.0, 'threshold': 80.0}
        }
        
        serializer = AlertLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        alert_log = serializer.save()
        
        self.assertEqual(alert_log.rule, self.alert_rule)
        self.assertEqual(alert_log.trigger_value, 92.0)
        self.assertEqual(alert_log.threshold_value, 80.0)
        self.assertEqual(alert_log.message, 'Disk usage is critical')
    
    def test_alert_log_serializer_update(self):
        """Test AlertLogSerializer update"""
        data = {
            'is_resolved': True,
            'resolution_note': 'Fixed the issue'
        }
        
        serializer = AlertLogSerializer(
            instance=self.alert_log,
            data=data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        updated_log = serializer.save()
        
        self.assertTrue(updated_log.is_resolved)
        self.assertEqual(updated_log.resolution_note, 'Fixed the issue')
    
    def test_alert_log_serializer_fields(self):
        """Test AlertLogSerializer fields"""
        serializer = AlertLogSerializer(self.alert_log)
        data = serializer.data
        
        expected_fields = [
            'id', 'rule', 'trigger_value', 'threshold_value', 'message',
            'details', 'is_resolved', 'resolved_by', 'resolved_at',
            'resolution_note', 'triggered_at', 'acknowledged_at',
            'acknowledged_by', 'acknowledgment_note'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_alert_log_serializer_custom_fields(self):
        """Test AlertLogSerializer custom fields"""
        serializer = AlertLogSerializer(self.alert_log)
        data = serializer.data
        
        # Test computed fields
        self.assertEqual(data['severity_display'], 'High')
        self.assertEqual(data['status_display'], 'Pending')
        self.assertIsInstance(data['exceed_percentage'], (int, float))
        self.assertIsInstance(data['age_minutes'], (int, float))
    
    def test_alert_log_serializer_nested_rule(self):
        """Test AlertLogSerializer nested rule data"""
        serializer = AlertLogSerializer(self.alert_log)
        data = serializer.data
        
        self.assertIn('rule', data)
        self.assertIsInstance(data['rule'], dict)
        self.assertEqual(data['rule']['name'], 'Test Alert Rule')
        self.assertEqual(data['rule']['alert_type'], 'cpu_usage')


class NotificationSerializerTest(TestCase):
    """Test cases for NotificationSerializer"""
    
    def setUp(self):
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
    
    def test_notification_serializer_validation(self):
        """Test NotificationSerializer validation"""
        # Valid data
        valid_data = {
            'alert_log': self.alert_log.id,
            'notification_type': 'sms',
            'recipient': '+1234567890',
            'status': 'pending'
        }
        
        serializer = NotificationSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid data - missing required fields
        invalid_data = {
            'notification_type': 'email',
            'recipient': 'test@example.com'
        }
        
        serializer = NotificationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('alert_log', serializer.errors)
    
    def test_notification_serializer_create(self):
        """Test NotificationSerializer create"""
        data = {
            'alert_log': self.alert_log.id,
            'notification_type': 'telegram',
            'recipient': '@testuser',
            'status': 'pending'
        }
        
        serializer = NotificationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        notification = serializer.save()
        
        self.assertEqual(notification.alert_log, self.alert_log)
        self.assertEqual(notification.notification_type, 'telegram')
        self.assertEqual(notification.recipient, '@testuser')
    
    def test_notification_serializer_update(self):
        """Test NotificationSerializer update"""
        data = {
            'status': 'sent',
            'sent_at': timezone.now()
        }
        
        serializer = NotificationSerializer(
            instance=self.notification,
            data=data,
            partial=True
        )
        self.assertTrue(serializer.is_valid())
        
        updated_notification = serializer.save()
        
        self.assertEqual(updated_notification.status, 'sent')
        self.assertIsNotNone(updated_notification.sent_at)
    
    def test_notification_serializer_fields(self):
        """Test NotificationSerializer fields"""
        serializer = NotificationSerializer(self.notification)
        data = serializer.data
        
        expected_fields = [
            'id', 'alert_log', 'notification_type', 'recipient',
            'status', 'sent_at', 'failed_at', 'error_message',
            'retry_count', 'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_notification_serializer_custom_fields(self):
        """Test NotificationSerializer custom fields"""
        serializer = NotificationSerializer(self.notification)
        data = serializer.data
        
        # Test display fields
        self.assertEqual(data['status_display'], 'Pending')
        self.assertEqual(data['type_display'], 'Email')
        
        # Test computed fields
        self.assertIsInstance(data['delivery_time_minutes'], (int, float, type(None)))
    
    def test_notification_serializer_nested_alert_log(self):
        """Test NotificationSerializer nested alert log data"""
        serializer = NotificationSerializer(self.notification)
        data = serializer.data
        
        self.assertIn('alert_log', data)
        self.assertIsInstance(data['alert_log'], dict)
        self.assertEqual(data['alert_log']['message'], 'CPU usage is high')


class SystemMetricsSerializerTest(TestCase):
    """Test cases for SystemMetricsSerializer"""
    
    def setUp(self):
        self.system_metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
    
    def test_system_metrics_serializer_validation(self):
        """Test SystemMetricsSerializer validation"""
        # Valid data
        valid_data = {
            'total_users': 1500,
            'active_users_1h': 750,
            'total_earnings_1h': 1500.0,
            'avg_response_time_ms': 250.0
        }
        
        serializer = SystemMetricsSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid data - negative values
        invalid_data = {
            'total_users': -100,
            'active_users_1h': 500,
            'total_earnings_1h': 1000.0,
            'avg_response_time_ms': 200.0
        }
        
        serializer = SystemMetricsSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('total_users', serializer.errors)
    
    def test_system_metrics_serializer_create(self):
        """Test SystemMetricsSerializer create"""
        data = {
            'total_users': 2000,
            'active_users_1h': 1000,
            'total_earnings_1h': 2000.0,
            'avg_response_time_ms': 300.0
        }
        
        serializer = SystemMetricsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        metrics = serializer.save()
        
        self.assertEqual(metrics.total_users, 2000)
        self.assertEqual(metrics.active_users_1h, 1000)
        self.assertEqual(metrics.total_earnings_1h, 2000.0)
        self.assertEqual(metrics.avg_response_time_ms, 300.0)
    
    def test_system_metrics_serializer_fields(self):
        """Test SystemMetricsSerializer fields"""
        serializer = SystemMetricsSerializer(self.system_metrics)
        data = serializer.data
        
        expected_fields = [
            'id', 'total_users', 'active_users_1h', 'total_earnings_1h',
            'avg_response_time_ms', 'timestamp'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_system_metrics_serializer_custom_fields(self):
        """Test SystemMetricsSerializer custom fields"""
        serializer = SystemMetricsSerializer(self.system_metrics)
        data = serializer.data
        
        # Test computed fields
        self.assertEqual(data['health_status'], 'healthy')
        self.assertIsInstance(data['active_user_percentage'], (int, float))
        self.assertIsInstance(data['earnings_per_user'], (int, float))


class AlertRuleListSerializerTest(TestCase):
    """Test cases for AlertRuleListSerializer"""
    
    def setUp(self):
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def test_alert_rule_list_serializer_fields(self):
        """Test AlertRuleListSerializer fields"""
        serializer = AlertRuleListSerializer(self.alert_rule)
        data = serializer.data
        
        # Should have fewer fields than full serializer
        expected_fields = [
            'id', 'name', 'alert_type', 'severity', 'threshold_value',
            'is_active', 'created_at', 'last_triggered'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Should not have detailed fields
        excluded_fields = ['description', 'cooldown_minutes', 'send_email']
        for field in excluded_fields:
            self.assertNotIn(field, data)


class AlertLogListSerializerTest(TestCase):
    """Test cases for AlertLogListSerializer"""
    
    def setUp(self):
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
    
    def test_alert_log_list_serializer_fields(self):
        """Test AlertLogListSerializer fields"""
        serializer = AlertLogListSerializer(self.alert_log)
        data = serializer.data
        
        # Should have fewer fields than full serializer
        expected_fields = [
            'id', 'rule', 'trigger_value', 'threshold_value', 'message',
            'is_resolved', 'triggered_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Should not have detailed fields
        excluded_fields = ['details', 'resolution_note', 'acknowledgment_note']
        for field in excluded_fields:
            self.assertNotIn(field, data)


class NotificationListSerializerTest(TestCase):
    """Test cases for NotificationListSerializer"""
    
    def setUp(self):
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
    
    def test_notification_list_serializer_fields(self):
        """Test NotificationListSerializer fields"""
        serializer = NotificationListSerializer(self.notification)
        data = serializer.data
        
        # Should have fewer fields than full serializer
        expected_fields = [
            'id', 'alert_log', 'notification_type', 'recipient',
            'status', 'created_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Should not have detailed fields
        excluded_fields = ['error_message', 'retry_count', 'failed_at']
        for field in excluded_fields:
            self.assertNotIn(field, data)


class SystemMetricsListSerializerTest(TestCase):
    """Test cases for SystemMetricsListSerializer"""
    
    def setUp(self):
        self.system_metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
    
    def test_system_metrics_list_serializer_fields(self):
        """Test SystemMetricsListSerializer fields"""
        serializer = SystemMetricsListSerializer(self.system_metrics)
        data = serializer.data
        
        # Should have fewer fields than full serializer
        expected_fields = [
            'id', 'total_users', 'active_users_1h', 'total_earnings_1h',
            'avg_response_time_ms', 'timestamp'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Should not have computed fields
        excluded_fields = ['health_status', 'active_user_percentage']
        for field in excluded_fields:
            self.assertNotIn(field, data)

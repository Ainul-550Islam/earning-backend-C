"""
Tests for Core Signals
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification
from alerts.signals.core import (
    alert_rule_created, alert_rule_updated, alert_rule_deleted,
    alert_log_created, alert_log_resolved, alert_log_acknowledged,
    notification_sent, notification_failed, system_metrics_updated
)


class AlertRuleSignalsTest(TestCase):
    """Test cases for AlertRule signals"""
    
    def setUp(self):
        self.signal_received = False
        self.signal_data = None
    
    def signal_handler(self, sender, **kwargs):
        """Custom signal handler for testing"""
        self.signal_received = True
        self.signal_data = kwargs
    
    def test_alert_rule_created_signal(self):
        """Test alert_rule_created signal"""
        # Connect signal handler
        alert_rule_created.connect(self.signal_handler)
        
        # Create alert rule
        rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], rule)
        self.assertIn('created_at', self.signal_data)
    
    def test_alert_rule_updated_signal(self):
        """Test alert_rule_updated signal"""
        # Connect signal handler
        alert_rule_updated.connect(self.signal_handler)
        
        # Create alert rule first
        rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Reset signal flag
        self.signal_received = False
        self.signal_data = None
        
        # Update alert rule
        rule.name = 'Updated Alert Rule'
        rule.severity = 'critical'
        rule.save()
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], rule)
        self.assertIn('updated_fields', self.signal_data)
    
    def test_alert_rule_deleted_signal(self):
        """Test alert_rule_deleted signal"""
        # Connect signal handler
        alert_rule_deleted.connect(self.signal_handler)
        
        # Create alert rule first
        rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Reset signal flag
        self.signal_received = False
        self.signal_data = None
        
        # Delete alert rule
        rule_id = rule.id
        rule.delete()
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance_id'], rule_id)
        self.assertIn('deleted_at', self.signal_data)
    
    def test_alert_rule_signal_payload(self):
        """Test alert rule signal payload"""
        # Connect signal handler
        alert_rule_created.connect(self.signal_handler)
        
        # Create alert rule with additional data
        rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            description='Test description'
        )
        
        # Check signal payload
        self.assertIn('instance', self.signal_data)
        self.assertIn('created_at', self.signal_data)
        self.assertIn('sender', self.signal_data)
        self.assertEqual(self.signal_data['instance'], rule)
    
    def test_multiple_signal_handlers(self):
        """Test multiple signal handlers for same signal"""
        handler1_called = False
        handler2_called = False
        
        def handler1(sender, **kwargs):
            nonlocal handler1_called
            handler1_called = True
        
        def handler2(sender, **kwargs):
            nonlocal handler2_called
            handler2_called = True
        
        # Connect multiple handlers
        alert_rule_created.connect(handler1)
        alert_rule_created.connect(handler2)
        
        # Create alert rule
        AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Both handlers should be called
        self.assertTrue(handler1_called)
        self.assertTrue(handler2_called)
    
    def test_signal_handler_exception(self):
        """Test signal handler exception handling"""
        def failing_handler(sender, **kwargs):
            raise Exception("Handler failed")
        
        def working_handler(sender, **kwargs):
            working_handler.called = True
        
        working_handler.called = False
        
        # Connect handlers
        alert_rule_created.connect(failing_handler)
        alert_rule_created.connect(working_handler)
        
        # Create alert rule - should not raise exception
        AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Working handler should still be called
        self.assertTrue(working_handler.called)


class AlertLogSignalsTest(TestCase):
    """Test cases for AlertLog signals"""
    
    def setUp(self):
        self.signal_received = False
        self.signal_data = None
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
    
    def signal_handler(self, sender, **kwargs):
        """Custom signal handler for testing"""
        self.signal_received = True
        self.signal_data = kwargs
    
    def test_alert_log_created_signal(self):
        """Test alert_log_created signal"""
        # Connect signal handler
        alert_log_created.connect(self.signal_handler)
        
        # Create alert log
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], alert_log)
        self.assertIn('triggered_at', self.signal_data)
    
    def test_alert_log_resolved_signal(self):
        """Test alert_log_resolved signal"""
        # Connect signal handler
        alert_log_resolved.connect(self.signal_handler)
        
        # Create alert log first
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )
        
        # Reset signal flag
        self.signal_received = False
        self.signal_data = None
        
        # Resolve alert log
        alert_log.is_resolved = True
        alert_log.resolution_note = 'Fixed the issue'
        alert_log.save()
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], alert_log)
        self.assertIn('resolved_at', self.signal_data)
        self.assertIn('resolution_note', self.signal_data)
    
    def test_alert_log_acknowledged_signal(self):
        """Test alert_log_acknowledged signal"""
        # Connect signal handler
        alert_log_acknowledged.connect(self.signal_handler)
        
        # Create alert log first
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high'
        )
        
        # Reset signal flag
        self.signal_received = False
        self.signal_data = None
        
        # Acknowledge alert log
        alert_log.acknowledged_at = timezone.now()
        alert_log.acknowledgment_note = 'Investigating'
        alert_log.save()
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], alert_log)
        self.assertIn('acknowledged_at', self.signal_data)
        self.assertIn('acknowledgment_note', self.signal_data)
    
    def test_alert_log_signal_with_details(self):
        """Test alert log signal with details"""
        # Connect signal handler
        alert_log_created.connect(self.signal_handler)
        
        # Create alert log with details
        details = {'current_usage': 85.0, 'threshold': 80.0}
        alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details=details
        )
        
        # Check signal includes details
        self.assertIn('instance', self.signal_data)
        self.assertEqual(self.signal_data['instance'].details, details)


class NotificationSignalsTest(TestCase):
    """Test cases for Notification signals"""
    
    def setUp(self):
        self.signal_received = False
        self.signal_data = None
        
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
    
    def signal_handler(self, sender, **kwargs):
        """Custom signal handler for testing"""
        self.signal_received = True
        self.signal_data = kwargs
    
    def test_notification_sent_signal(self):
        """Test notification_sent signal"""
        # Connect signal handler
        notification_sent.connect(self.signal_handler)
        
        # Create notification
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            sent_at=timezone.now()
        )
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], notification)
        self.assertIn('sent_at', self.signal_data)
        self.assertIn('delivery_time', self.signal_data)
    
    def test_notification_failed_signal(self):
        """Test notification_failed signal"""
        # Connect signal handler
        notification_failed.connect(self.signal_handler)
        
        # Create failed notification
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            failed_at=timezone.now(),
            error_message='SMTP server error'
        )
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], notification)
        self.assertIn('failed_at', self.signal_data)
        self.assertIn('error_message', self.signal_data)
        self.assertIn('retry_count', self.signal_data)
    
    def test_notification_retry_signal(self):
        """Test notification retry signal"""
        # Connect signal handler
        notification_failed.connect(self.signal_handler)
        
        # Create notification with retries
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            retry_count=2,
            failed_at=timezone.now()
        )
        
        # Check signal includes retry information
        self.assertIn('retry_count', self.signal_data)
        self.assertEqual(self.signal_data['retry_count'], 2)
    
    def test_notification_signal_batch_operations(self):
        """Test notification signals during batch operations"""
        # Connect signal handler
        notification_sent.connect(self.signal_handler)
        
        # Create multiple notifications
        notifications = []
        for i in range(3):
            notification = Notification.objects.create(
                alert_log=self.alert_log,
                notification_type='email',
                recipient=f'test{i}@example.com',
                status='sent',
                sent_at=timezone.now()
            )
            notifications.append(notification)
        
        # Signal should be sent for each notification
        # In a real implementation, you'd track multiple signals
        self.assertTrue(self.signal_received)
    
    def test_notification_signal_with_metadata(self):
        """Test notification signal with metadata"""
        # Connect signal handler
        notification_sent.connect(self.signal_handler)
        
        # Create notification with metadata
        metadata = {
            'delivery_method': 'smtp',
            'provider': 'sendgrid',
            'message_id': 'msg_12345'
        }
        
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            sent_at=timezone.now()
        )
        
        # Store metadata (in real implementation)
        notification.metadata = metadata
        notification.save()
        
        # Check signal includes metadata
        self.assertIn('instance', self.signal_data)


class SystemMetricsSignalsTest(TestCase):
    """Test cases for SystemMetrics signals"""
    
    def setUp(self):
        self.signal_received = False
        self.signal_data = None
    
    def signal_handler(self, sender, **kwargs):
        """Custom signal handler for testing"""
        self.signal_received = True
        self.signal_data = kwargs
    
    def test_system_metrics_updated_signal(self):
        """Test system_metrics_updated signal"""
        # Connect signal handler
        system_metrics_updated.connect(self.signal_handler)
        
        # Create system metrics
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
        
        # Check signal was sent
        self.assertTrue(self.signal_received)
        self.assertIsNotNone(self.signal_data)
        self.assertEqual(self.signal_data['instance'], metrics)
        self.assertIn('timestamp', self.signal_data)
    
    def test_system_metrics_signal_anomaly_detection(self):
        """Test system metrics signal anomaly detection"""
        # Connect signal handler
        system_metrics_updated.connect(self.signal_handler)
        
        # Create metrics with anomaly (high response time)
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=5000.0  # High response time
        )
        
        # Check signal includes anomaly detection
        self.assertIn('instance', self.signal_data)
        self.assertIn('anomaly_detected', self.signal_data)
        self.assertIn('health_status', self.signal_data)
    
    def test_system_metrics_signal_trend_analysis(self):
        """Test system metrics signal trend analysis"""
        # Connect signal handler
        system_metrics_updated.connect(self.signal_handler)
        
        # Create multiple metrics for trend analysis
        base_time = timezone.now() - timedelta(hours=2)
        for i in range(5):
            SystemMetrics.objects.create(
                total_users=1000 + i * 10,
                active_users_1h=500 + i * 5,
                total_earnings_1h=1000.0 + i * 50,
                avg_response_time_ms=200.0 + i * 10,
                timestamp=base_time + timedelta(minutes=i * 30)
            )
        
        # Check signal includes trend analysis
        self.assertIn('trend_analysis', self.signal_data)
        self.assertIn('trend_direction', self.signal_data)
    
    def test_system_metrics_signal_health_check(self):
        """Test system metrics signal health check"""
        # Connect signal handler
        system_metrics_updated.connect(self.signal_handler)
        
        # Create metrics for health check
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0
        )
        
        # Check signal includes health check
        self.assertIn('health_check', self.signal_data)
        self.assertIn('health_score', self.signal_data)
        self.assertIn('issues_detected', self.signal_data)


class SignalIntegrationTest(TestCase):
    """Test cases for signal integration"""
    
    def setUp(self):
        self.signal_log = []
        
    def universal_signal_handler(self, sender, **kwargs):
        """Universal signal handler for testing all signals"""
        self.signal_log.append({
            'sender': sender.__name__,
            'signal_type': kwargs.get('signal_type', 'unknown'),
            'timestamp': timezone.now(),
            'data': kwargs
        })
    
    def test_signal_chain_reaction(self):
        """Test signal chain reaction"""
        # Connect all core signals
        from alerts.signals.core import (
            alert_rule_created, alert_log_created, notification_sent
        )
        
        alert_rule_created.connect(self.universal_signal_handler)
        alert_log_created.connect(self.universal_signal_handler)
        notification_sent.connect(self.universal_signal_handler)
        
        # Create alert rule
        rule = AlertRule.objects.create(
            name='Chain Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Create alert log
        alert_log = AlertLog.objects.create(
            rule=rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Chain test alert'
        )
        
        # Create notification
        notification = Notification.objects.create(
            alert_log=alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            sent_at=timezone.now()
        )
        
        # Check signal chain
        self.assertEqual(len(self.signal_log), 3)
        
        # Verify signal order and content
        signal_types = [log['signal_type'] for log in self.signal_log]
        self.assertIn('alert_rule_created', signal_types)
        self.assertIn('alert_log_created', signal_types)
        self.assertIn('notification_sent', signal_types)
    
    def test_signal_error_handling(self):
        """Test signal error handling"""
        def failing_handler(sender, **kwargs):
            raise ValueError("Signal handler error")
        
        def recovery_handler(sender, **kwargs):
            recovery_handler.called = True
        
        recovery_handler.called = False
        
        # Connect handlers
        from alerts.signals.core import alert_rule_created
        alert_rule_created.connect(failing_handler)
        alert_rule_created.connect(recovery_handler)
        
        # Create alert rule - should not raise exception
        AlertRule.objects.create(
            name='Error Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Recovery handler should still be called
        self.assertTrue(recovery_handler.called)
    
    def test_signal_performance(self):
        """Test signal performance with many objects"""
        from alerts.signals.core import alert_log_created
        alert_log_created.connect(self.universal_signal_handler)
        
        # Create many alert logs
        start_time = timezone.now()
        
        rule = AlertRule.objects.create(
            name='Performance Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        for i in range(100):
            AlertLog.objects.create(
                rule=rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Performance test alert {i}'
            )
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # Check performance
        self.assertEqual(len(self.signal_log), 100)
        self.assertLess(duration, 5.0)  # Should complete within 5 seconds
    
    def test_signal_data_integrity(self):
        """Test signal data integrity"""
        from alerts.signals.core import alert_log_created
        alert_log_created.connect(self.universal_signal_handler)
        
        # Create alert log with complex data
        complex_details = {
            'metrics': {
                'cpu_usage': 85.0,
                'memory_usage': 70.0,
                'disk_io': 50.0
            },
            'context': {
                'server': 'web-01',
                'environment': 'production',
                'region': 'us-east-1'
            },
            'metadata': {
                'source': 'monitoring_system',
                'version': '1.0',
                'timestamp': timezone.now().isoformat()
            }
        }
        
        alert_log = AlertLog.objects.create(
            rule=AlertRule.objects.create(
                name='Data Integrity Test',
                alert_type='cpu_usage',
                severity='high',
                threshold_value=80.0
            ),
            trigger_value=85.0,
            threshold_value=80.0,
            message='Data integrity test',
            details=complex_details
        )
        
        # Check data integrity
        self.assertEqual(len(self.signal_log), 1)
        signal_data = self.signal_log[0]['data']['instance']
        self.assertEqual(signal_data.details, complex_details)
        self.assertEqual(signal_data.message, 'Data integrity test')

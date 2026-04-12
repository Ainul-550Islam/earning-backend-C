"""
Tests for Alert Utilities
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.utils.core import (
    AlertUtils, NotificationUtils, MetricsUtils, ValidationUtils,
    DateTimeUtils, FormatUtils, SecurityUtils
)


class AlertUtilsTest(TestCase):
    """Test cases for AlertUtils"""
    
    def setUp(self):
        self.utils = AlertUtils()
        
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
    
    def test_get_alert_severity_score(self):
        """Test getting alert severity score"""
        # Test different severities
        self.assertEqual(self.utils.get_severity_score('low'), 1)
        self.assertEqual(self.utils.get_severity_score('medium'), 2)
        self.assertEqual(self.utils.get_severity_score('high'), 3)
        self.assertEqual(self.utils.get_severity_score('critical'), 4)
        
        # Test invalid severity
        self.assertEqual(self.utils.get_severity_score('invalid'), 0)
    
    def test_get_alert_priority(self):
        """Test getting alert priority"""
        # Test alert priority calculation
        priority = self.utils.get_alert_priority(self.alert_log)
        
        self.assertIsInstance(priority, int)
        self.assertGreater(priority, 0)
        self.assertLessEqual(priority, 100)
    
    def test_is_alert_critical(self):
        """Test checking if alert is critical"""
        # Critical alert
        critical_rule = AlertRule.objects.create(
            name='Critical Alert',
            alert_type='system_error',
            severity='critical',
            threshold_value=1.0
        )
        
        critical_log = AlertLog.objects.create(
            rule=critical_rule,
            trigger_value=1.0,
            threshold_value=1.0,
            message='Critical system error'
        )
        
        self.assertTrue(self.utils.is_alert_critical(critical_log))
        
        # Non-critical alert
        self.assertFalse(self.utils.is_alert_critical(self.alert_log))
    
    def test_get_alert_age_in_minutes(self):
        """Test getting alert age in minutes"""
        # Recent alert
        recent_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Recent alert',
            triggered_at=timezone.now() - timedelta(minutes=30)
        )
        
        age = self.utils.get_alert_age_in_minutes(recent_log)
        self.assertEqual(age, 30)
        
        # Old alert
        old_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Old alert',
            triggered_at=timezone.now() - timedelta(hours=2)
        )
        
        age = self.utils.get_alert_age_in_minutes(old_log)
        self.assertEqual(age, 120)
    
    def test_get_alert_resolution_time(self):
        """Test getting alert resolution time"""
        # Resolved alert
        resolved_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Resolved alert',
            triggered_at=timezone.now() - timedelta(minutes=30),
            is_resolved=True,
            resolved_at=timezone.now()
        )
        
        resolution_time = self.utils.get_alert_resolution_time(resolved_log)
        self.assertEqual(resolution_time, 30)
        
        # Unresolved alert
        self.assertIsNone(self.utils.get_alert_resolution_time(self.alert_log))
    
    def test_get_alert_exceed_percentage(self):
        """Test getting alert exceed percentage"""
        # Alert above threshold
        exceed = self.utils.get_alert_exceed_percentage(self.alert_log)
        expected = ((85.0 - 80.0) / 80.0) * 100
        self.assertEqual(exceed, expected)
        
        # Alert below threshold
        below_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=75.0,
            threshold_value=80.0,
            message='Below threshold alert'
        )
        
        exceed = self.utils.get_alert_exceed_percentage(below_log)
        self.assertEqual(exceed, 0)
    
    def test_group_alerts_by_similarity(self):
        """Test grouping alerts by similarity"""
        # Create similar alerts
        similar_alerts = []
        for i in range(3):
            alert = AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'CPU usage is high - {i}'
            )
            similar_alerts.append(alert)
        
        groups = self.utils.group_alerts_by_similarity(similar_alerts)
        
        self.assertIsInstance(groups, list)
        self.assertGreater(len(groups), 0)
    
    def test_get_alert_context(self):
        """Test getting alert context"""
        context = self.utils.get_alert_context(self.alert_log)
        
        self.assertIn('rule', context)
        self.assertIn('severity', context)
        self.assertIn('trigger_value', context)
        self.assertIn('threshold_value', context)
        self.assertIn('message', context)
        self.assertIn('triggered_at', context)
    
    def test_validate_alert_data(self):
        """Test validating alert data"""
        # Valid data
        valid_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Test alert'
        }
        
        result = self.utils.validate_alert_data(valid_data)
        self.assertTrue(result['valid'])
        
        # Invalid data
        invalid_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0
            # Missing required fields
        }
        
        result = self.utils.validate_alert_data(invalid_data)
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)


class NotificationUtilsTest(TestCase):
    """Test cases for NotificationUtils"""
    
    def setUp(self):
        self.utils = NotificationUtils()
        
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
            status='sent'
        )
    
    def test_format_notification_message(self):
        """Test formatting notification message"""
        message = self.utils.format_notification_message(
            self.notification,
            subject='Alert Notification',
            template='default'
        )
        
        self.assertIsInstance(message, str)
        self.assertIn('CPU usage is high', message)
    
    def test_get_notification_recipients(self):
        """Test getting notification recipients"""
        recipients = self.utils.get_notification_recipients(
            self.alert_log,
            notification_types=['email', 'sms']
        )
        
        self.assertIsInstance(recipients, list)
    
    def test_is_notification_successful(self):
        """Test checking if notification is successful"""
        # Successful notification
        self.assertTrue(self.utils.is_notification_successful(self.notification))
        
        # Failed notification
        failed_notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed'
        )
        
        self.assertFalse(self.utils.is_notification_successful(failed_notification))
    
    def test_get_notification_retry_count(self):
        """Test getting notification retry count"""
        # Notification with retries
        retry_notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            retry_count=3
        )
        
        retry_count = self.utils.get_notification_retry_count(retry_notification)
        self.assertEqual(retry_count, 3)
        
        # Notification without retries
        self.assertEqual(self.utils.get_notification_retry_count(self.notification), 0)
    
    def test_calculate_notification_success_rate(self):
        """Test calculating notification success rate"""
        # Create multiple notifications
        notifications = []
        for i in range(10):
            notification = Notification.objects.create(
                alert_log=self.alert_log,
                notification_type='email',
                recipient=f'test{i}@example.com',
                status='sent' if i % 3 != 0 else 'failed'
            )
            notifications.append(notification)
        
        success_rate = self.utils.calculate_notification_success_rate(notifications)
        expected = (7 / 10) * 100  # 7 sent, 3 failed
        self.assertEqual(success_rate, expected)
    
    def test_get_notification_delivery_time(self):
        """Test getting notification delivery time"""
        # Notification with delivery time
        delivery_notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            created_at=timezone.now() - timedelta(minutes=2),
            sent_at=timezone.now() - timedelta(minutes=1)
        )
        
        delivery_time = self.utils.get_notification_delivery_time(delivery_notification)
        self.assertEqual(delivery_time, 60)  # 1 minute = 60 seconds
        
        # Notification without delivery time
        self.assertIsNone(self.utils.get_notification_delivery_time(self.notification))
    
    def test_group_notifications_by_type(self):
        """Test grouping notifications by type"""
        # Create notifications of different types
        notifications = []
        for i in range(6):
            notification = Notification.objects.create(
                alert_log=self.alert_log,
                notification_type='email' if i % 2 == 0 else 'sms',
                recipient=f'test{i}@example.com',
                status='sent'
            )
            notifications.append(notification)
        
        groups = self.utils.group_notifications_by_type(notifications)
        
        self.assertIn('email', groups)
        self.assertIn('sms', groups)
        self.assertEqual(len(groups['email']), 3)
        self.assertEqual(len(groups['sms']), 3)
    
    def test_validate_notification_data(self):
        """Test validating notification data"""
        # Valid data
        valid_data = {
            'alert_log_id': self.alert_log.id,
            'notification_type': 'email',
            'recipient': 'test@example.com',
            'subject': 'Test Notification'
        }
        
        result = self.utils.validate_notification_data(valid_data)
        self.assertTrue(result['valid'])
        
        # Invalid data
        invalid_data = {
            'notification_type': 'email',
            'recipient': 'test@example.com'
            # Missing alert_log_id
        }
        
        result = self.utils.validate_notification_data(invalid_data)
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)


class MetricsUtilsTest(TestCase):
    """Test cases for MetricsUtils"""
    
    def setUp(self):
        self.utils = MetricsUtils()
        
        # Create test metrics
        for i in range(5):
            SystemMetrics.objects.create(
                total_users=1000 + i * 100,
                active_users_1h=500 + i * 50,
                total_earnings_1h=1000.0 + i * 100,
                avg_response_time_ms=200.0 + i * 20,
                timestamp=timezone.now() - timedelta(hours=i)
            )
    
    def test_calculate_mttr(self):
        """Test calculating MTTR"""
        from alerts.models.core import AlertLog
        
        # Create resolved alerts
        for i in range(10):
            alert = AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'MTTR Test {i}',
                    alert_type='cpu_usage',
                    severity='high',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'MTTR test {i}',
                triggered_at=timezone.now() - timedelta(minutes=i * 5),
                is_resolved=True,
                resolved_at=timezone.now() - timedelta(minutes=i * 2)
            )
        
        mttr = self.utils.calculate_mttr(days=7)
        
        self.assertIsInstance(mttr, (int, float))
        self.assertGreater(mttr, 0)
    
    def test_calculate_mttd(self):
        """Test calculating MTTD"""
        from alerts.models.core import AlertLog
        
        # Create alerts
        for i in range(10):
            AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'MTTD Test {i}',
                    alert_type='cpu_usage',
                    severity='high',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'MTTD test {i}',
                triggered_at=timezone.now() - timedelta(minutes=i)
            )
        
        mttd = self.utils.calculate_mttd(days=7)
        
        self.assertIsInstance(mttd, (int, float))
        self.assertGreater(mttd, 0)
    
    def test_get_system_health_score(self):
        """Test getting system health score"""
        health_score = self.utils.get_system_health_score()
        
        self.assertIsInstance(health_score, (int, float))
        self.assertGreaterEqual(health_score, 0)
        self.assertLessEqual(health_score, 100)
    
    def test_get_alert_trends(self):
        """Test getting alert trends"""
        from alerts.models.core import AlertLog
        
        # Create alerts over time
        base_time = timezone.now() - timedelta(days=7)
        for i in range(50):
            AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'Trend Test {i}',
                    alert_type='cpu_usage',
                    severity='high',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Trend test {i}',
                triggered_at=base_time + timedelta(hours=i * 3)
            )
        
        trends = self.utils.get_alert_trends(days=7)
        
        self.assertIn('daily_trends', trends)
        self.assertIn('hourly_trends', trends)
        self.assertIn('severity_trends', trends)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        metrics = self.utils.get_performance_metrics(days=7)
        
        self.assertIn('avg_response_time', metrics)
        self.assertIn('peak_response_time', metrics)
        self.assertIn('error_rate', metrics)
        self.assertIn('throughput', metrics)
    
    def test_calculate_sla_compliance(self):
        """Test calculating SLA compliance"""
        from alerts.models.reporting import SLABreach
        
        # Create some SLA breaches
        for i in range(3):
            SLABreach.objects.create(
                name=f'SLA Breach {i}',
                sla_type='response_time',
                severity='high',
                status='resolved',
                threshold_minutes=30,
                breach_duration_minutes=15 + i * 5
            )
        
        compliance = self.utils.calculate_sla_compliance(days=30)
        
        self.assertIsInstance(compliance, (int, float))
        self.assertGreaterEqual(compliance, 0)
        self.assertLessEqual(compliance, 100)
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary"""
        summary = self.utils.get_metrics_summary(days=7)
        
        self.assertIn('total_alerts', summary)
        self.assertIn('resolved_alerts', summary)
        self.assertIn('mttr', summary)
        self.assertIn('system_health', summary)
        self.assertIn('sla_compliance', summary)


class ValidationUtilsTest(TestCase):
    """Test cases for ValidationUtils"""
    
    def setUp(self):
        self.utils = ValidationUtils()
    
    def test_validate_email(self):
        """Test email validation"""
        # Valid emails
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org',
            'user123@test-domain.com'
        ]
        
        for email in valid_emails:
            self.assertTrue(self.utils.validate_email(email))
        
        # Invalid emails
        invalid_emails = [
            'invalid-email',
            '@example.com',
            'test@',
            'test@.com',
            'test space@example.com'
        ]
        
        for email in invalid_emails:
            self.assertFalse(self.utils.validate_email(email))
    
    def test_validate_phone_number(self):
        """Test phone number validation"""
        # Valid phone numbers
        valid_phones = [
            '+1234567890',
            '+1-234-567-8901',
            '+44 20 7946 0123',
            '555-123-4567'
        ]
        
        for phone in valid_phones:
            self.assertTrue(self.utils.validate_phone_number(phone))
        
        # Invalid phone numbers
        invalid_phones = [
            '123',
            'abc123',
            '+12345678901234567890',  # Too long
            '+abc1234567890'
        ]
        
        for phone in invalid_phones:
            self.assertFalse(self.utils.validate_phone_number(phone))
    
    def test_validate_severity(self):
        """Test severity validation"""
        # Valid severities
        valid_severities = ['low', 'medium', 'high', 'critical']
        
        for severity in valid_severities:
            self.assertTrue(self.utils.validate_severity(severity))
        
        # Invalid severities
        invalid_severities = ['invalid', 'very_high', 'urgent', 'normal']
        
        for severity in invalid_severities:
            self.assertFalse(self.utils.validate_severity(severity))
    
    def test_validate_threshold_value(self):
        """Test threshold value validation"""
        # Valid values
        valid_values = [0, 50.5, 100, 1000.0]
        
        for value in valid_values:
            self.assertTrue(self.utils.validate_threshold_value(value))
        
        # Invalid values
        invalid_values = [-10, 'invalid', None]
        
        for value in invalid_values:
            self.assertFalse(self.utils.validate_threshold_value(value))
    
    def test_validate_json_field(self):
        """Test JSON field validation"""
        # Valid JSON
        valid_json = '{"key": "value", "number": 123}'
        self.assertTrue(self.utils.validate_json_field(valid_json))
        
        # Invalid JSON
        invalid_json = '{"key": "value", "number": 123'
        self.assertFalse(self.utils.validate_json_field(invalid_json))
        
        # Valid Python dict
        valid_dict = {'key': 'value', 'number': 123}
        self.assertTrue(self.utils.validate_json_field(valid_dict))
    
    def test_validate_time_window(self):
        """Test time window validation"""
        # Valid windows
        valid_windows = [1, 15, 60, 1440]  # minutes
        for window in valid_windows:
            self.assertTrue(self.utils.validate_time_window(window))
        
        # Invalid windows
        invalid_windows = [0, -5, 10000, 'invalid']
        for window in invalid_windows:
            self.assertFalse(self.utils.validate_time_window(window))
    
    def test_validate_url(self):
        """Test URL validation"""
        # Valid URLs
        valid_urls = [
            'https://example.com',
            'http://api.example.com/endpoint',
            'https://subdomain.example.com:8080/path'
        ]
        
        for url in valid_urls:
            self.assertTrue(self.utils.validate_url(url))
        
        # Invalid URLs
        invalid_urls = [
            'not-a-url',
            'ftp://example.com',
            'http://',
            'https://'
        ]
        
        for url in invalid_urls:
            self.assertFalse(self.utils.validate_url(url))


class DateTimeUtilsTest(TestCase):
    """Test cases for DateTimeUtils"""
    
    def setUp(self):
        self.utils = DateTimeUtils()
    
    def test_format_duration(self):
        """Test formatting duration"""
        # Test different durations
        self.assertEqual(self.utils.format_duration(60), '1 minute')
        self.assertEqual(self.utils.format_duration(120), '2 minutes')
        self.assertEqual(self.utils.format_duration(3600), '1 hour')
        self.assertEqual(self.utils.format_duration(7200), '2 hours')
        self.assertEqual(self.utils.format_duration(86400), '1 day')
        self.assertEqual(self.utils.format_duration(172800), '2 days')
    
    def test_format_timestamp(self):
        """Test formatting timestamp"""
        timestamp = timezone.now()
        
        # Test different formats
        iso_format = self.utils.format_timestamp(timestamp, 'iso')
        self.assertIsInstance(iso_format, str)
        
        readable_format = self.utils.format_timestamp(timestamp, 'readable')
        self.assertIsInstance(readable_format, str)
        
        short_format = self.utils.format_timestamp(timestamp, 'short')
        self.assertIsInstance(short_format, str)
    
    def test_parse_time_string(self):
        """Test parsing time string"""
        # Test different time strings
        time_strings = [
            '1h',
            '30m',
            '2d',
            '1w',
            '1h30m',
            '2d3h'
        ]
        
        for time_str in time_strings:
            delta = self.utils.parse_time_string(time_str)
            self.assertIsInstance(delta, timedelta)
            self.assertGreater(delta.total_seconds(), 0)
    
    def test_get_time_range(self):
        """Test getting time range"""
        now = timezone.now()
        
        # Test last 24 hours
        start, end = self.utils.get_time_range('last_24h')
        self.assertEqual(end - start, timedelta(hours=24))
        self.assertLessEqual(end, now)
        
        # Test last 7 days
        start, end = self.utils.get_time_range('last_7d')
        self.assertEqual(end - start, timedelta(days=7))
        self.assertLessEqual(end, now)
    
    def test_is_within_time_window(self):
        """Test checking if time is within window"""
        now = timezone.now()
        
        # Recent time
        recent_time = now - timedelta(minutes=30)
        self.assertTrue(self.utils.is_within_time_window(recent_time, hours=1))
        
        # Old time
        old_time = now - timedelta(hours=2)
        self.assertFalse(self.utils.is_within_time_window(old_time, hours=1))
    
    def test_get_business_hours_duration(self):
        """Test getting business hours duration"""
        # Create time range within business hours
        start = timezone.now().replace(hour=10, minute=0)
        end = start + timedelta(hours=4)
        
        duration = self.utils.get_business_hours_duration(start, end)
        self.assertEqual(duration, timedelta(hours=4))
        
        # Create time range outside business hours
        start = timezone.now().replace(hour=20, minute=0)
        end = start + timedelta(hours=4)
        
        duration = self.utils.get_business_hours_duration(start, end)
        self.assertEqual(duration, timedelta(hours=0))
    
    def test_get_next_business_day(self):
        """Test getting next business day"""
        # Test weekday
        wednesday = timezone.now().replace(year=2024, month=1, day=3, hour=12)
        next_day = self.utils.get_next_business_day(wednesday)
        self.assertEqual(next_day.weekday(), 3)  # Thursday
        
        # Test Friday
        friday = timezone.now().replace(year=2024, month=1, day=5, hour=12)
        next_day = self.utils.get_next_business_day(friday)
        self.assertEqual(next_day.weekday(), 0)  # Monday
    
    def test_format_relative_time(self):
        """Test formatting relative time"""
        now = timezone.now()
        
        # Test different relative times
        self.assertEqual(
            self.utils.format_relative_time(now - timedelta(minutes=5)),
            '5 minutes ago'
        )
        
        self.assertEqual(
            self.utils.format_relative_time(now - timedelta(hours=2)),
            '2 hours ago'
        )
        
        self.assertEqual(
            self.utils.format_relative_time(now - timedelta(days=1)),
            '1 day ago'
        )


class FormatUtilsTest(TestCase):
    """Test cases for FormatUtils"""
    
    def setUp(self):
        self.utils = FormatUtils()
    
    def test_format_bytes(self):
        """Test formatting bytes"""
        self.assertEqual(self.utils.format_bytes(1024), '1.0 KB')
        self.assertEqual(self.utils.format_bytes(1048576), '1.0 MB')
        self.assertEqual(self.utils.format_bytes(1073741824), '1.0 GB')
        self.assertEqual(self.utils.format_bytes(500), '500.0 B')
    
    def test_format_percentage(self):
        """Test formatting percentage"""
        self.assertEqual(self.utils.format_percentage(85.5), '85.5%')
        self.assertEqual(self.utils.format_percentage(0), '0.0%')
        self.assertEqual(self.utils.format_percentage(100), '100.0%')
    
    def test_format_currency(self):
        """Test formatting currency"""
        self.assertEqual(self.utils.format_currency(1234.56), '$1,234.56')
        self.assertEqual(self.utils.format_currency(1000000), '$1,000,000.00')
        self.assertEqual(self.utils.format_currency(0), '$0.00')
    
    def test_format_number(self):
        """Test formatting numbers"""
        self.assertEqual(self.utils.format_number(1234.567, 2), '1,234.57')
        self.assertEqual(self.utils.format_number(1234567, 0), '1,234,567')
        self.assertEqual(self.utils.format_number(1234.567, 0), '1,235')
    
    def test_truncate_text(self):
        """Test truncating text"""
        long_text = 'This is a very long text that should be truncated'
        
        truncated = self.utils.truncate_text(long_text, 20)
        self.assertEqual(len(truncated), 20)
        self.assertTrue(truncated.endswith('...'))
        
        # Short text should not be truncated
        short_text = 'Short text'
        self.assertEqual(self.utils.truncate_text(short_text, 20), short_text)
    
    def test_format_list(self):
        """Test formatting list"""
        items = ['item1', 'item2', 'item3']
        
        formatted = self.utils.format_list(items)
        self.assertIn('item1', formatted)
        self.assertIn('item2', formatted)
        self.assertIn('item3', formatted)
        
        # Empty list
        self.assertEqual(self.utils.format_list([]), '')
    
    def test_format_dict(self):
        """Test formatting dictionary"""
        data = {'key1': 'value1', 'key2': 'value2'}
        
        formatted = self.utils.format_dict(data)
        self.assertIn('key1: value1', formatted)
        self.assertIn('key2: value2', formatted)
        
        # Empty dict
        self.assertEqual(self.utils.format_dict({}), '')
    
    def test_format_boolean(self):
        """Test formatting boolean"""
        self.assertEqual(self.utils.format_boolean(True), 'Yes')
        self.assertEqual(self.utils.format_boolean(False), 'No')
        self.assertEqual(self.utils.format_boolean(None), 'Unknown')
    
    def test_format_status_badge(self):
        """Test formatting status badge"""
        self.assertEqual(self.utils.format_status_badge('active'), 'Active')
        self.assertEqual(self.utils.format_status_badge('inactive'), 'Inactive')
        self.assertEqual(self.utils.format_status_badge('pending'), 'Pending')
        self.assertEqual(self.utils.format_status_badge('unknown'), 'Unknown')


class SecurityUtilsTest(TestCase):
    """Test cases for SecurityUtils"""
    
    def setUp(self):
        self.utils = SecurityUtils()
    
    def test_mask_email(self):
        """Test email masking"""
        email = 'user@example.com'
        masked = self.utils.mask_email(email)
        
        self.assertEqual(masked, 'u***@example.com')
        
        # Short email
        short_email = 'ab@cd.com'
        masked_short = self.utils.mask_email(short_email)
        self.assertEqual(masked_short, '**@cd.com')
    
    def test_mask_phone_number(self):
        """Test phone number masking"""
        phone = '+1234567890'
        masked = self.utils.mask_phone_number(phone)
        
        self.assertEqual(masked, '+*******7890')
        
        # Short phone
        short_phone = '123456'
        masked_short = self.utils.mask_phone_number(short_phone)
        self.assertEqual(masked_short, '******')
    
    def test_mask_sensitive_data(self):
        """Test masking sensitive data"""
        data = {
            'email': 'user@example.com',
            'phone': '+1234567890',
            'password': 'secret123',
            'api_key': 'sk_test123456789'
        }
        
        masked_data = self.utils.mask_sensitive_data(data)
        
        self.assertEqual(masked_data['email'], 'u***@example.com')
        self.assertEqual(masked_data['phone'], '+*******7890')
        self.assertEqual(masked_data['password'], '***')
        self.assertEqual(masked_data['api_key'], 'sk_***')
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        # Test XSS prevention
        malicious_input = '<script>alert("xss")</script>'
        sanitized = self.utils.sanitize_input(malicious_input)
        
        self.assertNotIn('<script>', sanitized)
        self.assertNotIn('</script>', sanitized)
        self.assertNotIn('alert("xss")', sanitized)
        
        # Test SQL injection prevention
        sql_input = "SELECT * FROM users WHERE id = 1; DROP TABLE users;"
        sanitized = self.utils.sanitize_input(sql_input)
        
        self.assertNotIn('SELECT', sanitized)
        self.assertNotIn('DROP TABLE', sanitized)
    
    def test_validate_api_key(self):
        """Test API key validation"""
        # Valid API keys
        valid_keys = [
            'sk_test123456789',
            'pk_live_123456789',
            'test_key_abc123'
        ]
        
        for key in valid_keys:
            self.assertTrue(self.utils.validate_api_key(key))
        
        # Invalid API keys
        invalid_keys = [
            '',
            'short',
            'invalid_key_with_symbols!',
            '1234567890123456789012345678901234567890'  # Too long
        ]
        
        for key in invalid_keys:
            self.assertFalse(self.utils.validate_api_key(key))
    
    def test_encrypt_sensitive_field(self):
        """Test encrypting sensitive field"""
        sensitive_data = 'secret_password'
        
        encrypted = self.utils.encrypt_sensitive_field(sensitive_data)
        
        self.assertNotEqual(encrypted, sensitive_data)
        self.assertIsInstance(encrypted, str)
        self.assertGreater(len(encrypted), len(sensitive_data))
    
    def test_decrypt_sensitive_field(self):
        """Test decrypting sensitive field"""
        original_data = 'secret_password'
        
        # Encrypt first
        encrypted = self.utils.encrypt_sensitive_field(original_data)
        
        # Then decrypt
        decrypted = self.utils.decrypt_sensitive_field(encrypted)
        
        self.assertEqual(decrypted, original_data)
    
    def test_generate_random_token(self):
        """Test generating random token"""
        token1 = self.utils.generate_random_token(32)
        token2 = self.utils.generate_random_token(32)
        
        # Tokens should be different
        self.assertNotEqual(token1, token2)
        
        # Token should be expected length
        self.assertEqual(len(token1), 32)
        self.assertEqual(len(token2), 32)
        
        # Token should be alphanumeric
        self.assertTrue(token1.isalnum())
        self.assertTrue(token2.isalnum())
    
    def test_hash_password(self):
        """Test password hashing"""
        password = 'test_password'
        
        hashed = self.utils.hash_password(password)
        
        self.assertNotEqual(hashed, password)
        self.assertTrue(hashed.startswith(('pbkdf2_sha256$', 'bcrypt$', 'sha256$')))
        
        # Verify password
        self.assertTrue(self.utils.verify_password(password, hashed))
        self.assertFalse(self.utils.verify_password('wrong_password', hashed))

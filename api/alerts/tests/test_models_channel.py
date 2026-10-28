"""
Tests for Channel Models
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, time

from api.alerts.models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog,
    ChannelRateLimit, AlertRecipient
)
from api.alerts.models.core import AlertRule, AlertLog

User = get_user_model()


class AlertChannelModelTest(TestCase):
    """Test cases for AlertChannel model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            priority=1,
            config={'smtp_host': 'smtp.example.com'},
            created_by=self.user
        )

    def test_alert_channel_creation(self):
        """Test AlertChannel creation"""
        self.assertEqual(self.alert_channel.name, 'Email Channel')
        self.assertEqual(self.alert_channel.channel_type, 'email')
        self.assertTrue(self.alert_channel.is_enabled)
        self.assertEqual(self.alert_channel.priority, 1)
        self.assertIsNotNone(self.alert_channel.created_at)

    def test_alert_channel_str_representation(self):
        """Test AlertChannel string representation"""
        expected = 'AlertChannel: Email Channel - email'
        self.assertEqual(str(self.alert_channel), expected)

    def test_alert_channel_get_type_display(self):
        """Test AlertChannel get_channel_type_display"""
        self.assertEqual(self.alert_channel.get_channel_type_display(), 'Email')
        self.alert_channel.channel_type = 'sms'
        self.assertEqual(self.alert_channel.get_channel_type_display(), 'SMS')
        self.alert_channel.channel_type = 'slack'
        self.assertEqual(self.alert_channel.get_channel_type_display(), 'Slack')

    def test_alert_channel_get_status_display(self):
        """Test AlertChannel get_status_display"""
        self.alert_channel.status = 'active'
        self.assertEqual(self.alert_channel.get_status_display(), 'Active')
        self.alert_channel.status = 'error'
        self.assertEqual(self.alert_channel.get_status_display(), 'Error')
        self.alert_channel.status = 'maintenance'
        self.assertEqual(self.alert_channel.get_status_display(), 'Maintenance')

    def test_alert_channel_mark_healthy(self):
        """Test AlertChannel mark_healthy sets status to active"""
        self.alert_channel.status = 'error'
        self.alert_channel.save()
        self.alert_channel.mark_healthy()
        self.assertEqual(self.alert_channel.status, 'active')

    def test_alert_channel_mark_error(self):
        """Test AlertChannel mark_error sets status and last_error_message"""
        self.alert_channel.mark_error('Connection timeout')
        self.assertEqual(self.alert_channel.status, 'error')
        self.assertEqual(self.alert_channel.last_error_message, 'Connection timeout')

    def test_alert_channel_get_health_status(self):
        """Test AlertChannel get_health_status returns correct health string"""
        self.alert_channel.status = 'active'
        self.alert_channel.save()
        self.assertEqual(self.alert_channel.get_health_status(), 'healthy')

        self.alert_channel.status = 'error'
        self.alert_channel.save()
        self.assertEqual(self.alert_channel.get_health_status(), 'critical')

        self.alert_channel.status = 'maintenance'
        self.alert_channel.save()
        self.assertEqual(self.alert_channel.get_health_status(), 'warning')

    def test_alert_channel_get_success_rate(self):
        """Test AlertChannel get_success_rate returns 0.0 when no counts"""
        rate = self.alert_channel.get_success_rate()
        self.assertEqual(rate, 0.0)

    def test_alert_channel_check_rate_limit(self):
        """Test AlertChannel check_rate_limit returns bool"""
        result = self.alert_channel.check_rate_limit()
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_alert_channel_send_notification(self):
        """Test AlertChannel send_notification returns bool"""
        result = self.alert_channel.send_notification(recipient='test@example.com', message='Test')
        self.assertIsInstance(result, bool)


class ChannelRouteModelTest(TestCase):
    """Test cases for ChannelRoute model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.source_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            created_by=self.user
        )
        self.destination_channel = AlertChannel.objects.create(
            name='SMS Channel',
            channel_type='sms',
            is_enabled=True,
            created_by=self.user
        )
        self.channel_route = ChannelRoute.objects.create(
            name='Email to SMS Route',
            route_type='rule_based',
            is_active=True,
            priority=1,
            escalation_delay_minutes=30
        )

    def test_channel_route_creation(self):
        """Test ChannelRoute creation"""
        self.assertEqual(self.channel_route.name, 'Email to SMS Route')
        self.assertEqual(self.channel_route.route_type, 'rule_based')
        self.assertTrue(self.channel_route.is_active)
        self.assertEqual(self.channel_route.priority, 1)
        self.assertEqual(self.channel_route.escalation_delay_minutes, 30)

    def test_channel_route_str_representation(self):
        """Test ChannelRoute string representation"""
        expected = 'ChannelRoute: Email to SMS Route - rule_based'
        self.assertEqual(str(self.channel_route), expected)

    def test_channel_route_get_type_display(self):
        """Test ChannelRoute get_route_type_display"""
        display = self.channel_route.get_route_type_display()
        self.assertIsInstance(display, str)
        self.assertTrue(len(display) > 0)

    def test_channel_route_should_route(self):
        """Test ChannelRoute is_active flag"""
        self.assertTrue(self.channel_route.is_active)

        self.channel_route.is_active = False
        self.channel_route.save()
        self.channel_route.refresh_from_db()
        self.assertFalse(self.channel_route.is_active)

        self.channel_route.is_active = True
        self.channel_route.save()
        self.channel_route.refresh_from_db()
        self.assertTrue(self.channel_route.is_active)

    def test_channel_route_get_source_channels_count(self):
        """Test ChannelRoute source_channels M2M count"""
        self.assertEqual(self.channel_route.source_channels.count(), 0)
        self.channel_route.source_channels.add(self.source_channel)
        self.assertEqual(self.channel_route.source_channels.count(), 1)

    def test_channel_route_get_destination_channels_count(self):
        """Test ChannelRoute destination_channels M2M count"""
        self.assertEqual(self.channel_route.destination_channels.count(), 0)
        self.channel_route.destination_channels.add(self.destination_channel)
        self.assertEqual(self.channel_route.destination_channels.count(), 1)


class ChannelHealthLogModelTest(TestCase):
    """Test cases for ChannelHealthLog model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            created_by=self.user
        )
        self.channel_health_log = ChannelHealthLog.objects.create(
            channel=self.alert_channel,
            status='healthy',
            response_time_ms=100.0,
            check_type='connectivity',
            error_message='',
            details={}
        )

    def test_channel_health_log_creation(self):
        """Test ChannelHealthLog creation"""
        self.assertEqual(self.channel_health_log.channel, self.alert_channel)
        self.assertEqual(self.channel_health_log.status, 'healthy')
        self.assertEqual(self.channel_health_log.response_time_ms, 100.0)
        self.assertEqual(self.channel_health_log.check_type, 'connectivity')
        self.assertIsNotNone(self.channel_health_log.checked_at)

    def test_channel_health_log_str_representation(self):
        """Test ChannelHealthLog string representation uses check_type"""
        expected = f'ChannelHealthLog: {self.channel_health_log.id} - connectivity'
        self.assertEqual(str(self.channel_health_log), expected)

    def test_channel_health_log_get_status_display(self):
        """Test ChannelHealthLog get_status_display"""
        self.assertEqual(self.channel_health_log.get_status_display(), 'Healthy')

        self.channel_health_log.status = 'warning'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Warning')

        self.channel_health_log.status = 'critical'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Critical')

        self.channel_health_log.status = 'unknown'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Unknown')

    def test_channel_health_log_get_type_display(self):
        """Test ChannelHealthLog get_check_type_display"""
        display = self.channel_health_log.get_check_type_display()
        self.assertEqual(display, 'Connectivity')

        self.channel_health_log.check_type = 'authentication'
        self.assertEqual(self.channel_health_log.get_check_type_display(), 'Authentication')

    def test_channel_health_log_is_healthy(self):
        """Test ChannelHealthLog is_healthy method"""
        self.assertTrue(self.channel_health_log.is_healthy())

        self.channel_health_log.status = 'critical'
        self.assertFalse(self.channel_health_log.is_healthy())

        self.channel_health_log.status = 'healthy'
        self.assertTrue(self.channel_health_log.is_healthy())

    def test_channel_health_log_get_response_time_display(self):
        """Test ChannelHealthLog get_response_time_display"""
        display = self.channel_health_log.get_response_time_display()
        self.assertEqual(display, '100.0 ms')

        self.channel_health_log.response_time_ms = None
        self.assertEqual(self.channel_health_log.get_response_time_display(), 'N/A')


class ChannelRateLimitModelTest(TestCase):
    """Test cases for ChannelRateLimit model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            created_by=self.user
        )
        # Signal auto-creates a ChannelRateLimit with limit_type='per_minute'
        self.channel_rate_limit = ChannelRateLimit.objects.filter(
            channel=self.alert_channel
        ).first()
        if not self.channel_rate_limit:
            self.channel_rate_limit = ChannelRateLimit.objects.create(
                channel=self.alert_channel,
                limit_type='token_bucket',
                window_seconds=60,
                max_requests=100,
                current_tokens=100,
                burst_size=10,
                refill_rate=1.0,
                bucket_size=100.0
            )

    def test_channel_rate_limit_creation(self):
        """Test ChannelRateLimit creation"""
        self.assertEqual(self.channel_rate_limit.channel, self.alert_channel)
        self.assertIsNotNone(self.channel_rate_limit.limit_type)
        self.assertIsNotNone(self.channel_rate_limit.max_requests)

    def test_channel_rate_limit_str_representation(self):
        """Test ChannelRateLimit string representation"""
        expected = f'ChannelRateLimit: {self.channel_rate_limit.id} - {self.channel_rate_limit.limit_type}'
        self.assertEqual(str(self.channel_rate_limit), expected)

    def test_channel_rate_limit_get_type_display(self):
        """Test ChannelRateLimit get_limit_type_display"""
        display = self.channel_rate_limit.get_limit_type_display()
        self.assertIsInstance(display, str)
        self.assertTrue(len(display) > 0)

    def test_channel_rate_limit_can_send(self):
        """Test ChannelRateLimit can_send_notification returns bool"""
        result = self.channel_rate_limit.can_send_notification()
        self.assertIsInstance(result, bool)

    def test_channel_rate_limit_consume_token(self):
        """Test ChannelRateLimit consume_token for token_bucket type"""
        # Update to token_bucket for this test
        self.channel_rate_limit.limit_type = 'token_bucket'
        self.channel_rate_limit.current_tokens = 10
        self.channel_rate_limit.bucket_size = 100.0
        self.channel_rate_limit.refill_rate = 1.0
        self.channel_rate_limit.save()

        result = self.channel_rate_limit.consume_token()
        self.assertTrue(result)
        self.channel_rate_limit.refresh_from_db()
        self.assertEqual(self.channel_rate_limit.current_tokens, 9.0)

        # Empty tokens - should reject
        self.channel_rate_limit.current_tokens = 0
        self.channel_rate_limit.save()
        result = self.channel_rate_limit.consume_token()
        self.assertFalse(result)

    def test_channel_rate_limit_refill_tokens(self):
        """Test ChannelRateLimit refill_tokens resets to max_requests"""
        self.channel_rate_limit.current_tokens = 10
        self.channel_rate_limit.save()

        self.channel_rate_limit.refill_tokens()
        self.channel_rate_limit.refresh_from_db()
        self.assertEqual(self.channel_rate_limit.current_tokens, self.channel_rate_limit.max_requests)

    def test_channel_rate_limit_get_utilization(self):
        """Test ChannelRateLimit get_utilization returns percentage"""
        self.channel_rate_limit.max_requests = 100
        self.channel_rate_limit.current_tokens = 50
        self.channel_rate_limit.save()

        utilization = self.channel_rate_limit.get_utilization()
        self.assertEqual(utilization, 50.0)

        self.channel_rate_limit.current_tokens = 100
        self.channel_rate_limit.save()
        utilization = self.channel_rate_limit.get_utilization()
        self.assertEqual(utilization, 0.0)

    def test_channel_rate_limit_reset(self):
        """Test ChannelRateLimit reset clears state"""
        self.channel_rate_limit.total_requests = 50
        self.channel_rate_limit.rejected_requests = 10
        self.channel_rate_limit.current_tokens = 5
        self.channel_rate_limit.save()

        self.channel_rate_limit.reset()
        self.channel_rate_limit.refresh_from_db()

        self.assertEqual(self.channel_rate_limit.total_requests, 0)
        self.assertEqual(self.channel_rate_limit.rejected_requests, 0)
        self.assertEqual(
            self.channel_rate_limit.current_tokens,
            self.channel_rate_limit.max_requests
        )


class AlertRecipientModelTest(TestCase):
    """Test cases for AlertRecipient model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.alert_recipient = AlertRecipient.objects.create(
            name='Test User',
            recipient_type='email',
            email_address='test@example.com',
            phone_number='+1234567890',
            priority='medium',
            is_active=True,
            max_notifications_per_hour=50,
            max_notifications_per_day=200
        )

    def test_alert_recipient_creation(self):
        """Test AlertRecipient creation"""
        self.assertEqual(self.alert_recipient.name, 'Test User')
        self.assertEqual(self.alert_recipient.recipient_type, 'email')
        self.assertEqual(self.alert_recipient.email_address, 'test@example.com')
        self.assertEqual(self.alert_recipient.priority, 'medium')
        self.assertTrue(self.alert_recipient.is_active)

    def test_alert_recipient_str_representation(self):
        """Test AlertRecipient string representation"""
        result = str(self.alert_recipient)
        self.assertIsInstance(result, str)
        self.assertIn('Test User', result)

    def test_alert_recipient_get_type_display(self):
        """Test AlertRecipient get_recipient_type_display"""
        display = self.alert_recipient.get_recipient_type_display()
        self.assertIsInstance(display, str)
        self.assertTrue(len(display) > 0)

    def test_alert_recipient_is_available_now(self):
        """Test AlertRecipient is_available_now reflects is_active"""
        self.assertTrue(self.alert_recipient.is_active)
        self.assertTrue(self.alert_recipient.is_available_now())

        self.alert_recipient.is_active = False
        self.alert_recipient.save()
        self.assertFalse(self.alert_recipient.is_available_now())

    def test_alert_recipient_get_contact_info(self):
        """Test AlertRecipient get_contact_info returns type-appropriate info"""
        contact_info = self.alert_recipient.get_contact_info()
        self.assertIsInstance(contact_info, dict)
        self.assertEqual(contact_info['type'], 'email')
        self.assertEqual(contact_info['email'], 'test@example.com')
        self.assertEqual(contact_info['name'], 'Test User')

    def test_alert_recipient_get_contact_info_phone_type(self):
        """Test get_contact_info for a phone-type recipient"""
        phone_recipient = AlertRecipient.objects.create(
            name='Phone User', recipient_type='phone',
            phone_number='+19998887777', is_active=True,
        )
        contact_info = phone_recipient.get_contact_info()
        self.assertEqual(contact_info['type'], 'phone')
        self.assertEqual(contact_info['phone'], '+19998887777')

    def test_alert_recipient_get_contact_info_webhook_type(self):
        """Test get_contact_info for a webhook-type recipient"""
        webhook_recipient = AlertRecipient.objects.create(
            name='Webhook Target', recipient_type='webhook',
            webhook_url='https://example.com/hook', is_active=True,
        )
        contact_info = webhook_recipient.get_contact_info()
        self.assertEqual(contact_info['type'], 'webhook')
        self.assertEqual(contact_info['url'], 'https://example.com/hook')

    def test_alert_recipient_can_receive_notification(self):
        """Test AlertRecipient can_receive_notification when active"""
        self.assertTrue(self.alert_recipient.is_active)
        result = self.alert_recipient.can_receive_notification()
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_alert_recipient_increment_notification_count(self):
        """Test AlertRecipient increment_notification_count"""
        self.alert_recipient.notification_count = 0
        self.alert_recipient.increment_notification_count()
        self.assertEqual(self.alert_recipient.notification_count, 1)

        self.alert_recipient.increment_notification_count()
        self.assertEqual(self.alert_recipient.notification_count, 2)

    def test_alert_recipient_reset_daily_counters(self):
        """Test AlertRecipient reset_counters clears notification_count"""
        self.alert_recipient.notification_count = 10
        self.alert_recipient.reset_counters()
        self.assertEqual(self.alert_recipient.notification_count, 0)

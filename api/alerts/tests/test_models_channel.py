"""
Tests for Channel Models
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, ChannelRateLimit, AlertRecipient
)


class AlertChannelModelTest(TestCase):
    """Test cases for AlertChannel model"""
    
    def setUp(self):
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            description='Primary email notification channel',
            is_enabled=True,
            priority=1,
            config={
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'alerts@example.com',
                'use_tls': True
            },
            webhook_url='https://api.example.com/webhooks/email'
        )
    
    def test_alert_channel_creation(self):
        """Test AlertChannel creation"""
        self.assertEqual(self.alert_channel.name, 'Email Channel')
        self.assertEqual(self.alert_channel.channel_type, 'email')
        self.assertEqual(self.alert_channel.priority, 1)
        self.assertTrue(self.alert_channel.is_enabled)
        self.assertEqual(self.alert_channel.status, 'active')
        self.assertIsInstance(self.alert_channel.config, dict)
    
    def test_alert_channel_str_representation(self):
        """Test AlertChannel string representation"""
        expected = f'AlertChannel: {self.alert_channel.name} - email'
        self.assertEqual(str(self.alert_channel), expected)
    
    def test_alert_channel_get_type_display(self):
        """Test AlertChannel type display"""
        self.assertEqual(self.alert_channel.get_type_display(), 'Email')
        
        self.alert_channel.channel_type = 'sms'
        self.assertEqual(self.alert_channel.get_type_display(), 'SMS')
        
        self.alert_channel.channel_type = 'telegram'
        self.assertEqual(self.alert_channel.get_type_display(), 'Telegram')
        
        self.alert_channel.channel_type = 'webhook'
        self.assertEqual(self.alert_channel.get_type_display(), 'Webhook')
    
    def test_alert_channel_get_status_display(self):
        """Test AlertChannel status display"""
        self.assertEqual(self.alert_channel.get_status_display(), 'Active')
        
        self.alert_channel.status = 'inactive'
        self.assertEqual(self.alert_channel.get_status_display(), 'Inactive')
        
        self.alert_channel.status = 'error'
        self.assertEqual(self.alert_channel.get_status_display(), 'Error')
        
        self.alert_channel.status = 'maintenance'
        self.assertEqual(self.alert_channel.get_status_display(), 'Maintenance')
    
    def test_alert_channel_mark_healthy(self):
        """Test AlertChannel mark healthy method"""
        self.alert_channel.status = 'error'
        self.alert_channel.consecutive_failures = 5
        self.alert_channel.save()
        
        self.alert_channel.mark_healthy()
        
        self.assertEqual(self.alert_channel.status, 'active')
        self.assertEqual(self.alert_channel.consecutive_failures, 0)
        self.assertIsNotNone(self.alert_channel.last_success)
    
    def test_alert_channel_mark_error(self):
        """Test AlertChannel mark error method"""
        self.alert_channel.mark_error('Connection failed')
        
        self.assertEqual(self.alert_channel.status, 'error')
        self.assertEqual(self.alert_channel.consecutive_failures, 1)
        self.assertEqual(self.alert_channel.error_message, 'Connection failed')
        self.assertIsNotNone(self.alert_channel.last_failure)
    
    def test_alert_channel_get_health_status(self):
        """Test AlertChannel health status calculation"""
        # Healthy channel
        self.alert_channel.status = 'active'
        self.alert_channel.consecutive_failures = 0
        self.alert_channel.save()
        
        health = self.alert_channel.get_health_status()
        self.assertEqual(health, 'healthy')
        
        # Warning channel
        self.alert_channel.consecutive_failures = 2
        self.alert_channel.save()
        
        health = self.alert_channel.get_health_status()
        self.assertEqual(health, 'warning')
        
        # Critical channel
        self.alert_channel.consecutive_failures = 5
        self.alert_channel.save()
        
        health = self.alert_channel.get_health_status()
        self.assertEqual(health, 'critical')
    
    def test_alert_channel_get_success_rate(self):
        """Test AlertChannel success rate calculation"""
        # No notifications sent
        success_rate = self.alert_channel.get_success_rate()
        self.assertEqual(success_rate, 0)
        
        # Some notifications sent
        self.alert_channel.total_sent = 100
        self.alert_channel.total_failed = 10
        self.alert_channel.save()
        
        success_rate = self.alert_channel.get_success_rate()
        expected = (100 - 10) / 100 * 100
        self.assertEqual(success_rate, expected)
    
    def test_alert_channel_check_rate_limit(self):
        """Test AlertChannel rate limit checking"""
        # No rate limit
        self.assertTrue(self.alert_channel.check_rate_limit())
        
        # With rate limit
        self.alert_channel.rate_limit_per_minute = 10
        self.alert_channel.save()
        
        # Simulate recent notifications
        for i in range(5):
            ChannelRateLimit.objects.create(
                channel=self.alert_channel,
                limit_type='per_minute',
                window_seconds=60,
                max_requests=10,
                current_tokens=10 - i,
                last_refill=timezone.now()
            )
        
        self.assertTrue(self.alert_channel.check_rate_limit())
    
    def test_alert_channel_send_notification(self):
        """Test AlertChannel send notification method"""
        # This would typically call the actual notification service
        # For testing, we'll just verify the method exists and can be called
        result = self.alert_channel.send_notification(
            message='Test notification',
            recipient='test@example.com',
            subject='Test Subject'
        )
        
        # The actual implementation would depend on the notification service
        # This test verifies the method signature
        self.assertIsNotNone(result)


class ChannelRouteModelTest(TestCase):
    """Test cases for ChannelRoute model"""
    
    def setUp(self):
        self.source_channel = AlertChannel.objects.create(
            name='Source Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.destination_channel = AlertChannel.objects.create(
            name='Destination Channel',
            channel_type='sms',
            is_enabled=True
        )
        
        self.channel_route = ChannelRoute.objects.create(
            name='Email to SMS Route',
            route_type='escalation',
            is_active=True,
            priority=1,
            escalation_delay_minutes=30,
            escalate_after_failures=3
        )
        
        self.channel_route.source_channels.add(self.source_channel)
        self.channel_route.destination_channels.add(self.destination_channel)
    
    def test_channel_route_creation(self):
        """Test ChannelRoute creation"""
        self.assertEqual(self.channel_route.name, 'Email to SMS Route')
        self.assertEqual(self.channel_route.route_type, 'escalation')
        self.assertEqual(self.channel_route.priority, 1)
        self.assertTrue(self.channel_route.is_active)
        self.assertEqual(self.channel_route.escalation_delay_minutes, 30)
    
    def test_channel_route_str_representation(self):
        """Test ChannelRoute string representation"""
        expected = f'ChannelRoute: {self.channel_route.name} - escalation'
        self.assertEqual(str(self.channel_route), expected)
    
    def test_channel_route_get_type_display(self):
        """Test ChannelRoute type display"""
        self.assertEqual(self.channel_route.get_type_display(), 'Escalation')
        
        self.channel_route.route_type = 'routing'
        self.assertEqual(self.channel_route.get_type_display(), 'Routing')
        
        self.channel_route.route_type = 'broadcast'
        self.assertEqual(self.channel_route.get_type_display(), 'Broadcast')
    
    def test_channel_route_should_route(self):
        """Test ChannelRoute should route logic"""
        # Test active route
        self.assertTrue(self.channel_route.should_route())
        
        # Test inactive route
        self.channel_route.is_active = False
        self.channel_route.save()
        self.assertFalse(self.channel_route.should_route())
        
        # Test time-based routing
        self.channel_route.is_active = True
        self.channel_route.start_time = timezone.now().time()
        self.channel_route.end_time = (timezone.now() + timezone.timedelta(hours=1)).time()
        self.channel_route.save()
        
        self.assertTrue(self.channel_route.should_route())
    
    def test_channel_route_get_source_channels_count(self):
        """Test ChannelRoute source channels count"""
        count = self.channel_route.get_source_channels_count()
        self.assertEqual(count, 1)
        
        # Add another source channel
        another_channel = AlertChannel.objects.create(
            name='Another Source',
            channel_type='telegram',
            is_enabled=True
        )
        self.channel_route.source_channels.add(another_channel)
        
        count = self.channel_route.get_source_channels_count()
        self.assertEqual(count, 2)
    
    def test_channel_route_get_destination_channels_count(self):
        """Test ChannelRoute destination channels count"""
        count = self.channel_route.get_destination_channels_count()
        self.assertEqual(count, 1)
        
        # Add another destination channel
        another_channel = AlertChannel.objects.create(
            name='Another Destination',
            channel_type='webhook',
            is_enabled=True
        )
        self.channel_route.destination_channels.add(another_channel)
        
        count = self.channel_route.get_destination_channels_count()
        self.assertEqual(count, 2)


class ChannelHealthLogModelTest(TestCase):
    """Test cases for ChannelHealthLog model"""
    
    def setUp(self):
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.channel_health_log = ChannelHealthLog.objects.create(
            channel=self.alert_channel,
            check_name='smtp_connection',
            check_type='connectivity',
            status='healthy',
            response_time_ms=150.5,
            status_message='Connection successful'
        )
    
    def test_channel_health_log_creation(self):
        """Test ChannelHealthLog creation"""
        self.assertEqual(self.channel_health_log.channel, self.alert_channel)
        self.assertEqual(self.channel_health_log.check_name, 'smtp_connection')
        self.assertEqual(self.channel_health_log.check_type, 'connectivity')
        self.assertEqual(self.channel_health_log.status, 'healthy')
        self.assertEqual(self.channel_health_log.response_time_ms, 150.5)
        self.assertIsNotNone(self.channel_health_log.checked_at)
    
    def test_channel_health_log_str_representation(self):
        """Test ChannelHealthLog string representation"""
        expected = f'ChannelHealthLog: {self.channel_health_log.id} - smtp_connection'
        self.assertEqual(str(self.channel_health_log), expected)
    
    def test_channel_health_log_get_status_display(self):
        """Test ChannelHealthLog status display"""
        self.assertEqual(self.channel_health_log.get_status_display(), 'Healthy')
        
        self.channel_health_log.status = 'warning'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Warning')
        
        self.channel_health_log.status = 'critical'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Critical')
        
        self.channel_health_log.status = 'error'
        self.assertEqual(self.channel_health_log.get_status_display(), 'Error')
    
    def test_channel_health_log_get_type_display(self):
        """Test ChannelHealthLog type display"""
        self.assertEqual(self.channel_health_log.get_type_display(), 'Connectivity')
        
        self.channel_health_log.check_type = 'performance'
        self.assertEqual(self.channel_health_log.get_type_display(), 'Performance')
        
        self.channel_health_log.check_type = 'availability'
        self.assertEqual(self.channel_health_log.get_type_display(), 'Availability')
    
    def test_channel_health_log_is_healthy(self):
        """Test ChannelHealthLog is healthy check"""
        self.assertTrue(self.channel_health_log.is_healthy())
        
        self.channel_health_log.status = 'warning'
        self.assertFalse(self.channel_health_log.is_healthy())
        
        self.channel_health_log.status = 'critical'
        self.assertFalse(self.channel_health_log.is_healthy())
    
    def test_channel_health_log_get_response_time_display(self):
        """Test ChannelHealthLog response time display"""
        display = self.channel_health_log.get_response_time_display()
        self.assertEqual(display, '150.5 ms')
        
        # Test with None response time
        self.channel_health_log.response_time_ms = None
        self.channel_health_log.save()
        display = self.channel_health_log.get_response_time_display()
        self.assertEqual(display, 'N/A')


class ChannelRateLimitModelTest(TestCase):
    """Test cases for ChannelRateLimit model"""
    
    def setUp(self):
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.channel_rate_limit = ChannelRateLimit.objects.create(
            channel=self.alert_channel,
            limit_type='per_minute',
            window_seconds=60,
            max_requests=100,
            current_tokens=100,
            last_refill=timezone.now()
        )
    
    def test_channel_rate_limit_creation(self):
        """Test ChannelRateLimit creation"""
        self.assertEqual(self.channel_rate_limit.channel, self.alert_channel)
        self.assertEqual(self.channel_rate_limit.limit_type, 'per_minute')
        self.assertEqual(self.channel_rate_limit.window_seconds, 60)
        self.assertEqual(self.channel_rate_limit.max_requests, 100)
        self.assertEqual(self.channel_rate_limit.current_tokens, 100)
    
    def test_channel_rate_limit_str_representation(self):
        """Test ChannelRateLimit string representation"""
        expected = f'ChannelRateLimit: {self.channel_rate_limit.id} - per_minute'
        self.assertEqual(str(self.channel_rate_limit), expected)
    
    def test_channel_rate_limit_get_type_display(self):
        """Test ChannelRateLimit type display"""
        self.assertEqual(self.channel_rate_limit.get_type_display(), 'Per Minute')
        
        self.channel_rate_limit.limit_type = 'per_hour'
        self.assertEqual(self.channel_rate_limit.get_type_display(), 'Per Hour')
        
        self.channel_rate_limit.limit_type = 'per_day'
        self.assertEqual(self.channel_rate_limit.get_type_display(), 'Per Day')
    
    def test_channel_rate_limit_can_send(self):
        """Test ChannelRateLimit can send check"""
        # With tokens available
        self.assertTrue(self.channel_rate_limit.can_send())
        
        # With no tokens available
        self.channel_rate_limit.current_tokens = 0
        self.channel_rate_limit.save()
        self.assertFalse(self.channel_rate_limit.can_send())
    
    def test_channel_rate_limit_consume_token(self):
        """Test ChannelRateLimit consume token method"""
        initial_tokens = self.channel_rate_limit.current_tokens
        
        self.channel_rate_limit.consume_token()
        
        self.assertEqual(self.channel_rate_limit.current_tokens, initial_tokens - 1)
    
    def test_channel_rate_limit_refill_tokens(self):
        """Test ChannelRateLimit refill tokens method"""
        self.channel_rate_limit.current_tokens = 50
        self.channel_rate_limit.save()
        
        self.channel_rate_limit.refill_tokens()
        
        self.assertEqual(self.channel_rate_limit.current_tokens, self.channel_rate_limit.max_requests)
        self.assertIsNotNone(self.channel_rate_limit.last_refill)
    
    def test_channel_rate_limit_get_utilization(self):
        """Test ChannelRateLimit utilization calculation"""
        # Half utilized
        self.channel_rate_limit.current_tokens = 50
        self.channel_rate_limit.save()
        
        utilization = self.channel_rate_limit.get_utilization()
        expected = ((100 - 50) / 100) * 100
        self.assertEqual(utilization, expected)
        
        # Fully utilized
        self.channel_rate_limit.current_tokens = 0
        self.channel_rate_limit.save()
        
        utilization = self.channel_rate_limit.get_utilization()
        self.assertEqual(utilization, 100)
    
    def test_channel_rate_limit_reset(self):
        """Test ChannelRateLimit reset method"""
        self.channel_rate_limit.current_tokens = 0
        self.channel_rate_limit.total_requests = 500
        self.channel_rate_limit.rejected_requests = 50
        self.channel_rate_limit.save()
        
        self.channel_rate_limit.reset()
        
        self.assertEqual(self.channel_rate_limit.current_tokens, self.channel_rate_limit.max_requests)
        self.assertEqual(self.channel_rate_limit.total_requests, 0)
        self.assertEqual(self.channel_rate_limit.rejected_requests, 0)


class AlertRecipientModelTest(TestCase):
    """Test cases for AlertRecipient model"""
    
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_recipient = AlertRecipient.objects.create(
            name='Test User',
            recipient_type='user',
            user=self.user,
            email_address='test@example.com',
            phone_number='+1234567890',
            priority=1,
            is_active=True,
            timezone='UTC',
            max_notifications_per_hour=50
        )
    
    def test_alert_recipient_creation(self):
        """Test AlertRecipient creation"""
        self.assertEqual(self.alert_recipient.name, 'Test User')
        self.assertEqual(self.alert_recipient.recipient_type, 'user')
        self.assertEqual(self.alert_recipient.user, self.user)
        self.assertEqual(self.alert_recipient.email_address, 'test@example.com')
        self.assertEqual(self.alert_recipient.phone_number, '+1234567890')
        self.assertTrue(self.alert_recipient.is_active)
    
    def test_alert_recipient_str_representation(self):
        """Test AlertRecipient string representation"""
        expected = f'AlertRecipient: {self.alert_recipient.name} - user'
        self.assertEqual(str(self.alert_recipient), expected)
    
    def test_alert_recipient_get_type_display(self):
        """Test AlertRecipient type display"""
        self.assertEqual(self.alert_recipient.get_type_display(), 'User')
        
        self.alert_recipient.recipient_type = 'email'
        self.assertEqual(self.alert_recipient.get_type_display(), 'Email')
        
        self.alert_recipient.recipient_type = 'phone'
        self.assertEqual(self.alert_recipient.get_type_display(), 'Phone')
        
        self.alert_recipient.recipient_type = 'webhook'
        self.assertEqual(self.alert_recipient.get_type_display(), 'Webhook')
    
    def test_alert_recipient_is_available_now(self):
        """Test AlertRecipient availability check"""
        # Always available (no time restrictions)
        self.assertTrue(self.alert_recipient.is_available_now())
        
        # With time restrictions
        self.alert_recipient.available_hours_start = timezone.now().time()
        self.alert_recipient.available_hours_end = (timezone.now() + timezone.timedelta(hours=8)).time()
        self.alert_recipient.save()
        
        self.assertTrue(self.alert_recipient.is_available_now())
        
        # Outside available hours
        self.alert_recipient.available_hours_start = (timezone.now() + timezone.timedelta(hours=4)).time()
        self.alert_recipient.available_hours_end = (timezone.now() + timezone.timedelta(hours=12)).time()
        self.alert_recipient.save()
        
        self.assertFalse(self.alert_recipient.is_available_now())
    
    def test_alert_recipient_get_contact_info(self):
        """Test AlertRecipient contact info retrieval"""
        contact_info = self.alert_recipient.get_contact_info()
        
        expected = {
            'email': 'test@example.com',
            'phone': '+1234567890',
            'user': self.user,
            'name': 'Test User'
        }
        
        self.assertEqual(contact_info['email'], expected['email'])
        self.assertEqual(contact_info['phone'], expected['phone'])
        self.assertEqual(contact_info['user'], expected['user'])
        self.assertEqual(contact_info['name'], expected['name'])
    
    def test_alert_recipient_can_receive_notification(self):
        """Test AlertRecipient can receive notification check"""
        # Active recipient
        self.assertTrue(self.alert_recipient.can_receive_notification())
        
        # Inactive recipient
        self.alert_recipient.is_active = False
        self.alert_recipient.save()
        self.assertFalse(self.alert_recipient.can_receive_notification())
        
        # Rate limited
        self.alert_recipient.is_active = True
        self.alert_recipient.notifications_sent_today = 100
        self.alert_recipient.max_notifications_per_hour = 50
        self.alert_recipient.save()
        self.assertFalse(self.alert_recipient.can_receive_notification())
    
    def test_alert_recipient_increment_notification_count(self):
        """Test AlertRecipient increment notification count"""
        initial_count = self.alert_recipient.notifications_sent_today
        
        self.alert_recipient.increment_notification_count()
        
        self.assertEqual(self.alert_recipient.notifications_sent_today, initial_count + 1)
        self.assertIsNotNone(self.alert_recipient.last_notification_at)
    
    def test_alert_recipient_reset_daily_counters(self):
        """Test AlertRecipient reset daily counters"""
        self.alert_recipient.notifications_sent_today = 100
        self.alert_recipient.save()
        
        self.alert_recipient.reset_daily_counters()
        
        self.assertEqual(self.alert_recipient.notifications_sent_today, 0)

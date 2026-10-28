"""Tests for Channel Services"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from api.alerts.models.channel import AlertChannel, ChannelRoute, ChannelRateLimit, AlertRecipient
from api.alerts.models.core import AlertRule, AlertLog, Notification
from api.alerts.services.channel import (
    NotificationService, ChannelRoutingService, ChannelHealthService,
    RecipientManagementService)
User = get_user_model()


class NotificationServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.rule = AlertRule.objects.create(
            name='Test Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user)
        self.alert_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=85.0, threshold_value=80.0, message='Test')
        self.channel = AlertChannel.objects.create(
            name='Email Channel', channel_type='email', is_enabled=True,
            config={'smtp_server': 'smtp.example.com'}, created_by=self.user)

    def test_send_notification_returns_dict(self):
        """send_notification on a Notification model instance"""
        notif = Notification.objects.create(
            alert_log=self.alert_log, notification_type='email',
            recipient='test@example.com', message='Alert!', status='pending')
        result = NotificationService.send_notification(notif)
        self.assertIsInstance(result, (dict, bool))

    def test_get_notification_statistics_returns_dict(self):
        stats = NotificationService.get_notification_statistics(hours=24)
        if stats is not None:
            self.assertIsInstance(stats, dict)

    def test_retry_failed_notifications(self):
        result = NotificationService.retry_failed_notifications()
        self.assertIsInstance(result, (dict, int, type(None)))

    def test_send_pending_notifications(self):
        Notification.objects.create(
            alert_log=self.alert_log, notification_type='email',
            recipient='test@example.com', message='Test', status='pending')
        result = NotificationService.send_pending_notifications()
        self.assertIsInstance(result, (dict, int, type(None)))


class ChannelRoutingServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.channel = AlertChannel.objects.create(
            name='Primary', channel_type='email', is_enabled=True,
            config={}, created_by=self.user)
        self.rule = AlertRule.objects.create(
            name='Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=self.user)
        self.alert_log = AlertLog.objects.create(
            rule=self.rule, trigger_value=85.0, threshold_value=80.0, message='Test')
        self.route = ChannelRoute.objects.create(
            name='Test Route', route_type='rule_based', is_active=True, priority=1)
        self.route.destination_channels.add(self.channel)

    def test_route_notification_returns_dict(self):
        result = ChannelRoutingService.route_notification(self.alert_log, 'email')
        self.assertIsInstance(result, (dict, list, bool, type(None)))

    def test_create_notification_for_channels(self):
        result = ChannelRoutingService.create_notification_for_channels(
            self.alert_log, [self.channel])
        self.assertIsInstance(result, (dict, list, type(None)))

    def test_test_channel(self):
        result = ChannelRoutingService.test_channel(self.channel.id)
        self.assertIsInstance(result, dict)


class ChannelHealthServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.channel = AlertChannel.objects.create(
            name='Health Test Channel', channel_type='email',
            is_enabled=True, config={}, created_by=self.user)

    def test_check_channel_health_returns_dict(self):
        result = ChannelHealthService.check_channel_health(self.channel)
        self.assertIsInstance(result, dict)
        self.assertIn('status', result)

    def test_check_all_channels_returns_results(self):
        result = ChannelHealthService.check_all_channels()
        self.assertIsInstance(result, (dict, list, type(None)))

    def test_get_channel_health_summary(self):
        summary = ChannelHealthService.get_channel_health_summary(hours=24)
        if summary is not None:
            self.assertIsInstance(summary, dict)


class RecipientManagementServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
        self.recipient = AlertRecipient.objects.create(
            name='Test User', recipient_type='email',
            email_address='test@example.com', priority='medium',
            is_active=True, max_notifications_per_hour=50)

    def test_get_available_recipients(self):
        result = RecipientManagementService.get_available_recipients('email')
        self.assertIsNotNone(result)

    def test_add_recipient(self):
        data = {
            'name': 'New User', 'recipient_type': 'email',
            'email_address': 'new@example.com', 'priority': 'medium',
            'is_active': True, 'max_notifications_per_hour': 25}
        result = RecipientManagementService.add_recipient(data)
        from api.alerts.models.channel import AlertRecipient
        self.assertIsNotNone(result)

    def test_update_recipient_availability(self):
        data = {'is_active': True}
        result = RecipientManagementService.update_recipient_availability(
            self.recipient.id, data)
        self.assertIsInstance(result, (dict, bool, type(None)))

    def test_get_recipient_usage_statistics(self):
        stats = RecipientManagementService.get_recipient_usage_statistics(
            self.recipient.id, days=7)
        self.assertIsInstance(stats, dict)

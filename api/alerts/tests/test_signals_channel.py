"""
Tests for Channel Signals — FIXED
Covers: channel_created, channel_enabled, channel_disabled, channel_updated,
        route_created, route_updated, recipient_availability_changed signals.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from api.alerts.models.channel import AlertChannel, ChannelRoute, AlertRecipient, ChannelHealthLog, ChannelRateLimit
from api.alerts.signals.channel import (
    channel_created, channel_updated, channel_enabled, channel_disabled,
    route_created, route_updated, recipient_availability_changed,
    channel_failure, channel_recovery, health_log_created,
    rate_limit_created, rate_limit_reset,
    channel_health_checked, channel_health_updated, channel_test_sent, routing_updated,
)

User = get_user_model()


class ChannelSignalsTest(TestCase):
    """Tests for AlertChannel signals"""

    def setUp(self):
        self.signal_received = False
        self.signal_data = {}
        self.user = User.objects.create_user(
            username='chsig', email='chsig@example.com', password='testpass'
        )

    def _handler(self, sender, **kwargs):
        self.signal_received = True
        self.signal_data = kwargs

    def test_channel_created_signal(self):
        channel_created.connect(self._handler)
        channel = AlertChannel.objects.create(
            name='Signal Test Channel', channel_type='slack', is_enabled=True,
            config={'webhook_url': 'https://hooks.slack.com/test'})
        self.assertTrue(self.signal_received)
        channel_created.disconnect(self._handler)

    def test_channel_enabled_signal(self):
        channel = AlertChannel.objects.create(
            name='Enable Test', channel_type='email', is_enabled=False,
            config={'to': 'ops@example.com'})
        channel_enabled.connect(self._handler)
        channel.is_enabled = True
        channel.save()
        self.assertTrue(self.signal_received)
        channel_enabled.disconnect(self._handler)

    def test_channel_updated_signal_fires(self):
        channel = AlertChannel.objects.create(
            name='Update Test', channel_type='slack', is_enabled=True,
            config={'webhook_url': 'https://test.slack.com'})
        channel_updated.connect(self._handler)
        channel.name = 'Updated Channel Name'
        channel.save()
        # Signal fires on update
        self.assertTrue(self.signal_received)
        channel_updated.disconnect(self._handler)


class RouteSignalsTest(TestCase):
    """Tests for ChannelRoute signals"""

    def setUp(self):
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_route_created_signal(self):
        route_created.connect(self._handler)
        route = ChannelRoute.objects.create(
            name='Signal Route', route_type='severity_based', is_active=True)
        self.assertTrue(self.signal_received)
        route_created.disconnect(self._handler)

    def test_route_updated_signal(self):
        route = ChannelRoute.objects.create(
            name='Update Route', route_type='severity_based', is_active=True)
        route_updated.connect(self._handler)
        route.is_active = False
        route.save()
        self.assertTrue(self.signal_received)
        route_updated.disconnect(self._handler)


class RecipientSignalsTest(TestCase):
    """Tests for AlertRecipient availability signals"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='recsig', email='recsig@example.com', password='testpass'
        )
        self.channel = AlertChannel.objects.create(
            name='Rec Channel', channel_type='email', is_enabled=True,
            config={'to': 'recsig@example.com'})
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_recipient_availability_changed_signal(self):
        recipient = AlertRecipient.objects.create(
            name='Test Recipient',
            recipient_type='user',
            user=self.user,
            email_address='recsig@example.com',
            is_active=True)
        recipient_availability_changed.connect(self._handler)
        recipient.is_active = False
        recipient.save()
        self.assertTrue(self.signal_received)
        recipient_availability_changed.disconnect(self._handler)


class NewlyWiredChannelSignalsTest(TestCase):
    """Real behavioral tests for 5 more signals confirmed never fired anywhere
    before this session: channel_failure, channel_recovery, health_log_created,
    rate_limit_created, rate_limit_reset."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='newchsig', email='newchsig@example.com', password='testpass', is_staff=True)
        self.channel = AlertChannel.objects.create(
            name='New Signal Channel', channel_type='email', is_enabled=True,
            created_by=self.user)
        self.signal_received = False

    def _handler(self, sender, **kwargs):
        self.signal_received = True

    def test_health_log_created_signal(self):
        health_log_created.connect(self._handler)
        ChannelHealthLog.objects.create(
            channel=self.channel, status='healthy', check_type='connectivity')
        self.assertTrue(self.signal_received)
        health_log_created.disconnect(self._handler)

    def test_channel_failure_signal_fires_on_critical_health_log(self):
        channel_failure.connect(self._handler)
        ChannelHealthLog.objects.create(
            channel=self.channel, status='critical', check_type='connectivity',
            error_message='Connection refused')
        self.assertTrue(self.signal_received)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, 'error')
        channel_failure.disconnect(self._handler)

    def test_channel_recovery_signal_fires_when_healthy_after_error(self):
        ChannelHealthLog.objects.create(
            channel=self.channel, status='critical', check_type='connectivity')
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, 'error')
        channel_recovery.connect(self._handler)
        ChannelHealthLog.objects.create(
            channel=self.channel, status='healthy', check_type='connectivity')
        self.assertTrue(self.signal_received)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, 'active')
        channel_recovery.disconnect(self._handler)

    def test_rate_limit_created_signal_fires_on_channel_creation(self):
        rate_limit_created.connect(self._handler)
        AlertChannel.objects.create(
            name='RL Created Signal Channel', channel_type='webhook', is_enabled=True)
        self.assertTrue(self.signal_received)
        rate_limit_created.disconnect(self._handler)

    def test_rate_limit_reset_signal_fires_on_reset(self):
        rl = ChannelRateLimit.objects.get(channel=self.channel)
        rate_limit_reset.connect(self._handler)
        rl.reset()
        self.assertTrue(self.signal_received)
        rate_limit_reset.disconnect(self._handler)

    def test_channel_disabled_signal_fires_on_direct_save(self):
        channel_disabled.connect(self._handler)
        self.channel.is_enabled = False
        self.channel.save()
        self.assertTrue(self.signal_received)
        channel_disabled.disconnect(self._handler)

    def test_channel_health_checked_signal_fires_on_any_health_log(self):
        channel_health_checked.connect(self._handler)
        ChannelHealthLog.objects.create(
            channel=self.channel, status='healthy', check_type='connectivity')
        self.assertTrue(self.signal_received)
        channel_health_checked.disconnect(self._handler)

    def test_channel_health_updated_signal_fires_when_channel_status_changes(self):
        channel_health_updated.connect(self._handler)
        ChannelHealthLog.objects.create(
            channel=self.channel, status='critical', check_type='connectivity')
        self.assertTrue(self.signal_received)
        channel_health_updated.disconnect(self._handler)

    def test_channel_test_sent_signal_fires_on_test_action(self):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=self.user)
        channel_test_sent.connect(self._handler)
        client.post(f'/channel/{self.channel.id}/test/')
        self.assertTrue(self.signal_received)
        channel_test_sent.disconnect(self._handler)

    def test_routing_updated_signal_fires_on_route_save(self):
        routing_updated.connect(self._handler)
        ChannelRoute.objects.create(
            name='Signal Routing Update', route_type='direct', is_active=True)
        self.assertTrue(self.signal_received)
        routing_updated.disconnect(self._handler)

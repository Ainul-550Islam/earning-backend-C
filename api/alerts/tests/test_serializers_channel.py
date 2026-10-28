"""Tests for Channel Serializers"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from api.alerts.models.channel import AlertChannel, ChannelRoute, ChannelRateLimit, AlertRecipient
from api.alerts.serializers.channel import (
    AlertChannelSerializer, ChannelRouteSerializer,
    ChannelRateLimitSerializer, AlertRecipientSerializer,
    AlertChannelListSerializer, ChannelRouteListSerializer,
    AlertChannelTestSerializer, ChannelRouteTestSerializer,
    ChannelRateLimitTestSerializer, AlertRecipientAvailabilityUpdateSerializer,
    AlertRecipientUsageStatsSerializer)

User = get_user_model()


class AlertChannelSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.channel = AlertChannel.objects.create(
            name='Slack Channel', channel_type='slack', is_enabled=True,
            config={'webhook_url': 'https://hooks.slack.com/test'},
            created_by=self.user
        )

    def test_serializer_read(self):
        data = AlertChannelSerializer(self.channel).data
        for field in ['id', 'name', 'channel_type', 'is_enabled', 'status', 'health_status']:
            self.assertIn(field, data)

    def test_serializer_valid_creation(self):
        valid_data = {
            'name': 'Email Channel', 'channel_type': 'email',
            'is_enabled': True, 'config': {'smtp_host': 'smtp.example.com'},
        }
        s = AlertChannelSerializer(data=valid_data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_list_serializer(self):
        data = AlertChannelListSerializer(self.channel).data
        for field in ['id', 'name', 'channel_type', 'is_enabled']:
            self.assertIn(field, data)

    def test_test_serializer_valid(self):
        s = AlertChannelTestSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)


class ChannelRouteSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.channel = AlertChannel.objects.create(
            name='Route Dest', channel_type='email', is_enabled=True,
            config={'to': 'ops@example.com'}, created_by=self.user
        )
        self.route = ChannelRoute.objects.create(
            name='Critical Route', route_type='rule_based', is_active=True
        )
        self.route.destination_channels.add(self.channel)

    def test_serializer_read(self):
        data = ChannelRouteSerializer(self.route).data
        for field in ['id', 'name', 'is_active', 'route_type']:
            self.assertIn(field, data)

    def test_list_serializer(self):
        data = ChannelRouteListSerializer(self.route).data
        for field in ['id', 'name', 'is_active']:
            self.assertIn(field, data)

    def test_test_routing_serializer_valid(self):
        from api.alerts.models.core import AlertRule, AlertLog
        user = User.objects.create_user('u2', 'u2@e.com', 'pass')
        rule = AlertRule.objects.create(
            name='R', alert_type='server_error', severity='high',
            threshold_value=80.0, created_by=user
        )
        log = AlertLog.objects.create(rule=rule, trigger_value=85.0, threshold_value=80.0, message='test')
        s = ChannelRouteTestSerializer(data={'rule_id': rule.id, 'trigger_value': 85.0, 'message': 'test'})
        self.assertTrue(s.is_valid(), s.errors)


class ChannelRateLimitSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.channel = AlertChannel.objects.create(
            name='Rate Test Channel', channel_type='email', is_enabled=True,
            config={}, created_by=self.user
        )
        self.rate_limit = ChannelRateLimit.objects.filter(channel=self.channel).first()
        if not self.rate_limit:
            self.rate_limit = ChannelRateLimit.objects.create(
                channel=self.channel, limit_type='sliding',
                window_seconds=60, max_requests=100
            )

    def test_serializer_read(self):
        data = ChannelRateLimitSerializer(self.rate_limit).data
        for field in ['id', 'channel', 'limit_type', 'max_requests']:
            self.assertIn(field, data)

    def test_test_serializer_valid(self):
        s = ChannelRateLimitTestSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)


class AlertRecipientSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.recipient = AlertRecipient.objects.create(
            name='Test Recipient', recipient_type='email',
            email_address='test@example.com', priority='medium', is_active=True
        )

    def test_serializer_read(self):
        data = AlertRecipientSerializer(self.recipient).data
        for field in ['id', 'name', 'recipient_type', 'is_active', 'priority']:
            self.assertIn(field, data)

    def test_availability_update_serializer_valid(self):
        from datetime import time
        s = AlertRecipientAvailabilityUpdateSerializer(data={
            'is_active': True, 'timezone': 'UTC',
            'available_days': [0, 1, 2, 3, 4]
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_usage_stats_serializer_valid(self):
        s = AlertRecipientUsageStatsSerializer(data={'days': 30})
        self.assertTrue(s.is_valid(), s.errors)


# -- config secrets are never exposed -------------------------------------------------
class AlertChannelConfigRedactionTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='cfg_user', email='cfg@test.com', password='x')
        self.channel = AlertChannel.objects.create(
            name='Secret channel', channel_type='webhook', created_by=self.user,
            config={'webhook_url': 'https://hooks.example.com/services/T000/B000/XXXX',
                    'api_key': 'super-secret-key', 'smtp_host': 'smtp.example.com',
                    'nested': {'password': 'hunter2', 'region': 'eu'}})

    def test_output_masks_credentials_but_keeps_plain_settings(self):
        from api.alerts.serializers.channel import AlertChannelSerializer
        data = AlertChannelSerializer(self.channel).data
        blob = str(dict(data))
        for secret in ('XXXX', 'super-secret-key', 'hunter2'):
            self.assertNotIn(secret, blob)
        self.assertEqual(data['config']['api_key'], '********')
        self.assertEqual(data['config']['smtp_host'], 'smtp.example.com')
        self.assertEqual(data['config']['nested']['region'], 'eu')

    def test_stored_secrets_are_untouched_by_serialization(self):
        from api.alerts.serializers.channel import AlertChannelSerializer
        AlertChannelSerializer(self.channel).data
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.config['api_key'], 'super-secret-key')

    def test_round_trip_with_masked_placeholders_keeps_stored_secrets(self):
        from api.alerts.serializers.channel import AlertChannelSerializer
        masked = dict(AlertChannelSerializer(self.channel).data['config'])
        masked['smtp_host'] = 'smtp2.example.com'
        serializer = AlertChannelSerializer(self.channel, data={'config': masked}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.config['api_key'], 'super-secret-key')
        self.assertEqual(self.channel.config['nested']['password'], 'hunter2')
        self.assertEqual(self.channel.config['smtp_host'], 'smtp2.example.com')

    def test_new_secret_value_replaces_the_old_one(self):
        from api.alerts.serializers.channel import AlertChannelSerializer
        serializer = AlertChannelSerializer(
            self.channel, data={'config': {'api_key': 'rotated-key'}}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.config['api_key'], 'rotated-key')

    def test_placeholder_without_stored_value_is_rejected(self):
        from api.alerts.serializers.channel import AlertChannelSerializer
        serializer = AlertChannelSerializer(
            self.channel, data={'config': {'brand_new_token': '********'}}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('config', serializer.errors)

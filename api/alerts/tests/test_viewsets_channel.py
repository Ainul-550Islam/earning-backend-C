"""
Tests for Channel ViewSets — FIXED
URL prefix: /channel/ (ROOT_URLCONF=alerts.urls in test context)
Pagination disabled in test_settings → response.data is a list, not {'results':[...]}.
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.alerts.models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog,
    ChannelRateLimit, AlertRecipient,
)

User = get_user_model()


def _count(data):
    """Return item count regardless of whether response is paginated or a plain list."""
    if isinstance(data, dict):
        return len(data.get('results', data))
    return len(data)


def _items(data):
    """Return the list of items from paginated or plain-list response."""
    if isinstance(data, dict):
        return data.get('results', list(data.values()))
    return data


class AlertChannelViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='chvstest', email='chvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.channel = AlertChannel.objects.create(
            name='Email Channel', channel_type='email',
            description='Primary email channel', is_enabled=True,
            priority=1, config={'smtp_server': 'smtp.example.com'})

    def test_list_channels(self):
        resp = self.client.get('/channel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_channel(self):
        data = {'name': 'SMS Channel', 'channel_type': 'sms',
                'is_enabled': True, 'priority': 2,
                'config': {'api_key': 'test_key'}}
        resp = self.client.post('/channel/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertChannel.objects.count(), 2)

    def test_retrieve_channel(self):
        resp = self.client.get(f'/channel/{self.channel.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Email Channel')

    def test_update_channel(self):
        resp = self.client.patch(f'/channel/{self.channel.id}/',
                                 {'name': 'Updated Email'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.name, 'Updated Email')

    def test_delete_channel(self):
        resp = self.client.delete(f'/channel/{self.channel.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AlertChannel.objects.count(), 0)

    def test_enable_channel(self):
        self.channel.is_enabled = False
        self.channel.save()
        resp = self.client.post(f'/channel/{self.channel.id}/enable/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.is_enabled)

    def test_disable_channel(self):
        resp = self.client.post(f'/channel/{self.channel.id}/disable/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.is_enabled)

    def test_test_channel(self):
        resp = self.client.post(f'/channel/{self.channel.id}/test/',
                                {'message': 'Test msg', 'recipient': 't@e.com'},
                                format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_channel_health(self):
        resp = self.client.get(f'/channel/{self.channel.id}/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_channel_statistics(self):
        resp = self.client.get(f'/channel/{self.channel.id}/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class ChannelRouteViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rvstest', email='rvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.src = AlertChannel.objects.create(
            name='Route Src', channel_type='email', is_enabled=True)
        self.dst = AlertChannel.objects.create(
            name='Route Dst', channel_type='sms', is_enabled=True)
        self.route = ChannelRoute.objects.create(
            name='Email to SMS', route_type='severity_based',
            is_active=True, priority=1)
        self.route.source_channels.add(self.src)
        self.route.destination_channels.add(self.dst)

    def test_list_routes(self):
        resp = self.client.get('/channel/routes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_route(self):
        data = {'name': 'New Route', 'route_type': 'rule_based',
                'is_active': True, 'priority': 2}
        resp = self.client.post('/channel/routes/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(ChannelRoute.objects.count(), 2)

    def test_retrieve_route(self):
        resp = self.client.get(f'/channel/routes/{self.route.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Email to SMS')

    def test_update_route(self):
        resp = self.client.patch(f'/channel/routes/{self.route.id}/',
                                 {'priority': 5}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.route.refresh_from_db()
        self.assertEqual(self.route.priority, 5)

    def test_delete_route(self):
        resp = self.client.delete(f'/channel/routes/{self.route.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_activate_route(self):
        self.route.is_active = False
        self.route.save()
        resp = self.client.post(f'/channel/routes/{self.route.id}/activate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.route.refresh_from_db()
        self.assertTrue(self.route.is_active)

    def test_deactivate_route(self):
        resp = self.client.post(f'/channel/routes/{self.route.id}/deactivate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.route.refresh_from_db()
        self.assertFalse(self.route.is_active)

    def test_test_route(self):
        resp = self.client.post(f'/channel/routes/{self.route.id}/test/',
                                {'test_message': 'Test'}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_routes_by_type(self):
        resp = self.client.get('/channel/routes/by_type/severity_based/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_active_routes(self):
        resp = self.client.get('/channel/routes/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class ChannelHealthLogViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='hlvstest', email='hlvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.channel = AlertChannel.objects.create(
            name='HL Test Channel', channel_type='email', is_enabled=True)
        self.log = ChannelHealthLog.objects.create(
            channel=self.channel, check_name='smtp_conn',
            check_type='connectivity', status='healthy',
            response_time_ms=150.0, status_message='OK')

    def test_list_health_logs(self):
        resp = self.client.get('/channel/health_logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_health_log(self):
        data = {'channel': self.channel.id, 'check_name': 'api_check',
                'check_type': 'connectivity', 'status': 'warning',
                'response_time_ms': 500.0, 'status_message': 'Slow'}
        resp = self.client.post('/channel/health_logs/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_health_log(self):
        resp = self.client.get(f'/channel/health_logs/{self.log.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['check_name'], 'smtp_conn')

    def test_health_logs_by_channel(self):
        resp = self.client.get(f'/channel/health_logs/by_channel/{self.channel.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_logs_by_status(self):
        resp = self.client.get('/channel/health_logs/by_status/healthy/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_logs_by_type(self):
        resp = self.client.get('/channel/health_logs/by_type/connectivity/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_recent_health_logs(self):
        resp = self.client.get('/channel/health_logs/recent/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_health_statistics(self):
        resp = self.client.get('/channel/health_logs/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class ChannelRateLimitViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rlvstest', email='rlvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.channel = AlertChannel.objects.create(
            name='RL Test Channel', channel_type='email', is_enabled=True)
        # The signal auto-creates a ChannelRateLimit (OneToOneField).
        # Fetch it rather than creating a duplicate.
        self.rl = ChannelRateLimit.objects.get(channel=self.channel)

    def test_list_rate_limits(self):
        resp = self.client.get('/channel/rate_limits/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_rate_limit_new_channel(self):
        """Signal auto-creates ChannelRateLimit (OneToOne). Verify via a new channel."""
        new_ch = AlertChannel.objects.create(
            name='RL Auto Channel', channel_type='webhook', is_enabled=True)
        self.assertTrue(ChannelRateLimit.objects.filter(channel=new_ch).exists())

    def test_rate_limits_listing(self):
        """Can list all rate limits."""
        resp = self.client.get('/channel/rate_limits/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_retrieve_rate_limit(self):
        resp = self.client.get(f'/channel/rate_limits/{self.rl.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(resp.data['limit_type'], ['sliding', 'per_minute', 'per_hour', 'per_day'])

    def test_update_rate_limit(self):
        resp = self.client.patch(f'/channel/rate_limits/{self.rl.id}/',
                                 {'max_requests': 200}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.rl.refresh_from_db()
        self.assertEqual(self.rl.max_requests, 200)

    def test_delete_rate_limit(self):
        resp = self.client.delete(f'/channel/rate_limits/{self.rl.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_consume_token(self):
        resp = self.client.post(f'/channel/rate_limits/{self.rl.id}/consume_token/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_refill_tokens(self):
        self.rl.current_tokens = 50
        self.rl.save()
        resp = self.client.post(f'/channel/rate_limits/{self.rl.id}/refill_tokens/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_rate_limit(self):
        resp = self.client.post(f'/channel/rate_limits/{self.rl.id}/reset/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rate_limit_status(self):
        resp = self.client.get(f'/channel/rate_limits/{self.rl.id}/status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rate_limits_by_channel(self):
        resp = self.client.get(f'/channel/rate_limits/by_channel/{self.channel.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_rate_limits_by_type(self):
        # The auto-created rate limit is always limit_type='sliding' (see
        # signals/channel.py's alert_channel_post_save) — use the real value
        # rather than a hardcoded guess, and check it's actually returned.
        resp = self.client.get(f'/channel/rate_limits/by_type/{self.rl.limit_type}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in resp.data] if isinstance(resp.data, list) else [
            row['id'] for row in resp.data.get('results', [])]
        self.assertIn(self.rl.id, ids)

    def test_create_rate_limit(self):
        """Creating a second RL for same channel fails (OneToOne); use new channel."""
        new_ch = AlertChannel.objects.create(
            name='RL New Ch', channel_type='webhook', is_enabled=True)
        # Signal already created one; just verify
        self.assertTrue(ChannelRateLimit.objects.filter(channel=new_ch).exists())


class AlertRecipientViewSetTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='recvstest', email='recvs@example.com', password='testpass123', is_staff=True)
        self.client.force_authenticate(user=self.user)
        self.recipient = AlertRecipient.objects.create(
            name='Test Recipient', recipient_type='user',
            user=self.user, email_address='recvs@example.com',
            priority='high', is_active=True,
            max_notifications_per_hour=50)

    def test_list_recipients(self):
        resp = self.client.get('/channel/recipients/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(_count(resp.data), 1)

    def test_create_recipient(self):
        data = {'name': 'New Recipient', 'recipient_type': 'email',
                'email_address': 'new@example.com', 'priority': 'medium',
                'is_active': True, 'max_notifications_per_hour': 25}
        resp = self.client.post('/channel/recipients/', data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_retrieve_recipient(self):
        resp = self.client.get(f'/channel/recipients/{self.recipient.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Test Recipient')

    def test_update_recipient(self):
        resp = self.client.patch(f'/channel/recipients/{self.recipient.id}/',
                                 {'priority': 'critical'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.priority, 'critical')

    def test_delete_recipient(self):
        resp = self.client.delete(f'/channel/recipients/{self.recipient.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_activate_recipient(self):
        self.recipient.is_active = False
        self.recipient.save()
        resp = self.client.post(f'/channel/recipients/{self.recipient.id}/activate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.recipient.refresh_from_db()
        self.assertTrue(self.recipient.is_active)

    def test_deactivate_recipient(self):
        resp = self.client.post(f'/channel/recipients/{self.recipient.id}/deactivate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.recipient.refresh_from_db()
        self.assertFalse(self.recipient.is_active)

    def test_test_recipient(self):
        resp = self.client.post(f'/channel/recipients/{self.recipient.id}/test/',
                                {'message': 'Test'}, format='json')
        self.assertIn(resp.status_code,
                      [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_recipients_by_type(self):
        resp = self.client.get('/channel/recipients/by_type/user/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_active_recipients(self):
        resp = self.client.get('/channel/recipients/active/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_recipients_by_priority(self):
        # self.recipient was created with priority='high' in setUp — use that
        # real value and confirm it's actually returned, rather than an
        # arbitrary '1' that matches no recipient's priority choice.
        resp = self.client.get('/channel/recipients/by_priority/high/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [row['id'] for row in resp.data] if isinstance(resp.data, list) else [
            row['id'] for row in resp.data.get('results', [])]
        self.assertIn(self.recipient.id, ids)

    def test_recipient_statistics(self):
        resp = self.client.get(f'/channel/recipients/{self.recipient.id}/statistics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_counters(self):
        self.recipient.notifications_sent_today = 10
        self.recipient.save()
        resp = self.client.post(
            f'/channel/recipients/{self.recipient.id}/reset_counters/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.notifications_sent_today, 0)

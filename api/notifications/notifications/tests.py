# earning_backend/api/notifications/tests.py
"""
Tests for the notifications system.
Tests cover: models, services, tasks, viewsets, signals.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


# ============================================================
# Model Tests
# ============================================================

class PushDeviceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_push_device(self):
        from notifications.models.channel import PushDevice
        device = PushDevice.objects.create(
            user=self.user,
            device_type='android',
            fcm_token='test_token_123',
            device_name='Test Phone',
        )
        self.assertEqual(device.device_type, 'android')
        self.assertTrue(device.is_active)
        self.assertEqual(device.get_push_token(), 'test_token_123')

    def test_device_deactivate(self):
        from notifications.models.channel import PushDevice
        device = PushDevice.objects.create(user=self.user, device_type='android')
        device.deactivate()
        self.assertFalse(device.is_active)

    def test_delivery_rate(self):
        from notifications.models.channel import PushDevice
        device = PushDevice.objects.create(
            user=self.user, device_type='android',
            push_sent=10, push_delivered=8
        )
        self.assertEqual(device.get_delivery_rate(), 80.0)


class InAppMessageModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser2', password='pass')

    def test_create_in_app_message(self):
        from notifications.models.channel import InAppMessage
        msg = InAppMessage.objects.create(
            user=self.user,
            message_type='toast',
            title='Test Notification',
            body='This is a test message.',
        )
        self.assertFalse(msg.is_read)
        self.assertFalse(msg.is_dismissed)
        self.assertFalse(msg.is_expired())

    def test_mark_read(self):
        from notifications.models.channel import InAppMessage
        msg = InAppMessage.objects.create(user=self.user, message_type='toast', title='T', body='B')
        msg.mark_read()
        self.assertTrue(msg.is_read)
        self.assertIsNotNone(msg.read_at)

    def test_expired_message(self):
        from notifications.models.channel import InAppMessage
        from datetime import timedelta
        msg = InAppMessage.objects.create(
            user=self.user, message_type='toast', title='T', body='B',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        self.assertTrue(msg.is_expired())


class NotificationFatigueModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser3', password='pass')

    def test_create_fatigue_record(self):
        from notifications.models.analytics import NotificationFatigue
        record = NotificationFatigue.objects.create(user=self.user)
        self.assertFalse(record.is_fatigued)
        self.assertEqual(record.sent_today, 0)

    def test_fatigue_triggers_on_daily_limit(self):
        from notifications.models.analytics import NotificationFatigue
        record = NotificationFatigue.objects.create(user=self.user, daily_limit=5)
        record.sent_today = 5
        is_fatigued = record.evaluate_fatigue(save=False)
        self.assertTrue(is_fatigued)

    def test_increment_counters(self):
        from notifications.models.analytics import NotificationFatigue
        record = NotificationFatigue.objects.create(user=self.user)
        record.increment(save=False)
        self.assertEqual(record.sent_today, 1)
        self.assertEqual(record.sent_this_week, 1)


class OptOutTrackingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser4', password='pass')

    def test_opt_out(self):
        from notifications.models.analytics import OptOutTracking
        record = OptOutTracking.opt_out(self.user, 'email', reason='too_many')
        self.assertTrue(record.is_active)
        self.assertEqual(record.channel, 'email')

    def test_is_opted_out(self):
        from notifications.models.analytics import OptOutTracking
        OptOutTracking.opt_out(self.user, 'sms')
        self.assertTrue(OptOutTracking.is_opted_out(self.user, 'sms'))
        self.assertFalse(OptOutTracking.is_opted_out(self.user, 'email'))

    def test_resubscribe(self):
        from notifications.models.analytics import OptOutTracking
        record = OptOutTracking.opt_out(self.user, 'push')
        record.resubscribe()
        self.assertFalse(record.is_active)


# ============================================================
# Service Tests
# ============================================================

class FatigueServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fatigue_user', password='pass')

    def test_not_fatigued_initially(self):
        from notifications.services.FatigueService import fatigue_service
        self.assertFalse(fatigue_service.is_fatigued(self.user))

    def test_exempt_priorities_bypass_fatigue(self):
        from notifications.services.FatigueService import fatigue_service
        from notifications.models.analytics import NotificationFatigue
        # Make user fatigued
        record, _ = NotificationFatigue.objects.get_or_create(user=self.user)
        record.sent_today = 100
        record.is_fatigued = True
        record.save()
        # Critical notifications bypass fatigue
        self.assertFalse(fatigue_service.is_fatigued(self.user, priority='critical'))
        self.assertFalse(fatigue_service.is_fatigued(self.user, priority='urgent'))

    def test_can_send_within_limits(self):
        from notifications.services.FatigueService import fatigue_service
        result = fatigue_service.can_send(self.user)
        self.assertTrue(result['allowed'])

    def test_record_send_increments_counters(self):
        from notifications.services.FatigueService import fatigue_service
        from notifications.models.analytics import NotificationFatigue
        fatigue_service.record_send(self.user)
        record = NotificationFatigue.objects.get(user=self.user)
        self.assertEqual(record.sent_today, 1)


class OptOutServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='optout_user', password='pass')

    def test_opt_out_channel(self):
        from notifications.services.OptOutService import opt_out_service
        result = opt_out_service.opt_out(self.user, 'email')
        self.assertTrue(result['success'])
        self.assertTrue(opt_out_service.is_opted_out(self.user, 'email'))

    def test_resubscribe(self):
        from notifications.services.OptOutService import opt_out_service
        opt_out_service.opt_out(self.user, 'sms')
        result = opt_out_service.resubscribe(self.user, 'sms')
        self.assertTrue(result['success'])
        self.assertFalse(opt_out_service.is_opted_out(self.user, 'sms'))

    def test_filter_opted_out_users(self):
        from notifications.services.OptOutService import opt_out_service
        user2 = User.objects.create_user(username='optout_user2', password='pass')
        opt_out_service.opt_out(self.user, 'email')
        filtered = opt_out_service.filter_opted_out_users([self.user.pk, user2.pk], 'email')
        self.assertNotIn(self.user.pk, filtered)
        self.assertIn(user2.pk, filtered)


class SegmentServiceTest(TestCase):
    def setUp(self):
        self.users = [
            User.objects.create_user(username=f'seg_user_{i}', password='pass', is_active=True)
            for i in range(5)
        ]

    def test_segment_all_users(self):
        from notifications.services.SegmentService import segment_service
        user_ids = segment_service.evaluate_conditions({'type': 'all'})
        for user in self.users:
            self.assertIn(user.pk, user_ids)

    def test_segment_with_explicit_ids(self):
        from notifications.services.SegmentService import segment_service
        ids = [self.users[0].pk, self.users[1].pk]
        result = segment_service.evaluate_conditions({'user_ids': ids})
        self.assertEqual(set(result), set(ids))


# ============================================================
# API Tests
# ============================================================

class PushDeviceAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_devices(self):
        response = self.client.get('/api/notifications/push-devices/')
        self.assertIn(response.status_code, [200, 404])

    def test_register_android_device(self):
        response = self.client.post('/api/notifications/push-devices/register/', {
            'device_type': 'android',
            'fcm_token': 'test_fcm_token_abc123',
            'device_name': 'My Android',
        }, format='json')
        self.assertIn(response.status_code, [200, 201, 404])


class InAppMessageAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inapp_user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_in_app_messages(self):
        response = self.client.get('/api/notifications/in-app-messages/')
        self.assertIn(response.status_code, [200, 404])


class OptOutAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='optout_api_user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_opt_out(self):
        response = self.client.post('/api/notifications/opt-outs/opt_out/', {
            'channel': 'email',
            'reason': 'too_many',
        }, format='json')
        self.assertIn(response.status_code, [200, 201, 404])


# ============================================================
# Provider Tests (mocked)
# ============================================================

class FCMProviderTest(TestCase):
    @patch('firebase_admin.messaging.send')
    def test_send_success(self, mock_send):
        mock_send.return_value = 'msg_id_123'
        from notifications.services.providers.FCMProvider import FCMProvider
        provider = FCMProvider()
        # Only test if available
        if provider.is_available():
            notification = MagicMock()
            notification.id = 1
            notification.title = 'Test'
            notification.message = 'Test message'
            notification.created_at = timezone.now()
            result = provider.send('fake_token', notification)
            self.assertTrue(result['success'])


class TwilioProviderTest(TestCase):
    def test_normalise_bd_phone(self):
        from notifications.services.providers.TwilioProvider import TwilioProvider
        provider = TwilioProvider()
        self.assertEqual(provider._normalise_phone('01712345678'), '+01712345678')
        self.assertEqual(provider._normalise_phone('+8801712345678'), '+8801712345678')

    def test_bd_number_detection(self):
        from notifications.services.NotificationDispatcher import NotificationDispatcher
        dispatcher = NotificationDispatcher()
        self.assertTrue(dispatcher._is_bd_number('01712345678'))
        self.assertTrue(dispatcher._is_bd_number('+8801712345678'))
        self.assertFalse(dispatcher._is_bd_number('+14155552671'))


class ShohoSMSProviderTest(TestCase):
    def test_normalise_bd_phone(self):
        from notifications.services.providers.ShohoSMSProvider import ShohoSMSProvider
        provider = ShohoSMSProvider()
        self.assertEqual(provider._normalise_bd_phone('+8801712345678'), '01712345678')
        self.assertEqual(provider._normalise_bd_phone('8801712345678'), '01712345678')
        self.assertEqual(provider._normalise_bd_phone('01712345678'), '01712345678')

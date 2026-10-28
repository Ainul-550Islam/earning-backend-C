# api/djoyalty/tests/test_notification_extended.py
"""
Extended NotificationViewSet tests -- admin_trigger (all 8 events),
admin_test, admin_send, admin_queue, my_notifications, mark_read, preferences。
Previously 0 of these 8 actions were tested。
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _setup():
    from djoyalty.models.core import Tenant, Customer
    from djoyalty.models.notifications import NotificationCenter, NotificationPreference
    t = Tenant.objects.create(name=f'NotifCo-{Tenant.objects.count()}',
                               slug=f'notif-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'nf_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u, code=f'N{Customer.objects.count():04d}', is_active=True)
    return t, c

def _admin():
    u = User.objects.create_user(username=f'na_{User.objects.count()}', password='pw', is_staff=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return cli

def _cli(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c


class NotificationMyInboxTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.cli = _cli(self.customer)

    def test_my_notifications_empty(self):
        resp = self.cli.get(
            f'/api/loyalty/notifications/my/?customer_id={self.customer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('unread_count', resp.data)
        self.assertEqual(resp.data['unread_count'], 0)

    def test_my_notifications_with_items(self):
        from djoyalty.models.notifications import NotificationCenter
        NotificationCenter.objects.create(
            customer=self.customer, tenant=self.tenant,
            notification_type='points_earned', title='You earned 50 points',
            body='Keep shopping!', is_read=False, is_sent=True,
        )
        resp = self.cli.get(
            f'/api/loyalty/notifications/my/?customer_id={self.customer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['unread_count'], 1)

    def test_mark_read(self):
        from djoyalty.models.notifications import NotificationCenter
        n = NotificationCenter.objects.create(
            customer=self.customer, tenant=self.tenant,
            notification_type='test', title='Test', body='body', is_read=False,
        )
        resp = self.cli.post(
            '/api/loyalty/notifications/mark-read/',
            {'notification_id': n.pk, 'customer_id': self.customer.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 1)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_all_read(self):
        from djoyalty.models.notifications import NotificationCenter
        for i in range(3):
            NotificationCenter.objects.create(
                customer=self.customer, tenant=self.tenant,
                notification_type='test', title=f'Test {i}', body='body', is_read=False,
            )
        resp = self.cli.post(
            '/api/loyalty/notifications/mark-all-read/',
            {'customer_id': self.customer.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['marked_read'], 3)

    def test_preferences_get(self):
        resp = self.cli.get(
            f'/api/loyalty/notifications/preferences/?customer_id={self.customer.pk}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class NotificationAdminTriggerTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.admin = _admin()

    TRIGGER_EVENTS = [
        ('tier_upgrade',    {'from_tier': 'Silver', 'to_tier': 'Gold'}),
        ('tier_downgrade',  {'from_tier': 'Gold', 'to_tier': 'Silver'}),
        ('streak_broken',   {'streak_days': 7}),
        ('expiry_warning',  {'points': 200, 'days_left': 7}),
        ('points_earned',   {'points': 50}),
        ('cashout_approved',{'amount': 500, 'method': 'bkash'}),
        ('cashout_rejected',{'reason': 'Insufficient verification'}),
        ('birthday',        {}),
    ]

    @patch('djoyalty.viewsets.advanced.NotificationViewSet.NotificationTriggerService')
    def test_all_trigger_events(self, mock_svc_cls):
        """All 8 NotificationTriggerService methods can be triggered via API."""
        mock_svc = MagicMock()
        mock_svc_cls.trigger_tier_upgrade     = MagicMock()
        mock_svc_cls.trigger_tier_downgrade   = MagicMock()
        mock_svc_cls.trigger_streak_broken    = MagicMock()
        mock_svc_cls.trigger_expiry_warning   = MagicMock()
        mock_svc_cls.trigger_points_earned    = MagicMock()
        mock_svc_cls.trigger_cashout_approved = MagicMock()
        mock_svc_cls.trigger_cashout_rejected = MagicMock()
        mock_svc_cls.trigger_birthday         = MagicMock()

        for event, params in self.TRIGGER_EVENTS:
            resp = self.admin.post('/api/loyalty/notifications/admin/trigger/', {
                'customer_id': self.customer.pk,
                'event':       event,
                'params':      params,
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK,
                             f"Event '{event}' failed: {resp.data}")
            self.assertEqual(resp.data['event'], event)
            self.assertEqual(resp.data['status'], 'triggered')

    def test_invalid_event_returns_400_with_valid_list(self):
        resp = self.admin.post('/api/loyalty/notifications/admin/trigger/', {
            'customer_id': self.customer.pk,
            'event':       'nonexistent_event',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('valid', resp.data)
        self.assertIsInstance(resp.data['valid'], list)
        self.assertIn('tier_upgrade', resp.data['valid'])

    def test_trigger_requires_customer_and_event(self):
        resp = self.admin.post('/api/loyalty/notifications/admin/trigger/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trigger_requires_admin(self):
        cli = _cli(self.customer)
        resp = cli.post('/api/loyalty/notifications/admin/trigger/', {
            'customer_id': self.customer.pk, 'event': 'birthday',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class NotificationAdminSendTest(TestCase):
    def setUp(self):
        self.tenant, self.customer = _setup()
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.NotificationViewSet.NotificationService.send')
    def test_admin_send(self, mock_send):
        resp = self.admin.post('/api/loyalty/notifications/admin/send/', {
            'customer_id':       self.customer.pk,
            'notification_type': 'promo',
            'title':             '50% off sale!',
            'body':              'Grab it before it ends.',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'sent')
        mock_send.assert_called_once()

    @patch('djoyalty.viewsets.advanced.NotificationViewSet.NotificationService.send')
    def test_admin_test_channel(self, mock_send):
        resp = self.admin.post('/api/loyalty/notifications/admin/test/', {
            'customer_id': self.customer.pk,
            'channel':     'push',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'test_sent')

    def test_admin_queue(self):
        from djoyalty.models.notifications import NotificationCenter
        NotificationCenter.objects.create(
            customer=self.customer, tenant=self.tenant,
            notification_type='test', title='Queued', body='body', is_sent=False,
        )
        resp = self.admin.get('/api/loyalty/notifications/admin/queue/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('count', resp.data)
        self.assertIn('queue', resp.data)
        self.assertGreaterEqual(resp.data['count'], 1)

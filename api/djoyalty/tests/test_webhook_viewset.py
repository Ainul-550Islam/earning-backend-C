# api/djoyalty/tests/test_webhook_viewset.py
"""
WebhookViewSet tests -- create_subscription, list, destroy, test_webhook,
delivery_log, retry_delivery。 All 6 actions: previously 0 tested。
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _admin():
    u = User.objects.create_user(username=f'wh_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _customer_cli():
    from djoyalty.models.core import Tenant, Customer
    t = Tenant.objects.create(name=f'WHCo-{Tenant.objects.count()}',
                               slug=f'wh-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'whc_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u,
                                code=f'WH{Customer.objects.count():04d}', is_active=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return cli

def _subscription():
    from djoyalty.models.catalog import WebhookSubscription
    return WebhookSubscription.objects.create(
        url='https://partner.example.com/webhook',
        event_types=['cashout.completed', 'tier.changed'],
        is_active=True,
    )


class WebhookSubscriptionCRUDTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    def test_list_subscriptions_empty(self):
        resp = self.admin.get('/api/loyalty/webhooks/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)

    def test_list_subscriptions_with_data(self):
        _subscription()
        resp = self.admin.get('/api/loyalty/webhooks/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)
        s = resp.data['results'][0]
        for field in ('id', 'url', 'event_types', 'is_active'):
            self.assertIn(field, s)

    def test_create_subscription_valid(self):
        resp = self.admin.post('/api/loyalty/webhooks/create/', {
            'url':         'https://partner.example.com/hook',
            'event_types': ['cashout.completed', 'points.earned'],
            'secret':      'mysecret123',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['url'], 'https://partner.example.com/hook')
        self.assertIn('cashout.completed', resp.data['event_types'])

    def test_create_requires_https(self):
        resp = self.admin.post('/api/loyalty/webhooks/create/', {
            'url': 'http://partner.example.com/hook',
            'event_types': ['cashout.completed'],
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('HTTPS', resp.data.get('error', ''))

    def test_create_requires_url(self):
        resp = self.admin.post('/api/loyalty/webhooks/create/', {
            'event_types': ['cashout.completed'],
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_requires_event_types(self):
        resp = self.admin.post('/api/loyalty/webhooks/create/', {
            'url': 'https://partner.example.com/hook',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_subscription(self):
        sub = _subscription()
        resp = self.admin.delete(f'/api/loyalty/webhooks/{sub.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'deleted')
        from djoyalty.models.catalog import WebhookSubscription
        self.assertFalse(WebhookSubscription.objects.filter(pk=sub.pk).exists())

    def test_requires_admin(self):
        cli = _customer_cli()
        resp = cli.get('/api/loyalty/webhooks/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class WebhookTestDeliveryTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.sub   = _subscription()

    @patch('djoyalty.viewsets.webhooks.WebhookViewSet.LoyaltyWebhookService.send_test')
    def test_test_webhook(self, mock_send):
        resp = self.admin.post(f'/api/loyalty/webhooks/{self.sub.pk}/test/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'test_sent')
        self.assertEqual(resp.data['url'], self.sub.url)
        mock_send.assert_called_once_with(subscription=self.sub)

    @patch('djoyalty.viewsets.webhooks.WebhookViewSet.LoyaltyWebhookService.send_test')
    def test_test_webhook_failure(self, mock_send):
        mock_send.side_effect = Exception('Connection refused')
        resp = self.admin.post(f'/api/loyalty/webhooks/{self.sub.pk}/test/')
        self.assertEqual(resp.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(resp.data['status'], 'test_failed')


class WebhookDeliveryLogTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.sub   = _subscription()

    def test_delivery_log_empty(self):
        resp = self.admin.get('/api/loyalty/webhooks/delivery-log/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)

    def test_delivery_log_with_data(self):
        from djoyalty.models.catalog import WebhookDeliveryLog
        from django.utils import timezone
        WebhookDeliveryLog.objects.create(
            subscription=self.sub, event_type='cashout.completed',
            status='failed', http_status_code=500, attempt_number=1,
            delivered_at=timezone.now(), response_body='Internal Server Error',
        )
        resp = self.admin.get('/api/loyalty/webhooks/delivery-log/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)
        log = resp.data['results'][0]
        for field in ('id', 'webhook_url', 'event_type', 'status', 'http_status', 'attempt'):
            self.assertIn(field, log)

    def test_delivery_log_filter_by_status(self):
        resp = self.admin.get('/api/loyalty/webhooks/delivery-log/?status=failed')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch('djoyalty.viewsets.webhooks.WebhookViewSet.LoyaltyWebhookService.retry')
    def test_retry_failed_delivery(self, mock_retry):
        from djoyalty.models.catalog import WebhookDeliveryLog
        from django.utils import timezone
        log = WebhookDeliveryLog.objects.create(
            subscription=self.sub, event_type='cashout.completed',
            status='failed', http_status_code=500, attempt_number=1,
            delivered_at=timezone.now(),
        )
        resp = self.admin.post(f'/api/loyalty/webhooks/{log.pk}/retry/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'retry_queued')
        mock_retry.assert_called_once()

    def test_retry_successful_delivery_blocked(self):
        from djoyalty.models.catalog import WebhookDeliveryLog
        from django.utils import timezone
        log = WebhookDeliveryLog.objects.create(
            subscription=self.sub, event_type='cashout.completed',
            status='success', http_status_code=200, attempt_number=1,
            delivered_at=timezone.now(),
        )
        resp = self.admin.post(f'/api/loyalty/webhooks/{log.pk}/retry/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

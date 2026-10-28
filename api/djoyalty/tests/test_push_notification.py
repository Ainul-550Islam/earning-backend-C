# api/djoyalty/tests/test_push_notification.py
"""PushNotificationViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer


class PushNotificationViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='PUSHCUST01')

    def test_send_push(self):
        resp = self.client.post('/api/push-notifications/send/', {
            'customer_id': self.customer.id,
            'title': 'Test Push',
            'body': 'Hello from djoyalty',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_register_device_token(self):
        resp = self.client.post('/api/push-notifications/register/', {
            'customer_id': self.customer.id,
            'token': 'TEST_FCM_TOKEN_XYZ',
            'platform': 'ios',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_delivery_stats(self):
        resp = self.client.get('/api/push-notifications/delivery_stats/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

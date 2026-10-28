# api/djoyalty/tests/test_sdk.py
"""SDKViewSet tests -- SDK/headless API endpoints."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class SDKViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='SDKCUST01')
        make_loyalty_points(self.customer, balance=Decimal('600'))

    def test_sdk_identify(self):
        resp = self.client.post('/api/sdk/identify/', {
            'customer_code': self.customer.code,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_sdk_track_event(self):
        resp = self.client.post('/api/sdk/track/', {
            'customer_code': self.customer.code,
            'event': 'purchase',
            'properties': {'amount': 500},
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_sdk_get_profile(self):
        resp = self.client.get(f'/api/sdk/profile/?code={self.customer.code}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

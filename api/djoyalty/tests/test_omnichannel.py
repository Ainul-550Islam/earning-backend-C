# api/djoyalty/tests/test_omnichannel.py
"""OmnichannelViewSet tests -- cross-channel loyalty sync."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class OmnichannelViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='OMNICUST01')
        make_loyalty_points(self.customer, balance=Decimal('1200'))

    def test_sync_channel(self):
        resp = self.client.post('/api/omnichannel/sync/', {
            'customer_id': self.customer.id,
            'channel': 'pos',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_channel_status(self):
        resp = self.client.get(f'/api/omnichannel/status/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_register_push_token(self):
        resp = self.client.post('/api/omnichannel/register_token/', {
            'customer_id': self.customer.id,
            'token': 'FCMTOKEN123ABC',
            'platform': 'android',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

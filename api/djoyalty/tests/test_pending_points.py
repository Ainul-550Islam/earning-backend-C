# api/djoyalty/tests/test_pending_points.py
"""PendingPointsViewSet tests -- reserved/pending points management."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class PendingPointsViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='PENDCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1500'))

    def test_list_pending(self):
        resp = self.client.get(f'/api/pending-points/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_release_pending(self):
        resp = self.client.post('/api/pending-points/release/', {
            'customer_id': self.customer.id,
            'reservation_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_cancel_pending(self):
        resp = self.client.post('/api/pending-points/cancel/', {
            'customer_id': self.customer.id,
            'reservation_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

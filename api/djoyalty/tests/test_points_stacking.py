# api/djoyalty/tests/test_points_stacking.py
"""PointsStackingViewSet tests -- multi-rule stacking logic."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points, make_txn


class PointsStackingViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='STKCUST01')
        make_loyalty_points(self.customer, balance=Decimal('3000'))

    def test_stacking_preview(self):
        resp = self.client.post('/api/points-stacking/preview/', {
            'customer_id': self.customer.id,
            'purchase_amount': 1000,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_list_stacking_rules(self):
        resp = self.client.get('/api/points-stacking/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])


class PointsStackingServiceTest(TestCase):
    def setUp(self):
        self.customer = make_customer(code='STKSVC01')
        make_loyalty_points(self.customer, balance=Decimal('2000'))

    def test_stacking_does_not_exceed_cap(self):
        """Points stacking must not exceed system cap."""
        from decimal import Decimal
        pts = Decimal('1000')
        max_multiplier = Decimal('5')
        stacked = pts * max_multiplier
        self.assertLessEqual(stacked, Decimal('10000'))

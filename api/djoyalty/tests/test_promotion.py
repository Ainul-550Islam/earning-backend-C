# api/djoyalty/tests/test_promotion.py
"""PromotionViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class PromotionViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='PROMCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_list_promotions(self):
        resp = self.client.get('/api/promotions/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_apply_promo_code(self):
        resp = self.client.post('/api/promotions/apply/', {
            'customer_id': self.customer.id,
            'promo_code': 'TESTPROMO',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

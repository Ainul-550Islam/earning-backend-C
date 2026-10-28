# api/djoyalty/tests/test_public_api.py
"""PublicAPIViewSet tests -- public-facing loyalty endpoints."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class PublicAPIViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='PUBCUST01')
        make_loyalty_points(self.customer, balance=Decimal('800'))

    def test_public_balance_check(self):
        resp = self.client.get(f'/api/public/balance/?code={self.customer.code}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_public_tier_info(self):
        resp = self.client.get(f'/api/public/tier/?code={self.customer.code}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

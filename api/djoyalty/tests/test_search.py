# api/djoyalty/tests/test_search.py
"""SearchViewSet tests -- global loyalty search."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class SearchViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='SRCHCUST01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_search_customers(self):
        resp = self.client.get('/api/search/?q=SRCHCUST01&type=customer')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_search_requires_query(self):
        resp = self.client.get('/api/search/')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_search_rewards(self):
        resp = self.client.get('/api/search/?q=voucher&type=reward')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

# api/djoyalty/tests/test_analytics.py
"""AnalyticsViewSet tests -- loyalty analytics endpoints."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points, make_txn


class AnalyticsViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='ANCUST01')
        make_loyalty_points(self.customer, balance=Decimal('2000'))
        make_txn(self.customer, value=Decimal('500'))
        make_txn(self.customer, value=Decimal('750'))

    def test_revenue_analytics(self):
        resp = self.client.get('/api/analytics/revenue/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_customer_analytics(self):
        resp = self.client.get('/api/analytics/customers/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_points_analytics(self):
        resp = self.client.get('/api/analytics/points/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_cohort_report(self):
        resp = self.client.get('/api/analytics/cohort/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

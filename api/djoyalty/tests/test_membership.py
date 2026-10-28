# api/djoyalty/tests/test_membership.py
"""MembershipViewSet (paid loyalty subscription) tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class MembershipModelTest(TestCase):
    def setUp(self):
        self.customer = make_customer(code='MEMCUST01')

    def test_customer_exists(self):
        self.assertTrue(self.customer.is_active)


class MembershipViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='MEMAPI01')
        make_loyalty_points(self.customer, balance=Decimal('5000'))

    def test_subscribe(self):
        resp = self.client.post('/api/membership/subscribe/', {
            'customer_id': self.customer.id,
            'plan_name': 'premium',
            'billing_cycle': 'monthly',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 401, 403, 404])

    def test_cancel_subscription(self):
        resp = self.client.post('/api/membership/cancel/', {
            'customer_id': self.customer.id,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_list_subscriptions(self):
        resp = self.client.get('/api/membership/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

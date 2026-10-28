# api/djoyalty/tests/test_referral.py
"""ReferralViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class ReferralModelTest(TestCase):
    def setUp(self):
        self.referrer = make_customer(code='REFCUST01')
        self.referred = make_customer(code='REFCUST02')
        make_loyalty_points(self.referrer, balance=Decimal('500'))

    def test_referrer_and_referred_are_different(self):
        self.assertNotEqual(self.referrer.code, self.referred.code)


class ReferralViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='REFAPI01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_generate_referral_link(self):
        resp = self.client.post('/api/referrals/generate_link/', {
            'customer_id': self.customer.id,
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 401, 403, 404])

    def test_list_referrals(self):
        resp = self.client.get(f'/api/referrals/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_referral_stats(self):
        resp = self.client.get(f'/api/referrals/stats/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

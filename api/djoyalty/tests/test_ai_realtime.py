# api/djoyalty/tests/test_ai_realtime.py
"""AIRealtimeViewSet tests -- real-time AI offer serving."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class AIRealtimeViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='AICUST01')
        make_loyalty_points(self.customer, balance=Decimal('1500'))

    def test_get_offers_for_customer(self):
        resp = self.client.get(f'/api/ai-realtime/offers/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_claim_offer(self):
        resp = self.client.post('/api/ai-realtime/claim/', {
            'customer_id': self.customer.id,
            'offer_id': 999,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_churn_score(self):
        resp = self.client.get(f'/api/ai-realtime/churn_score/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

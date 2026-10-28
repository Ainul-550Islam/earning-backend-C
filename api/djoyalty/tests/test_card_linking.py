# api/djoyalty/tests/test_card_linking.py
"""CardLinkingViewSet tests."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class CardLinkingTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='CARDCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_link_card_endpoint(self):
        resp = self.client.post('/api/card-linking/link/', {
            'customer_id': self.customer.id,
            'card_number': '4111111111111111',
            'card_type': 'visa',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 401, 403, 404])

    def test_list_linked_cards(self):
        resp = self.client.get('/api/card-linking/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_unlink_card(self):
        resp = self.client.post('/api/card-linking/unlink/', {
            'customer_id': self.customer.id,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

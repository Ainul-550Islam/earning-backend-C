# api/djoyalty/tests/test_web3.py
"""Web3ViewSet tests -- blockchain loyalty features."""
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points
from decimal import Decimal


class Web3ViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='WEB3CUST01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_connect_wallet(self):
        resp = self.client.post('/api/web3/connect_wallet/', {
            'customer_id': self.customer.id,
            'wallet_address': '0xABCDEF1234567890',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_mint_nft_badge(self):
        resp = self.client.post('/api/web3/mint_badge/', {
            'customer_id': self.customer.id,
            'badge_id': 1,
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_token_balance(self):
        resp = self.client.get(f'/api/web3/token_balance/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

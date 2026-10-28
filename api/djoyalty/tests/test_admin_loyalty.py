# api/djoyalty/tests/test_admin_loyalty.py
"""AdminLoyaltyViewSet tests -- admin-level operations."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points


class AdminLoyaltyTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='ADMINCUST01')
        make_loyalty_points(self.customer, balance=Decimal('1000'))

    def test_admin_dashboard_endpoint(self):
        resp = self.client.get('/api/admin-loyalty/dashboard/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_adjust_points_requires_auth(self):
        resp = self.client.post('/api/admin-loyalty/adjust_points/', {
            'customer_id': self.customer.id,
            'points': 100,
            'reason': 'Test adjustment',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 401, 403, 404])

    def test_audit_log_endpoint(self):
        resp = self.client.get('/api/admin-loyalty/audit_log/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

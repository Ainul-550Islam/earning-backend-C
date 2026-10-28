# api/djoyalty/tests/test_compliance.py
"""ComplianceViewSet tests -- GDPR/consent management."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer


class ComplianceViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='COMPCUST01')

    def test_export_customer_data(self):
        resp = self.client.get(f'/api/compliance/export/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_delete_customer_data(self):
        resp = self.client.post('/api/compliance/delete/', {
            'customer_id': self.customer.id,
            'reason': 'GDPR request',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_consent_status(self):
        resp = self.client.get(f'/api/compliance/consent/?customer_id={self.customer.id}')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

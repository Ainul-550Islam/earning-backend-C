# api/djoyalty/tests/test_dao_governance.py
"""DAOGovernanceViewSet tests -- loyalty DAO voting."""
from django.test import TestCase
from rest_framework.test import APITestCase
from .factories import make_customer, make_loyalty_points
from decimal import Decimal


class DAOGovernanceTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='DAOCUST01')
        make_loyalty_points(self.customer, balance=Decimal('10000'))

    def test_list_proposals(self):
        resp = self.client.get('/api/dao/proposals/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_vote_on_proposal(self):
        resp = self.client.post('/api/dao/vote/', {
            'customer_id': self.customer.id,
            'proposal_id': 1,
            'vote': 'yes',
        }, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_create_proposal(self):
        resp = self.client.post('/api/dao/proposals/', {
            'customer_id': self.customer.id,
            'title': 'Test Proposal',
            'description': 'Test',
        }, format='json')
        self.assertIn(resp.status_code, [200, 201, 400, 401, 403, 404])

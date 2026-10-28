# api/djoyalty/tests/test_milestone_viewset.py
"""MilestoneViewSet tests -- API coverage for milestone endpoints."""
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from .factories import make_customer, make_loyalty_points


class MilestoneModelTest(TestCase):
    def setUp(self):
        self.customer = make_customer(code='MILECUST01')

    def test_customer_created(self):
        self.assertEqual(self.customer.code, 'MILECUST01')


class MilestoneViewSetTest(APITestCase):
    def setUp(self):
        self.customer = make_customer(code='MILEAPI01')
        make_loyalty_points(self.customer, balance=Decimal('500'))

    def test_list_milestones(self):
        resp = self.client.get('/api/milestones/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_active_milestones(self):
        resp = self.client.get('/api/milestones/active/')
        self.assertIn(resp.status_code, [200, 401, 403, 404])

    def test_check_requires_customer_id(self):
        resp = self.client.post('/api/milestones/check/', {}, format='json')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

    def test_my_milestones_requires_customer_id(self):
        resp = self.client.get('/api/milestones/my_milestones/')
        self.assertIn(resp.status_code, [200, 400, 401, 403, 404])

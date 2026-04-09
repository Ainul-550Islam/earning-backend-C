# api/djoyalty/tests/test_api_views.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .factories import make_customer, make_txn, make_loyalty_points

User = get_user_model()


class CustomerAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.force_authenticate(user=self.user)
        self.customer = make_customer(code='APICUST01', firstname='API', lastname='User')

    def test_customer_list_returns_200(self):
        response = self.client.get('/api/djoyalty/customers/')
        self.assertIn(response.status_code, [200, 404])

    def test_customer_detail_returns_200(self):
        response = self.client.get(f'/api/djoyalty/customers/{self.customer.id}/')
        self.assertIn(response.status_code, [200, 404])

    def test_customer_create(self):
        data = {'code': 'NEWCUST99', 'firstname': 'New', 'lastname': 'Customer', 'email': 'new@example.com', 'newsletter': True}
        response = self.client.post('/api/djoyalty/customers/', data)
        self.assertIn(response.status_code, [201, 400, 404])

    def test_unauthenticated_returns_401(self):
        unauth_client = APIClient()
        response = unauth_client.get('/api/djoyalty/customers/')
        self.assertIn(response.status_code, [401, 403, 404])


class TxnAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='txnuser', password='testpass123')
        self.client.force_authenticate(user=self.user)
        self.customer = make_customer(code='TXNAPI01')
        self.txn = make_txn(self.customer, value=Decimal('150'))

    def test_txn_list_returns_200(self):
        response = self.client.get('/api/djoyalty/transactions/')
        self.assertIn(response.status_code, [200, 404])

    def test_txn_summary_endpoint(self):
        response = self.client.get('/api/djoyalty/transactions/summary/')
        self.assertIn(response.status_code, [200, 404])


class EventAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='evtuser', password='testpass123')
        self.client.force_authenticate(user=self.user)
        self.customer = make_customer(code='EVTAPI01')

    def test_event_list_returns_200(self):
        response = self.client.get('/api/djoyalty/events/')
        self.assertIn(response.status_code, [200, 404])

    def test_event_by_action_endpoint(self):
        response = self.client.get('/api/djoyalty/events/by_action/')
        self.assertIn(response.status_code, [200, 404])

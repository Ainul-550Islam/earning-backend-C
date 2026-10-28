# api/support/tests/test_csat.py  — WORLD #1
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from api.support.tests.factories import SupportTicketFactory, UserFactory

class CSATRatingTest(TestCase):
    def setUp(self):
        self.user   = UserFactory()
        self.ticket = SupportTicketFactory(user=self.user, status='resolved')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_rate_ticket_valid(self):
        response = self.client.post(f'/api/support/tickets/{self.ticket.ticket_id}/rate/', {'score': 5, 'comment': 'Great!'})
        self.assertIn(response.status_code, [200, 201])

    def test_rate_invalid_score(self):
        response = self.client.post(f'/api/support/tickets/{self.ticket.ticket_id}/rate/', {'score': 6})
        self.assertEqual(response.status_code, 400)
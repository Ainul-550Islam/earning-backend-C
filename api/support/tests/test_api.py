# api/support/tests/test_api.py
"""Integration tests for support API endpoints."""
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch


def make_user(username='api_u', staff=False):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f'{username}@t.com', password='p', is_staff=staff
    )


class TicketCreateAPITest(APITestCase):
    def setUp(self):
        self.user = make_user('create_u')
        self.client.force_authenticate(user=self.user)

    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_ticket_success(self, m1, m2, m3, m4):
        r = self.client.post('/api/support/tickets/', {
            'subject':     'Test ticket subject',
            'description': 'This is a detailed description.',
            'category':    'technical',
        })
        self.assertIn(r.status_code, [200, 201])

    def test_create_ticket_missing_fields(self):
        r = self.client.post('/api/support/tickets/', {'subject': 'Only subject'})
        self.assertIn(r.status_code, [400, 422])


class RatingAPITest(APITestCase):
    def setUp(self):
        self.user = make_user('rate_u')
        self.client.force_authenticate(user=self.user)

    def test_rate_ticket(self):
        from api.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=self.user, subject='T', description='D',
            category='technical', status='resolved',
        )
        r = self.client.post(
            f'/api/support/tickets/{t.ticket_id}/rate/',
            {'score': 5, 'comment': 'Great!'}
        )
        self.assertIn(r.status_code, [200, 201])
        t.refresh_from_db()
        self.assertEqual(t.satisfaction_rating, 5)

    def test_invalid_rating(self):
        from api.support.models import SupportTicket
        t = SupportTicket.objects.create(
            user=self.user, subject='T', description='D',
            category='technical', status='resolved',
        )
        r = self.client.post(f'/api/support/tickets/{t.ticket_id}/rate/', {'score': 10})
        self.assertIn(r.status_code, [400, 422])


class FAQAPITest(APITestCase):
    def test_faq_helpful_vote(self):
        from api.support.models import FAQ
        faq  = FAQ.objects.create(question='Q?', answer='A.', category='g', is_active=True)
        user = make_user('vote_u')
        self.client.force_authenticate(user=user)
        r = self.client.post(f'/api/support/faqs/{faq.id}/helpful/', {'helpful': True})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        faq.refresh_from_db()
        self.assertEqual(faq.helpful_yes, 1)
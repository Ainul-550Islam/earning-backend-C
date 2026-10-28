# api/support/tests/test_use_cases.py
"""Tests for use cases."""
from django.test import TestCase
from unittest.mock import patch


def make_user(un='uc_u'):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username=un, email=f'{un}@t.com', password='p')


class CreateTicketUseCaseTest(TestCase):
    @patch('support.services.TicketService._notify_created')
    @patch('support.services.TicketService._auto_assign')
    @patch('support.services.TicketService._setup_sla')
    @patch('support.services.TicketService._trigger_automation')
    def test_create_success(self, m1, m2, m3, m4):
        from api.support.use_cases import CreateTicketUseCase
        user   = make_user('uc1')
        result = CreateTicketUseCase().execute(user, {
            'subject': 'Test ticket subject', 'description': 'Detailed description.',
            'category': 'technical',
        })
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['ticket'])

    def test_create_invalid_subject(self):
        from api.support.use_cases import CreateTicketUseCase
        user   = make_user('uc2')
        result = CreateTicketUseCase().execute(user, {
            'subject': 'hi', 'description': 'description.', 'category': 'technical',
        })
        self.assertFalse(result['success'])
        self.assertIsNotNone(result['error'])

    def test_rate_ticket(self):
        from api.support.models import SupportTicket
        from api.support.use_cases import RateTicketUseCase
        user   = make_user('uc_rate')
        ticket = SupportTicket.objects.create(
            user=user, subject='T', description='D', category='technical', status='resolved'
        )
        result = RateTicketUseCase().execute(ticket.ticket_id, user, score=5)
        self.assertTrue(result['success'])
        ticket.refresh_from_db()
        self.assertEqual(ticket.satisfaction_rating, 5)

    def test_rate_invalid_score(self):
        from api.support.models import SupportTicket
        from api.support.use_cases import RateTicketUseCase
        user   = make_user('uc_bad')
        ticket = SupportTicket.objects.create(
            user=user, subject='T', description='D', category='technical', status='resolved'
        )
        result = RateTicketUseCase().execute(ticket.ticket_id, user, score=10)
        self.assertFalse(result['success'])


class MarkFAQHelpfulUseCaseTest(TestCase):
    def test_helpful_vote(self):
        from api.support.models import FAQ
        from api.support.use_cases import MarkFAQHelpfulUseCase
        faq    = FAQ.objects.create(question='Q?', answer='A.', category='g', is_active=True)
        result = MarkFAQHelpfulUseCase().execute(faq.id, helpful=True)
        self.assertTrue(result['success'])
        faq.refresh_from_db()
        self.assertEqual(faq.helpful_yes, 1)

    def test_nonexistent_faq(self):
        from api.support.use_cases import MarkFAQHelpfulUseCase
        result = MarkFAQHelpfulUseCase().execute(99999, helpful=True)
        self.assertFalse(result['success'])
# api/support/tests/test_integration.py  — WORLD #1
"""Full ticket lifecycle integration test."""
from django.test import TestCase
from unittest.mock import patch
from api.support.services import ticket_service
from api.support.tests.factories import UserFactory, SupportAgentFactory

class FullTicketLifecycleTest(TestCase):
    def setUp(self):
        self.user  = UserFactory()
        self.agent = SupportAgentFactory()
        self.agent.user.is_staff = True
        self.agent.user.save()

    @patch('support.services.TicketService._notify_ticket_created')
    @patch('support.services.TicketService._ai_classify_async')
    def test_full_lifecycle(self, mock_ai, mock_notify):
        # 1. Create ticket
        ticket = ticket_service.create(self.user, {
            'subject': 'Payment not credited', 'description': 'I completed an offer but coins not added.',
            'category': 'coins', 'priority': 'high',
        })
        self.assertEqual(ticket.status, 'open')
        self.assertTrue(ticket.ticket_id.startswith('TKT'))

        # 2. Agent replies
        msg = ticket_service.add_message(ticket.ticket_id, self.agent.user, 'We are looking into it.', is_agent=True)
        self.assertEqual(msg.is_agent, True)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'waiting_user')

        # 3. User replies
        ticket_service.add_message(ticket.ticket_id, self.user, 'Thank you!', is_agent=False)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'in_progress')

        # 4. Resolve
        ticket = ticket_service.resolve(ticket.ticket_id, self.agent.user, 'Issue resolved.')
        self.assertEqual(ticket.status, 'resolved')
        self.assertIsNotNone(ticket.resolved_at)

        # 5. Rate
        ticket.satisfaction_rating = 5
        ticket.save()
        self.assertEqual(ticket.satisfaction_rating, 5)
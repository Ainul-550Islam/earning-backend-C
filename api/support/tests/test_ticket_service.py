# api/support/tests/test_ticket_service.py  — WORLD #1
from django.test import TestCase
from unittest.mock import patch
from api.support.services import TicketService, ticket_service
from api.support.tests.factories import UserFactory

class TicketServiceCreateTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_create_ticket_returns_ticket(self):
        with patch.object(ticket_service, '_notify_ticket_created'),              patch.object(ticket_service, '_auto_assign'),              patch.object(ticket_service, '_setup_sla'),              patch.object(ticket_service, '_ai_classify_async'):
            ticket = ticket_service.create(self.user, {
                'subject': 'Test issue', 'description': 'Detailed description here.',
                'category': 'technical', 'priority': 'medium',
            })
        self.assertIsNotNone(ticket)
        self.assertIsNotNone(ticket.ticket_id)
        self.assertEqual(ticket.user, self.user)
        self.assertEqual(ticket.status, 'open')

    def test_get_stats_returns_dict(self):
        stats = ticket_service.get_stats()
        self.assertIn('total', stats)
        self.assertIn('open', stats)
        self.assertIn('resolved', stats)

    def test_category_priority_mapping(self):
        svc = TicketService()
        self.assertEqual(svc.CATEGORY_PRIORITY_MAP.get('fraud'), 'urgent')
        self.assertEqual(svc.CATEGORY_PRIORITY_MAP.get('payment'), 'high')
        self.assertEqual(svc.CATEGORY_PRIORITY_MAP.get('other'), 'low')
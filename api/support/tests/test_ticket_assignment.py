# api/support/tests/test_ticket_assignment.py  — WORLD #1
from django.test import TestCase
from api.support.tests.factories import SupportTicketFactory, SupportAgentFactory
from api.support.services.ticket.TicketAssignmentService import ticket_assignment_service

class TicketAssignmentTest(TestCase):
    def test_assign_to_agent(self):
        ticket = SupportTicketFactory()
        agent  = SupportAgentFactory()
        result = ticket_assignment_service.assign(ticket, agent.id)
        self.assertTrue(result.get('success'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, agent.user)

    def test_assign_invalid_agent(self):
        ticket = SupportTicketFactory()
        result = ticket_assignment_service.assign(ticket, 99999)
        self.assertIn('error', result)

    def test_unassign(self):
        agent  = SupportAgentFactory()
        ticket = SupportTicketFactory(assigned_to=agent.user)
        result = ticket_assignment_service.unassign(ticket)
        self.assertTrue(result.get('success'))
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assigned_to)
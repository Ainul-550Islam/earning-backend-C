# api/support/tests/test_ticket_routing.py  — WORLD #1
from django.test import TestCase
from api.support.services.ticket.TicketRoutingService import TicketRoutingService
from api.support.tests.factories import SupportTicketFactory

class TicketRoutingTest(TestCase):
    def test_route_by_content_payment(self):
        svc    = TicketRoutingService()
        ticket = SupportTicketFactory(subject='bkash payment not credited', category='payment')
        slug   = svc.route_by_content(ticket)
        self.assertEqual(slug, 'payment')

    def test_route_by_content_kyc(self):
        svc    = TicketRoutingService()
        ticket = SupportTicketFactory(subject='NID verification failed', description='My document not accepted.')
        slug   = svc.route_by_content(ticket)
        self.assertEqual(slug, 'kyc')
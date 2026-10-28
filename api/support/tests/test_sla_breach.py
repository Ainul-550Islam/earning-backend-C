# api/support/tests/test_sla_breach.py  — WORLD #1
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from api.support.services import sla_service
from api.support.models import TicketSLA
from api.support.tests.factories import SupportTicketFactory

class SLABreachDetectionTest(TestCase):
    def test_no_breach_on_fresh_ticket(self):
        ticket = SupportTicketFactory()
        sla_service._setup_sla(ticket)
        result = sla_service.check_breaches()
        sla = TicketSLA.objects.get(ticket=ticket)
        self.assertFalse(sla.first_response_breached)

    def test_breach_detected_on_overdue(self):
        ticket = SupportTicketFactory()
        sla_service._setup_sla(ticket)
        sla = TicketSLA.objects.get(ticket=ticket)
        # Simulate overdue
        sla.first_response_due = timezone.now() - timedelta(hours=2)
        sla.save(update_fields=['first_response_due'])
        sla_service.check_breaches()
        sla.refresh_from_db()
        self.assertTrue(sla.first_response_breached)
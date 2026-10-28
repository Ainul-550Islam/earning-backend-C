# api/support/tests/test_sla_service.py  — WORLD #1
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from api.support.services import SLAService, sla_service
from api.support.tests.factories import SupportTicketFactory

class SLAServiceTest(TestCase):
    def test_check_breaches_returns_dict(self):
        result = sla_service.check_breaches()
        self.assertIn('checked', result)
        self.assertIn('breached', result)

    def test_compliance_report(self):
        report = sla_service.get_compliance_report(days=7)
        self.assertIn('compliance_rate', report)
        self.assertIn('total', report)

    def test_setup_sla_creates_record(self):
        from api.support.models import TicketSLA
        ticket = SupportTicketFactory()
        sla_service._setup_sla(ticket)
        self.assertTrue(TicketSLA.objects.filter(ticket=ticket).exists())
        sla = TicketSLA.objects.get(ticket=ticket)
        self.assertIsNotNone(sla.first_response_due)
        self.assertIsNotNone(sla.resolution_due)
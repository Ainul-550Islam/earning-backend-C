# api/support/tests/test_automation_engine.py  — WORLD #1
from django.test import TestCase
from api.support.services.automation.AutomationEngine import AutomationEngine
from api.support.tests.factories import SupportTicketFactory

class AutomationEngineTest(TestCase):
    def test_evaluate_no_rules(self):
        engine = AutomationEngine()
        ticket = SupportTicketFactory()
        results = engine.evaluate_and_run('ticket_created', ticket)
        self.assertIsInstance(results, list)
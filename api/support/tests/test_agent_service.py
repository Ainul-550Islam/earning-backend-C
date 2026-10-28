# api/support/tests/test_agent_service.py  — WORLD #1
from django.test import TestCase
from api.support.services.agent.AgentService import AgentService, WorkloadBalancerService
from api.support.tests.factories import SupportAgentFactory

class AgentServiceTest(TestCase):
    def test_get_leaderboard_returns_list(self):
        SupportAgentFactory()
        svc = AgentService()
        board = svc.get_leaderboard(days=30)
        self.assertIsInstance(board, list)

    def test_workload_report(self):
        SupportAgentFactory()
        svc = WorkloadBalancerService()
        report = svc.get_workload_report()
        self.assertIsInstance(report, list)
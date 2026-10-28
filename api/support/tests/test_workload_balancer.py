# api/support/tests/test_workload_balancer.py  — WORLD #1
from django.test import TestCase
from api.support.services.agent.AgentService import WorkloadBalancerService
from api.support.tests.factories import SupportAgentFactory

class WorkloadBalancerTest(TestCase):
    def test_get_workload_report_empty(self):
        svc = WorkloadBalancerService()
        report = svc.get_workload_report()
        self.assertIsInstance(report, list)

    def test_get_workload_report_with_agents(self):
        SupportAgentFactory()
        SupportAgentFactory()
        svc = WorkloadBalancerService()
        report = svc.get_workload_report()
        self.assertEqual(len(report), 2)

    def test_report_sorted_by_load(self):
        SupportAgentFactory()
        svc = WorkloadBalancerService()
        report = svc.get_workload_report()
        if len(report) > 1:
            self.assertGreaterEqual(report[0]['load_pct'], report[-1]['load_pct'])
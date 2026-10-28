"""
tests/test_health.py — NEWLY CREATED
Tests for the root-level health.py module (0% tested previously).

check_database() previously ran `WHERE table_schema = DATABASE()` -
DATABASE() is a MySQL-only function and doesn't exist in PostgreSQL, the
production backend. Every call raised a DatabaseError that got caught and
reported as "unhealthy", regardless of actual DB state - and because this
module had no tests at all, that never surfaced until this audit.
"""
from django.test import TestCase

from api.alerts.health import HealthChecker, HealthCheckStatus


class HealthCheckerTest(TestCase):
    def test_import_and_instantiate(self):
        checker = HealthChecker()
        self.assertIsNotNone(checker)
        self.assertEqual(checker.checks, [])

    def test_check_database_returns_true_and_healthy(self):
        """Regression test for the DATABASE()-is-MySQL-only bug."""
        checker = HealthChecker()
        result = checker.check_database()
        self.assertTrue(result, msg=checker.checks[-1] if checker.checks else None)
        self.assertEqual(checker.checks[-1]['status'], HealthCheckStatus.HEALTHY)
        self.assertEqual(checker.overall_status, HealthCheckStatus.HEALTHY)

    def test_check_database_reports_expected_tables(self):
        checker = HealthChecker()
        checker.check_database()
        details = checker.checks[-1]['details']
        self.assertIn('tables_found', details)
        # alerts_alertlog / alerts_alertrule exist in the test DB (migrations run)
        self.assertEqual(details['tables_found'], 2)

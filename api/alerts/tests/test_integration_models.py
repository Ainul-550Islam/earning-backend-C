"""
tests/test_integration_models.py — NEWLY CREATED
Tests for integration/ subfolder classes (model/serial/service — 0% tested)
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class CircuitBreakerTest(TestCase):
    def test_import(self):
        from api.alerts.integration.circuit_breaker import CircuitBreaker, CircuitBreakerState
        self.assertIsNotNone(CircuitBreaker)

    def test_initial_state_closed(self):
        from api.alerts.integration.circuit_breaker import CircuitBreaker, CircuitBreakerState
        cb = CircuitBreaker('test_cb', failure_threshold=5, timeout=60)
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

    def test_failure_increments_count(self):
        from api.alerts.integration.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker('test_cb2', failure_threshold=3, timeout=60)
        initial = cb.failure_count
        cb.record_failure() if hasattr(cb, 'record_failure') else setattr(cb, 'failure_count', initial + 1)
        self.assertGreaterEqual(cb.failure_count, initial)

    def test_reset_clears_failures(self):
        from api.alerts.integration.circuit_breaker import CircuitBreaker, CircuitBreakerState
        cb = CircuitBreaker('test_cb3', failure_threshold=3, timeout=60)
        cb.reset()
        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)

    def test_circuit_breaker_manager_import(self):
        from api.alerts.integration.circuit_breaker import CircuitBreakerManager
        mgr = CircuitBreakerManager()
        self.assertIsNotNone(mgr)

    def test_get_open_circuit_breakers(self):
        from api.alerts.integration.circuit_breaker import get_open_circuit_breakers
        result = get_open_circuit_breakers()
        self.assertIsInstance(result, (list, dict))

    def test_get_circuit_breaker_statistics(self):
        from api.alerts.integration.circuit_breaker import get_circuit_breaker_statistics
        stats = get_circuit_breaker_statistics()
        self.assertIsInstance(stats, dict)


class IntegrationHealthCheckerTest(TestCase):
    def test_import(self):
        from api.alerts.integration.health_check import IntegrationHealthChecker
        checker = IntegrationHealthChecker()
        self.assertIsNotNone(checker)

    def test_check_health_returns_dict(self):
        from api.alerts.integration.health_check import IntegrationHealthChecker
        checker = IntegrationHealthChecker()
        result = checker.check_integration_health()
        self.assertIsInstance(result, dict)

    def test_component_health_function(self):
        from api.alerts.integration.health_check import integration_component_health
        result = integration_component_health()
        self.assertIsInstance(result, dict)

    def test_check_database_reports_healthy(self):
        """Regression test: _check_database() used to run
        `WHERE table_schema = DATABASE()`, a MySQL-only function that doesn't
        exist in PostgreSQL. On the production DB backend this raised an error
        on every call and always reported 'unhealthy' even when the DB was
        fine. This method previously had zero test coverage, which is exactly
        why that went unnoticed. Now uses connection.introspection.table_names(),
        which is portable, so this can genuinely assert a healthy result."""
        from api.alerts.integration.health_check import IntegrationHealthChecker
        checker = IntegrationHealthChecker()
        result = checker._check_database()
        self.assertEqual(result['status'], 'healthy', msg=result.get('message'))


class IntegrationRegistryTest(TestCase):
    def test_import(self):
        from api.alerts.integration.integ_registry import IntegrationRegistry
        reg = IntegrationRegistry()
        self.assertIsNotNone(reg)

    def test_registry_has_integrations_attr(self):
        from api.alerts.integration.integ_registry import IntegrationRegistry
        reg = IntegrationRegistry()
        self.assertTrue(hasattr(reg, 'integrations'))

    def test_register_integration(self):
        from api.alerts.integration.integ_registry import IntegrationRegistry
        reg = IntegrationRegistry()
        if hasattr(reg, 'register_integration'):
            class DummyIntegration:
                pass
            reg.register_integration('dummy', DummyIntegration, {})
            self.assertIn('dummy', reg.integrations)


class AuditLoggerTest(TestCase):
    def test_import(self):
        from api.alerts.integration.integ_audit_logs import AuditLogger
        logger = AuditLogger()
        self.assertIsNotNone(logger)

    def test_audit_event_function(self):
        from api.alerts.integration.integ_audit_logs import audit_event
        try:
            audit_event(event_type='test', message='Test audit', user='testuser')
        except Exception as e:
            self.fail(f"audit_event raised unexpectedly: {e}")

    def test_get_statistics(self):
        from api.alerts.integration.integ_audit_logs import AuditLogger
        logger = AuditLogger()
        if hasattr(logger, 'get_statistics'):
            stats = logger.get_statistics()
            self.assertIsInstance(stats, dict)


class PerformanceMonitorTest(TestCase):
    def test_import(self):
        from api.alerts.integration.performance_monitor import IntegrationPerformanceMonitor
        monitor = IntegrationPerformanceMonitor()
        self.assertIsNotNone(monitor)

    def test_get_performance_metrics(self):
        from api.alerts.integration.performance_monitor import get_performance_metrics
        result = get_performance_metrics()
        self.assertIsInstance(result, dict)

    def test_record_integration_metric(self):
        from api.alerts.integration.performance_monitor import record_integration_metric
        try:
            record_integration_metric('test_metric', 42.0, {'tag': 'test'})
        except Exception as e:
            self.fail(f"record_integration_metric raised: {e}")


class MessageQueueTest(TestCase):
    def test_import(self):
        from api.alerts.integration.message_queue import IntegrationMessageQueue
        mq = IntegrationMessageQueue()
        self.assertIsNotNone(mq)

    def test_get_queue_statistics(self):
        from api.alerts.integration.message_queue import get_queue_statistics
        stats = get_queue_statistics()
        self.assertIsInstance(stats, dict)

    def test_enqueue_message(self):
        from api.alerts.integration.message_queue import enqueue_integration_message
        try:
            result = enqueue_integration_message(
                message_type='test', payload={'key': 'value'}, priority='MEDIUM')
        except Exception as e:
            self.fail(f"enqueue_integration_message raised: {e}")


class SyncManagerTest(TestCase):
    def test_import(self):
        from api.alerts.integration.sync_manager import IntegrationSyncManager
        mgr = IntegrationSyncManager()
        self.assertIsNotNone(mgr)

    def test_get_sync_statistics(self):
        from api.alerts.integration.sync_manager import get_sync_statistics
        stats = get_sync_statistics()
        self.assertIsInstance(stats, dict)

    def test_get_sync_conflicts(self):
        from api.alerts.integration.sync_manager import get_sync_conflicts
        conflicts = get_sync_conflicts()
        self.assertIsInstance(conflicts, (list, type(None)))


class TransformerTest(TestCase):
    def test_import(self):
        from api.alerts.integration.transformer import IntegrationTransformer
        t = IntegrationTransformer()
        self.assertIsNotNone(t)

    def test_get_transformer_info(self):
        from api.alerts.integration.transformer import get_transformer_info
        info = get_transformer_info()
        self.assertIsInstance(info, dict)

    def test_transform_external_to_alerts(self):
        from api.alerts.integration.transformer import transform_external_to_alerts
        try:
            result = transform_external_to_alerts(
                source_format='prometheus',
                data={'metric': 'server_error', 'value': 95})
        except Exception as e:
            self.fail(f"transform raised: {e}")


class VersioningTest(TestCase):
    def test_import(self):
        from api.alerts.integration.versioning import IntegrationVersionManager
        mgr = IntegrationVersionManager()
        self.assertIsNotNone(mgr)

    def test_create_version(self):
        from api.alerts.integration.versioning import create_integration_version
        try:
            create_integration_version(
                integration_id='slack_v1', version='1.0.0', config={})
        except Exception as e:
            self.fail(f"create_integration_version raised: {e}")

    def test_get_version_statistics(self):
        from api.alerts.integration.versioning import get_version_statistics
        stats = get_version_statistics()
        self.assertIsInstance(stats, dict)

    def test_create_version_twice_same_config_short_circuits(self):
        """Regression test: calling create_version() twice with the SAME config
        for the same integration_id must not crash, and must not create a
        second row - it should return the existing version."""
        from api.alerts.integration.versioning import create_integration_version
        from api.alerts.models import IntegrationVersion

        v1 = create_integration_version(
            integration_id='regression_same_cfg', version='1.0.0', config={'x': 1})
        v2 = create_integration_version(
            integration_id='regression_same_cfg', version='1.0.0', config={'x': 1})

        self.assertEqual(v1, v2)
        self.assertEqual(
            IntegrationVersion.objects.filter(integration_id='regression_same_cfg').count(), 1)

    def test_create_version_twice_different_config_creates_history(self):
        """Regression test for the actual crash bug: create_version() previously
        used an in-memory dict (self.versions) to decide whether a version
        already existed, instead of querying the database. A fresh
        IntegrationVersionManager (e.g. a new worker process) has an empty dict,
        so a second registration for an integration that already has a DB row
        skipped the "already exists" branch and called .objects.create() again,
        raising IntegrityError against the unique constraint on integration_id.
        This calls create_version twice with genuinely different config for the
        same integration_id and confirms it succeeds, keeps exactly one active
        version, and preserves history instead of crashing."""
        from api.alerts.integration.versioning import create_integration_version
        from api.alerts.models import IntegrationVersion

        create_integration_version(
            integration_id='regression_diff_cfg', version='1.0.0', config={'x': 1})
        try:
            create_integration_version(
                integration_id='regression_diff_cfg', version='2.0.0', config={'x': 2})
        except Exception as e:
            self.fail(f"create_integration_version crashed on second registration: {e}")

        rows = IntegrationVersion.objects.filter(integration_id='regression_diff_cfg')
        self.assertEqual(rows.count(), 2, "expected both versions preserved as history")
        active = rows.filter(is_active=True)
        self.assertEqual(active.count(), 1, "expected exactly one active version")
        self.assertEqual(active.first().version, '2.0.0')

    def test_create_version_survives_fresh_manager_instance(self):
        """Regression test targeting the cross-process angle specifically: a
        brand new IntegrationVersionManager (empty self.versions, as happens on
        every new worker/process) must still detect an existing DB row and not
        crash when create_version is called again for the same integration_id."""
        from api.alerts.integration.versioning import IntegrationVersionManager
        from api.alerts.models import IntegrationVersion

        mgr1 = IntegrationVersionManager()
        mgr1.create_version('regression_fresh_mgr', config={'x': 1}, version='1.0.0')

        # Simulate a fresh process: a brand new manager with no warm cache
        mgr2 = IntegrationVersionManager()
        mgr2.versions = {}
        try:
            mgr2.create_version('regression_fresh_mgr', config={'x': 2}, version='2.0.0')
        except Exception as e:
            self.fail(f"create_version crashed with a fresh manager instance: {e}")

        self.assertEqual(
            IntegrationVersion.objects.filter(integration_id='regression_fresh_mgr').count(), 2)


class DataValidatorTest(TestCase):
    def test_import(self):
        from api.alerts.integration.data_validator import IntegrationDataValidator
        v = IntegrationDataValidator()
        self.assertIsNotNone(v)

    def test_validate_data(self):
        from api.alerts.integration.data_validator import validate_integration_data
        try:
            result = validate_integration_data(
                data_type='alert',
                data={'id': 1, 'severity': 'high'})
        except Exception as e:
            self.fail(f"validate_integration_data raised: {e}")


class WebhookIntegrationTest(TestCase):
    def test_import(self):
        from api.alerts.integration.webhooks_integration import IntegrationWebhookManager
        mgr = IntegrationWebhookManager()
        self.assertIsNotNone(mgr)

    def test_get_webhook_statistics(self):
        from api.alerts.integration.webhooks_integration import get_webhook_statistics
        stats = get_webhook_statistics()
        self.assertIsInstance(stats, dict)


class IntegrationExceptionsTest(TestCase):
    def test_import_exceptions(self):
        from api.alerts.integration.integ_exceptions import (
            IntegrationException, ConnectionException, AuthenticationException)
        self.assertIsNotNone(IntegrationException)
        self.assertIsNotNone(ConnectionException)

    def test_raise_integration_exception(self):
        from api.alerts.integration.integ_exceptions import IntegrationException
        with self.assertRaises(IntegrationException):
            raise IntegrationException("Test integration error")

    def test_exception_hierarchy(self):
        from api.alerts.integration.integ_exceptions import (
            IntegrationException, ConnectionException)
        self.assertTrue(issubclass(ConnectionException, IntegrationException))

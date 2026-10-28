"""
test_integration_system.py – Smoke tests for INTEGRATION_SYSTEM core modules.

These tests verify importability and basic instantiation of the core classes.
Full behavioural tests for each integration connector belong in dedicated
test files once the INTEGRATION_SYSTEM is wired into the main pipeline.
"""
from django.test import TestCase


class IntegrationSystemImportTests(TestCase):
    """Verify all INTEGRATION_SYSTEM subpackages are importable."""

    def test_core_connectors_package_importable(self):
        import api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS  # noqa

    def test_bridge_bus_package_importable(self):
        import api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS  # noqa

    def test_security_validation_package_importable(self):
        import api.postback.INTEGRATION_SYSTEM.SECURITY_VALIDATION  # noqa

    def test_monitoring_logs_package_importable(self):
        import api.postback.INTEGRATION_SYSTEM.MONITORING_LOGS  # noqa

    def test_integ_registry_importable(self):
        from api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS import integ_registry
        self.assertTrue(hasattr(integ_registry, "IntegrationRegistry"))

    def test_integ_handler_importable(self):
        from api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS import integ_handler
        self.assertTrue(hasattr(integ_handler, "IntegrationHandler"))

    def test_integ_adapter_importable(self):
        from api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS import integ_adapter
        self.assertTrue(hasattr(integ_adapter, "IntegrationAdapter"))


class IntegrationRegistryTests(TestCase):

    def setUp(self):
        from api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS.integ_registry import (
            IntegrationRegistry
        )
        self.registry_cls = IntegrationRegistry

    def test_registry_is_instantiable(self):
        try:
            registry = self.registry_cls()
            self.assertIsNotNone(registry)
        except TypeError as exc:
            self.fail(f"IntegrationRegistry is not instantiable: {exc}")

    def test_registry_has_register_method(self):
        self.assertTrue(
            hasattr(self.registry_cls, "register"),
            "IntegrationRegistry must have a register() method",
        )

    def test_registry_has_get_method(self):
        self.assertTrue(
            hasattr(self.registry_cls, "get") or hasattr(self.registry_cls, "get_integration"),
            "IntegrationRegistry must have a get() or get_integration() method",
        )


class IntegrationHandlerTests(TestCase):

    def test_handler_class_has_handle_method(self):
        from api.postback.INTEGRATION_SYSTEM.CORE_CONNECTORS.integ_handler import (
            IntegrationHandler
        )
        self.assertTrue(
            hasattr(IntegrationHandler, "handle") or hasattr(IntegrationHandler, "process"),
            "IntegrationHandler must have a handle() or process() method",
        )


class BridgeBusImportTests(TestCase):

    def test_bridge_importable(self):
        from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS import bridge
        self.assertTrue(hasattr(bridge, "Bridge") or hasattr(bridge, "BridgeManager"))

    def test_data_bridge_importable(self):
        from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS import data_bridge
        self.assertTrue(hasattr(data_bridge, "DataBridge"))

    def test_circuit_breaker_importable(self):
        from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS import circuit_breaker
        self.assertIsNotNone(circuit_breaker)

    def test_message_queue_importable(self):
        from api.postback.INTEGRATION_SYSTEM.BRIDGE_BUS import message_queue
        self.assertIsNotNone(message_queue)


class SecurityValidationImportTests(TestCase):

    def test_auth_bridge_importable(self):
        from api.postback.INTEGRATION_SYSTEM.SECURITY_VALIDATION import auth_bridge
        self.assertIsNotNone(auth_bridge)

    def test_data_validator_importable(self):
        from api.postback.INTEGRATION_SYSTEM.SECURITY_VALIDATION import data_validator
        self.assertIsNotNone(data_validator)

    def test_fallback_logic_importable(self):
        from api.postback.INTEGRATION_SYSTEM.SECURITY_VALIDATION import fallback_logic
        self.assertIsNotNone(fallback_logic)


class MonitoringLogsImportTests(TestCase):

    def test_health_check_importable(self):
        from api.postback.INTEGRATION_SYSTEM.MONITORING_LOGS import health_check
        self.assertIsNotNone(health_check)

    def test_performance_monitor_importable(self):
        from api.postback.INTEGRATION_SYSTEM.MONITORING_LOGS import performance_monitor
        self.assertIsNotNone(performance_monitor)

    def test_sync_manager_importable(self):
        from api.postback.INTEGRATION_SYSTEM.MONITORING_LOGS import sync_manager
        self.assertIsNotNone(sync_manager)

    def test_audit_logs_importable(self):
        from api.postback.INTEGRATION_SYSTEM.MONITORING_LOGS import integ_audit_logs
        self.assertIsNotNone(integ_audit_logs)

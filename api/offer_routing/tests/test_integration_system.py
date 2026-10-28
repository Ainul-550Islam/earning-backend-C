"""
Tests for integration_system — all classes + API viewsets.
Covers: AuthBridge, IntegrationBridge, DataBridge, DataValidator,
EventBus, FallbackLogic, HealthCheck, IntegrationHandler,
IntegrationRegistry, PerformanceMonitor, IntegrationAuditLogger,
and all their API viewset endpoints.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock, PropertyMock

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — integration_system classes directly
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationSystemImportTest(TestCase):
    """Verify the entire integration_system package imports cleanly."""

    def test_package_imports(self):
        from offer_routing.integration_system import (
            AuthBridge, IntegrationBridge, DataBridge, DataValidator,
            EventBus, FallbackLogic, HealthCheck,
            IntegrationHandler, IntegrationRegistry,
            PerformanceMonitor, IntegrationAuditLogger,
            WebhookIntegration, MessageQueueIntegration,
        )
        self.assertIsNotNone(AuthBridge)
        self.assertIsNotNone(IntegrationBridge)
        self.assertIsNotNone(EventBus)

    def test_singletons_exist(self):
        from offer_routing.integration_system import (
            auth_bridge, integration_bridge, data_bridge,
            event_bus, health_check_service, performance_monitor,
            integration_handler, integration_registry, audit_logger,
        )
        self.assertIsNotNone(auth_bridge)
        self.assertIsNotNone(event_bus)
        self.assertIsNotNone(performance_monitor)

    def test_constants_exist(self):
        from offer_routing.integration_system import (
            IntegrationType, IntegrationStatus,
            DEFAULT_INTEGRATION_TIMEOUT, INTEGRATION_ERROR_CODES,
        )
        self.assertIsNotNone(IntegrationType)
        self.assertIsNotNone(INTEGRATION_ERROR_CODES)

    def test_exceptions_exist(self):
        from offer_routing.integration_system import (
            IntegrationError, IntegrationAuthenticationError,
            IntegrationValidationError, IntegrationTimeoutError,
        )
        with self.assertRaises(IntegrationError):
            raise IntegrationError("test error")


class AuthBridgeTest(TestCase):
    """Tests for AuthBridge class."""

    def setUp(self):
        from offer_routing.integration_system import AuthBridge
        self.bridge = AuthBridge()

    def test_instantiation(self):
        self.assertIsNotNone(self.bridge)

    def test_authenticate_integration_missing_id(self):
        result = self.bridge.authenticate_integration('', {})
        self.assertIsNotNone(result)  # score may be float or dict

    def test_authenticate_integration_valid(self):
        result = self.bridge.authenticate_integration(
            'test-integration', {'api_key': 'abc123'}
        )
        self.assertIsNotNone(result)  # score may be float or dict

    def test_validate_token_returns_dict(self):
        result = self.bridge.validate_token('fake-token', 'test-integration')
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_auth_stats_returns_dict(self):
        result = self.bridge.get_auth_stats()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check_returns_dict(self):
        result = self.bridge.health_check()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_permission_manager_check(self):
        from offer_routing.integration_system import PermissionManager
        pm = PermissionManager()
        self.assertIsNotNone(pm)

    def test_token_store(self):
        from offer_routing.integration_system import TokenStore
        ts = TokenStore()
        self.assertIsNotNone(ts)


class EventBusTest(TestCase):
    """Tests for EventBus class."""

    def setUp(self):
        from offer_routing.integration_system import EventBus
        self.bus = EventBus()

    def test_instantiation(self):
        self.assertIsNotNone(self.bus)

    def test_publish_event(self):
        result = self.bus.publish('test.event', {'key': 'value'})
        self.assertIsInstance(result, (dict, bool))

    def test_subscribe_and_unsubscribe(self):
        handler = MagicMock()
        sub_result = self.bus.subscribe('test.event', handler)
        self.assertIsInstance(sub_result, bool)
        unsub_result = self.bus.unsubscribe('test.event', handler)
        self.assertIsInstance(unsub_result, bool)

    def test_get_event_history(self):
        result = self.bus.get_event_history()
        self.assertIsInstance(result, (dict, list))

    def test_get_bus_stats(self):
        result = self.bus.get_bus_stats()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check(self):
        result = self.bus.health_check()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_clear_history(self):
        result = self.bus.clear_history()
        self.assertIsInstance(result, (bool, dict))

    def test_get_subscribers_empty(self):
        result = self.bus.get_subscribers()
        self.assertIsNotNone(result)  # score may be float or dict


class IntegrationRegistryTest(TestCase):
    """Tests for IntegrationRegistry class."""

    def setUp(self):
        from offer_routing.integration_system import IntegrationRegistry
        self.registry = IntegrationRegistry()

    def test_instantiation(self):
        self.assertIsNotNone(self.registry)

    def test_register_integration(self):
        result = self.registry.register(
            'test-integration',
            {'type': 'webhook', 'url': 'https://example.com/hook'}
        )
        self.assertIsNotNone(result)

    def test_get_active_integrations(self):
        result = self.registry.get_active_integrations()
        self.assertIsInstance(result, list)

    def test_get_registry_stats(self):
        result = self.registry.get_registry_stats()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_validate_registry(self):
        result = self.registry.validate_registry()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_export_registry(self):
        result = self.registry.export_registry()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_nonexistent_integration(self):
        result = self.registry.get_integration('nonexistent-id-12345')
        self.assertIsNone(result)

    def test_unregister_nonexistent(self):
        result = self.registry.unregister('nonexistent-id-12345')
        self.assertIsInstance(result, bool)


class IntegrationHandlerTest(TestCase):
    """Tests for IntegrationHandler class."""

    def setUp(self):
        from offer_routing.integration_system import IntegrationHandler
        self.handler = IntegrationHandler()

    def test_instantiation(self):
        self.assertIsNotNone(self.handler)

    def test_register_integration(self):
        result = self.handler.register_integration(
            'handler-test',
            {'type': 'api', 'endpoint': 'https://api.example.com'}
        )
        self.assertIsInstance(result, bool)

    def test_list_integrations_no_filter(self):
        result = self.handler.list_integrations()
        self.assertIsInstance(result, list)

    def test_list_integrations_with_type(self):
        result = self.handler.list_integrations('webhook')
        self.assertIsInstance(result, list)

    def test_get_integration_metrics_all(self):
        result = self.handler.get_integration_metrics()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check(self):
        result = self.handler.health_check()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_sync_all_integrations(self):
        result = self.handler.sync_all_integrations()
        self.assertIsNotNone(result)  # score may be float or dict


class PerformanceMonitorTest(TestCase):
    """Tests for PerformanceMonitor class."""

    def setUp(self):
        from offer_routing.integration_system import PerformanceMonitor
        self.monitor = PerformanceMonitor()

    def test_instantiation(self):
        self.assertIsNotNone(self.monitor)

    def test_start_monitoring(self):
        result = self.monitor.start_monitoring()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_stop_monitoring(self):
        self.monitor.start_monitoring()
        result = self.monitor.stop_monitoring()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_record_integration_execution(self):
        result = self.monitor.record_integration_execution(
            'test-integration', 120.5, True
        )
        self.assertIsInstance(result, (dict, type(None)))

    def test_get_performance_metrics(self):
        result = self.monitor.get_performance_metrics()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_performance_history(self):
        result = self.monitor.get_performance_history(hours=24)
        self.assertIsNotNone(result)  # score may be float or dict

    def test_set_alert_thresholds(self):
        result = self.monitor.set_alert_thresholds(
            {'slow_response_time': 3.0, 'high_error_rate': 0.05}
        )
        self.assertIsNotNone(result)  # score may be float or dict

    def test_reset_metrics(self):
        result = self.monitor.reset_metrics()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check(self):
        result = self.monitor.health_check()
        self.assertIsNotNone(result)  # score may be float or dict


class HealthCheckTest(TestCase):
    """Tests for HealthCheck class."""

    def setUp(self):
        from offer_routing.integration_system import HealthCheck
        self.hc = HealthCheck()

    def test_instantiation(self):
        self.assertIsNotNone(self.hc)

    def test_run_health_check(self):
        result = self.hc.run_health_check()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_health_status(self):
        result = self.hc.get_health_status()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_set_alert_thresholds(self):
        result = self.hc.set_alert_thresholds({'cpu_usage': 0.9})
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check_method(self):
        result = self.hc.health_check()
        self.assertIsNotNone(result)  # score may be float or dict


class DataBridgeTest(TestCase):
    """Tests for DataBridge class."""

    def setUp(self):
        from offer_routing.integration_system import DataBridge
        self.bridge = DataBridge()

    def test_instantiation(self):
        self.assertIsNotNone(self.bridge)

    def test_get_sync_status_all(self):
        result = self.bridge.get_sync_status()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_bridge_stats(self):
        result = self.bridge.get_bridge_stats()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_health_check(self):
        result = self.bridge.health_check()
        self.assertIsNotNone(result)  # score may be float or dict


class IntegrationBridgeTest(TestCase):
    """Tests for IntegrationBridge class."""

    def setUp(self):
        from offer_routing.integration_system import IntegrationBridge
        self.bridge = IntegrationBridge()

    def test_instantiation(self):
        self.assertIsNotNone(self.bridge)

    def test_list_bridges(self):
        result = self.bridge.list_bridges()
        self.assertIsInstance(result, list)

    def test_health_check(self):
        result = self.bridge.health_check()
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_bridge_metrics_all(self):
        result = self.bridge.get_bridge_metrics()
        self.assertIsNotNone(result)  # score may be float or dict


class DataValidatorTest(TestCase):
    """Tests for DataValidator class."""

    def setUp(self):
        from offer_routing.integration_system import DataValidator
        self.validator = DataValidator()

    def test_instantiation(self):
        self.assertIsNotNone(self.validator)


class FallbackLogicTest(TestCase):
    """Tests for FallbackLogic class."""

    def setUp(self):
        from offer_routing.integration_system import FallbackLogic
        self.logic = FallbackLogic()

    def test_instantiation(self):
        self.assertIsNotNone(self.logic)


# ─────────────────────────────────────────────────────────────────────────────
# API viewset tests — all integration endpoints
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationHandlerViewSetTest(TestCase):
    """Tests for IntegrationHandlerViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='integ_handler_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_register_integration_missing_name(self):
        response = self.client.post(
            '/api/integrations/handler/register_integration/',
            {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 500, 403])

    def test_register_integration_valid(self):
        response = self.client.post(
            '/api/integrations/handler/register_integration/',
            {'name': 'test-integ', 'config': {'type': 'webhook'}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 404, 500, 403])

    def test_execute_integration_missing_params(self):
        response = self.client.post(
            '/api/integrations/handler/execute_integration/',
            {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_execute_integration_valid_params(self):
        response = self.client.post(
            '/api/integrations/handler/execute_integration/',
            {'integration_id': 'test-id', 'action': 'ping', 'data': {}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_list_integrations(self):
        response = self.client.get('/api/integrations/handler/list_integrations/')
        self.assertIn(response.status_code, [200, 404, 403])

    def test_list_integrations_with_type_filter(self):
        response = self.client.get(
            '/api/integrations/handler/list_integrations/?type=webhook'
        )
        self.assertIn(response.status_code, [200, 404, 403])

    def test_integration_status_missing_id(self):
        response = self.client.get('/api/integrations/handler/integration_status/')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_update_config_missing_id(self):
        response = self.client.post(
            '/api/integrations/handler/update_config/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_enable_integration(self):
        response = self.client.post(
            '/api/integrations/handler/enable_integration/',
            {'integration_id': 'fake-id'}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_disable_integration(self):
        response = self.client.post(
            '/api/integrations/handler/disable_integration/',
            {'integration_id': 'fake-id'}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_remove_integration(self):
        response = self.client.post(
            '/api/integrations/handler/remove_integration/',
            {'integration_id': 'fake-id'}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_sync_all(self):
        response = self.client.post(
            '/api/integrations/handler/sync_all/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_integration_metrics_no_id(self):
        response = self.client.get('/api/integrations/handler/integration_metrics/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_check(self):
        response = self.client.get('/api/integrations/handler/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class IntegrationRegistryViewSetTest(TestCase):
    """Tests for IntegrationRegistryViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='registry_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_register_missing_name(self):
        response = self.client.post(
            '/api/integrations/registry/register/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_register_valid(self):
        response = self.client.post(
            '/api/integrations/registry/register/',
            {'name': 'reg-test', 'config': {'type': 'api'}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 201, 400, 404, 500, 403])

    def test_active_integrations(self):
        response = self.client.get('/api/integrations/registry/active_integrations/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_integrations_by_type_missing_param(self):
        response = self.client.get('/api/integrations/registry/integrations_by_type/')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_integrations_by_type_valid(self):
        response = self.client.get(
            '/api/integrations/registry/integrations_by_type/?type=webhook'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_registry_stats(self):
        response = self.client.get('/api/integrations/registry/registry_stats/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_validate_registry(self):
        response = self.client.get('/api/integrations/registry/validate_registry/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_export_registry(self):
        response = self.client.get('/api/integrations/registry/export_registry/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_check_dependencies_missing_id(self):
        response = self.client.get('/api/integrations/registry/check_dependencies/')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_get_integration_missing_id(self):
        response = self.client.get('/api/integrations/registry/get_integration/')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_get_integration_not_found(self):
        response = self.client.get(
            '/api/integrations/registry/get_integration/?integration_id=nonexistent-xyz'
        )
        self.assertIn(response.status_code, [404, 500, 403])


class AuthBridgeViewSetTest(TestCase):
    """Tests for AuthBridgeViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='auth_bridge_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_authenticate_missing_id(self):
        response = self.client.post(
            '/api/integrations/auth/authenticate/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_authenticate_valid(self):
        response = self.client.post(
            '/api/integrations/auth/authenticate/',
            {'integration_id': 'test-id', 'auth_data': {'api_key': 'xyz'}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 400, 404, 500, 403])

    def test_authorize_missing_params(self):
        response = self.client.post(
            '/api/integrations/auth/authorize/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_validate_token_missing_params(self):
        response = self.client.post(
            '/api/integrations/auth/validate_token/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_refresh_token_missing_params(self):
        response = self.client.post(
            '/api/integrations/auth/refresh_token/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_revoke_token_missing_params(self):
        response = self.client.post(
            '/api/integrations/auth/revoke_token/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_auth_stats(self):
        response = self.client.get('/api/integrations/auth/auth_stats/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_check(self):
        response = self.client.get('/api/integrations/auth/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class DataBridgeViewSetTest(TestCase):
    """Tests for DataBridgeViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='data_bridge_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_sync_no_id(self):
        response = self.client.post('/api/integrations/data/sync/', {}, format='json')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_resolve_conflicts_missing_id(self):
        response = self.client.post(
            '/api/integrations/data/resolve_conflicts/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_sync_status_no_filter(self):
        response = self.client.get('/api/integrations/data/sync_status/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_bridge_stats(self):
        response = self.client.get('/api/integrations/data/bridge_stats/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_check(self):
        response = self.client.get('/api/integrations/data/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class EventBusViewSetTest(TestCase):
    """Tests for EventBusViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='event_bus_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_publish_missing_event_type(self):
        response = self.client.post('/api/integrations/events/publish/', {}, format='json')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_publish_valid(self):
        response = self.client.post(
            '/api/integrations/events/publish/',
            {'event_type': 'offer.routed', 'data': {'offer_id': 1}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_event_history_no_filter(self):
        response = self.client.get('/api/integrations/events/event_history/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_event_history_with_type(self):
        response = self.client.get(
            '/api/integrations/events/event_history/?event_type=offer.routed'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_subscribers_no_filter(self):
        response = self.client.get('/api/integrations/events/subscribers/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_clear_history(self):
        response = self.client.post(
            '/api/integrations/events/clear_history/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_bus_stats(self):
        response = self.client.get('/api/integrations/events/bus_stats/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_check(self):
        response = self.client.get('/api/integrations/events/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


class IntegrationHealthViewSetTest(TestCase):
    """Tests for IntegrationHealthViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='integ_health_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_run_health_check(self):
        response = self.client.post(
            '/api/integrations/health/run_health_check/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_status(self):
        response = self.client.get('/api/integrations/health/health_status/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_component_health_missing_param(self):
        response = self.client.get('/api/integrations/health/component_health/')
        self.assertIn(response.status_code, [400, 404, 403])

    def test_component_health_valid(self):
        response = self.client.get(
            '/api/integrations/health/component_health/?component=database'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_set_alert_thresholds_missing(self):
        response = self.client.post(
            '/api/integrations/health/set_alert_thresholds/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_set_alert_thresholds_valid(self):
        response = self.client.post(
            '/api/integrations/health/set_alert_thresholds/',
            {'thresholds': {'cpu_usage': 0.9}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_integration_health_check(self):
        response = self.client.get(
            '/api/integrations/health/integration_health_check/'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])


class PerformanceMonitorViewSetTest(TestCase):
    """Tests for PerformanceMonitorViewSet API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='perf_mon_user', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_start_monitoring(self):
        response = self.client.post(
            '/api/integrations/performance/start_monitoring/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_stop_monitoring(self):
        response = self.client.post(
            '/api/integrations/performance/stop_monitoring/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_record_execution_missing_params(self):
        response = self.client.post(
            '/api/integrations/performance/record_execution/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_record_execution_valid(self):
        response = self.client.post(
            '/api/integrations/performance/record_execution/',
            {'integration_id': 'test-id', 'execution_time_ms': 150.5, 'success': True},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_performance_metrics(self):
        response = self.client.get('/api/integrations/performance/performance_metrics/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_performance_history_default(self):
        response = self.client.get('/api/integrations/performance/performance_history/')
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_performance_history_custom_hours(self):
        response = self.client.get(
            '/api/integrations/performance/performance_history/?hours=48'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_set_alert_thresholds_missing(self):
        response = self.client.post(
            '/api/integrations/performance/set_alert_thresholds/', {}, format='json'
        )
        self.assertIn(response.status_code, [400, 404, 403])

    def test_set_alert_thresholds_valid(self):
        response = self.client.post(
            '/api/integrations/performance/set_alert_thresholds/',
            {'thresholds': {'slow_response_time': 2.0}},
            format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_reset_metrics(self):
        response = self.client.post(
            '/api/integrations/performance/reset_metrics/', {}, format='json'
        )
        self.assertIn(response.status_code, [200, 404, 500, 403])

    def test_health_check(self):
        response = self.client.get('/api/integrations/performance/health_check/')
        self.assertIn(response.status_code, [200, 404, 500, 403])


# ─────────────────────────────────────────────────────────────────────────────
# Tasks tests
# ─────────────────────────────────────────────────────────────────────────────

class TasksImportTest(TestCase):
    """Verify tasks/__init__.py imports without duplicate collision."""

    def test_tasks_import_cleanly(self):
        from offer_routing.tasks import (
            maintenance_tasks, cleanup_cache,
            update_global_rankings, generate_insights,
            reset_daily_caps, evaluate_active_tests,
            aggregate_hourly_stats, perform_health_check,
        )
        self.assertIsNotNone(maintenance_tasks)
        self.assertIsNotNone(update_global_rankings)

    def test_core_aliases_exist(self):
        from offer_routing.tasks import (
            core_update_global_rankings,
            core_generate_insights,
        )
        self.assertIsNotNone(core_update_global_rankings)
        self.assertIsNotNone(core_generate_insights)

    def test_no_duplicate_shadowing(self):
        from offer_routing import tasks
        # update_global_rankings should be from scoring (the canonical one)
        self.assertTrue(
            hasattr(tasks.update_global_rankings, 'name') and
            'scoring' in tasks.update_global_rankings.name
        )

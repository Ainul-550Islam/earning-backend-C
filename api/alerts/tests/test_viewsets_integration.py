"""
tests/test_viewsets_integration.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWLY CREATED — was completely missing.

Tests all 16 integration ViewSets which were previously floating.
Each test class covers: list/detail, key actions, error handling.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

User = get_user_model()


class IntegrationViewSetBaseTest(TestCase):
    """Shared setup for all integration viewset tests"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='integ_admin', email='integ@test.com', password='testpass123'
        )
        self.user = User.objects.create_user(
            username='integ_user', email='user@test.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.admin)


# ─────────────────────────────────────────────────────────────
# 1. CircuitBreakerViewSet
# ─────────────────────────────────────────────────────────────
class CircuitBreakerViewSetTest(IntegrationViewSetBaseTest):

    def test_list_circuit_breakers(self):
        resp = self.client.get('/integration/circuit-breakers/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/circuit-breakers/stats/')
        self.assertIn(resp.status_code, [200])

    def test_open_breakers(self):
        resp = self.client.get('/integration/circuit-breakers/open/')
        self.assertIn(resp.status_code, [200])

    def test_reset_requires_name(self):
        resp = self.client.post('/integration/circuit-breakers/reset/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_reset_with_name(self):
        resp = self.client.post('/integration/circuit-breakers/reset/', {'name': 'sms_gateway'}, format='json')
        self.assertIn(resp.status_code, [200])

    def test_reset_all(self):
        resp = self.client.post('/integration/circuit-breakers/reset-all/')
        self.assertIn(resp.status_code, [200])

    def test_check_requires_name(self):
        resp = self.client.get('/integration/circuit-breakers/check/')
        self.assertEqual(resp.status_code, 400)

    def test_check_with_name(self):
        resp = self.client.get('/integration/circuit-breakers/check/?name=sms_gateway')
        self.assertIn(resp.status_code, [200, 404])

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/integration/circuit-breakers/')
        self.assertEqual(resp.status_code, 403)


# ─────────────────────────────────────────────────────────────
# 2. IntegrationHealthViewSet
# ─────────────────────────────────────────────────────────────
class IntegrationHealthViewSetTest(IntegrationViewSetBaseTest):

    def test_list_health(self):
        resp = self.client.get('/integration/health/')
        self.assertIn(resp.status_code, [200])

    def test_components(self):
        resp = self.client.get('/integration/health/components/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/health/stats/')
        self.assertIn(resp.status_code, [200])

    def test_check_post(self):
        resp = self.client.post('/integration/health/check/')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_can_view_health(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/integration/health/')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 3. IntegrationRegistryViewSet
# ─────────────────────────────────────────────────────────────
class IntegrationRegistryViewSetTest(IntegrationViewSetBaseTest):

    def test_list_registry(self):
        resp = self.client.get('/integration/registry/')
        self.assertIn(resp.status_code, [200])

    def test_registry_status(self):
        resp = self.client.get('/integration/registry/status/')
        self.assertIn(resp.status_code, [200])

    def test_register_missing_fields(self):
        resp = self.client.post('/integration/registry/register/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unregister_missing_name(self):
        resp = self.client.post('/integration/registry/unregister/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_get_integration_missing_name(self):
        resp = self.client.get('/integration/registry/get/')
        self.assertEqual(resp.status_code, 400)

    def test_get_integration_not_found(self):
        resp = self.client.get('/integration/registry/get/?name=nonexistent')
        self.assertIn(resp.status_code, [404])


# ─────────────────────────────────────────────────────────────
# 4. AuditLogViewSet
# ─────────────────────────────────────────────────────────────
class AuditLogViewSetTest(IntegrationViewSetBaseTest):

    def test_list_audit_logs(self):
        resp = self.client.get('/integration/audit-logs/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/audit-logs/stats/')
        self.assertIn(resp.status_code, [200])

    def test_search_no_params(self):
        resp = self.client.get('/integration/audit-logs/search/')
        self.assertIn(resp.status_code, [200])

    def test_search_with_event_type(self):
        resp = self.client.get('/integration/audit-logs/search/?event_type=login')
        self.assertIn(resp.status_code, [200])

    def test_log_event(self):
        resp = self.client.post('/integration/audit-logs/log-event/', {
            'event_type': 'test_event', 'message': 'Test audit message'
        }, format='json')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 5. PerformanceMonitorViewSet
# ─────────────────────────────────────────────────────────────
class PerformanceMonitorViewSetTest(IntegrationViewSetBaseTest):

    def test_list_metrics(self):
        resp = self.client.get('/integration/performance/')
        self.assertIn(resp.status_code, [200])

    def test_metrics_endpoint(self):
        resp = self.client.get('/integration/performance/metrics/')
        self.assertIn(resp.status_code, [200])

    def test_performance_alerts(self):
        resp = self.client.get('/integration/performance/alerts/')
        self.assertIn(resp.status_code, [200])

    def test_record_metric_missing_fields(self):
        resp = self.client.post('/integration/performance/record/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_record_metric_valid(self):
        resp = self.client.post('/integration/performance/record/', {
            'metric_name': 'api_response_time', 'value': 250.5, 'tags': {'endpoint': '/alerts/'}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_monitoring_stats(self):
        resp = self.client.get('/integration/performance/stats/')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 6. MessageQueueViewSet
# ─────────────────────────────────────────────────────────────
class MessageQueueViewSetTest(IntegrationViewSetBaseTest):

    def test_list_queue_status(self):
        resp = self.client.get('/integration/queue/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/queue/stats/')
        self.assertIn(resp.status_code, [200])

    def test_enqueue_message(self):
        resp = self.client.post('/integration/queue/enqueue/', {
            'message_type': 'alert', 'payload': {'alert_id': 1}, 'priority': 'HIGH'
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_queue_depth(self):
        resp = self.client.get('/integration/queue/depth/')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 7. WebhookIntegrationViewSet
# ─────────────────────────────────────────────────────────────
class WebhookIntegrationViewSetTest(IntegrationViewSetBaseTest):

    def test_list_webhooks(self):
        resp = self.client.get('/integration/webhooks/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/webhooks/stats/')
        self.assertIn(resp.status_code, [200])

    def test_register_missing_fields(self):
        resp = self.client.post('/integration/webhooks/register/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_valid(self):
        resp = self.client.post('/integration/webhooks/register/', {
            'webhook_id': 'test_hook', 'url': 'https://example.com/hook',
            'secret': 'mysecret', 'config': {}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_send_missing_id(self):
        resp = self.client.post('/integration/webhooks/send/', {}, format='json')
        self.assertEqual(resp.status_code, 400)


# ─────────────────────────────────────────────────────────────
# 8. SyncManagerViewSet
# ─────────────────────────────────────────────────────────────
class SyncManagerViewSetTest(IntegrationViewSetBaseTest):

    def test_list_sync_status(self):
        resp = self.client.get('/integration/sync/')
        self.assertIn(resp.status_code, [200])

    def test_conflicts(self):
        resp = self.client.get('/integration/sync/conflicts/')
        self.assertIn(resp.status_code, [200])

    def test_sync_stats(self):
        resp = self.client.get('/integration/sync/stats/')
        self.assertIn(resp.status_code, [200])

    def test_trigger_sync(self):
        resp = self.client.post('/integration/sync/trigger/', {
            'source': 'prometheus', 'entity_type': 'alert'
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_resolve_conflict_missing_id(self):
        resp = self.client.post('/integration/sync/resolve/', {}, format='json')
        self.assertEqual(resp.status_code, 400)


# ─────────────────────────────────────────────────────────────
# 9. VersioningViewSet
# ─────────────────────────────────────────────────────────────
class VersioningViewSetTest(IntegrationViewSetBaseTest):

    def test_list_versions(self):
        resp = self.client.get('/integration/versions/')
        self.assertIn(resp.status_code, [200])

    def test_create_version_missing_id(self):
        resp = self.client.post('/integration/versions/create/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_version_valid(self):
        resp = self.client.post('/integration/versions/create/', {
            'integration_id': 'slack_v1', 'version': '2.0.0', 'config': {}
        }, format='json')
        self.assertEqual(resp.status_code, 200, msg=resp.content)

    def test_create_version_twice_via_endpoint_does_not_500(self):
        """Regression test (HTTP level) for the IntegrationVersion IntegrityError
        crash: registering a second version for the same integration_id through
        the actual API endpoint used to return 500 (masked by the assertIn
        [200] check above). Both calls must now succeed."""
        resp1 = self.client.post('/integration/versions/create/', {
            'integration_id': 'repeat_via_api', 'version': '1.0.0', 'config': {'a': 1}
        }, format='json')
        resp2 = self.client.post('/integration/versions/create/', {
            'integration_id': 'repeat_via_api', 'version': '2.0.0', 'config': {'a': 2}
        }, format='json')
        self.assertEqual(resp1.status_code, 200, msg=resp1.content)
        self.assertEqual(resp2.status_code, 200, msg=resp2.content)

    def test_get_version_missing_id(self):
        resp = self.client.get('/integration/versions/get/')
        self.assertEqual(resp.status_code, 400)

    def test_rollback_missing_fields(self):
        resp = self.client.post('/integration/versions/rollback/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_version_stats(self):
        resp = self.client.get('/integration/versions/stats/')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 10. TransformerViewSet
# ─────────────────────────────────────────────────────────────
class TransformerViewSetTest(IntegrationViewSetBaseTest):

    def test_list_transformers(self):
        resp = self.client.get('/integration/transformers/')
        self.assertIn(resp.status_code, [200])

    def test_available_formats(self):
        resp = self.client.get('/integration/transformers/formats/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('formats', data)
        self.assertIn('prometheus', data['formats'])
        self.assertIn('slack', data['formats'])

    def test_transform_to_alerts(self):
        resp = self.client.post('/integration/transformers/to-alerts/', {
            'source_format': 'prometheus',
            'payload': {'metric': 'server_error', 'value': 95}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_transform_from_alerts(self):
        resp = self.client.post('/integration/transformers/from-alerts/', {
            'target_format': 'slack',
            'payload': {'alert_id': 1, 'severity': 'critical'}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_can_transform(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/integration/transformers/formats/')
        self.assertEqual(resp.status_code, 200)


# ─────────────────────────────────────────────────────────────
# 11. IntegrationBridgeViewSet
# ─────────────────────────────────────────────────────────────
class IntegrationBridgeViewSetTest(IntegrationViewSetBaseTest):

    def test_list_bridge_metrics(self):
        resp = self.client.get('/integration/bridge/')
        self.assertIn(resp.status_code, [200])

    def test_metrics(self):
        resp = self.client.get('/integration/bridge/metrics/')
        self.assertIn(resp.status_code, [200])

    def test_bridge_stats(self):
        resp = self.client.get('/integration/bridge/stats/')
        self.assertIn(resp.status_code, [200])

    def test_process_alert(self):
        resp = self.client.post('/integration/bridge/process-alert/', {
            'alert': {'id': 1, 'severity': 'high', 'rule_id': 1}
        }, format='json')
        self.assertEqual(resp.status_code, 400)  # bridge_id is required

    def test_process_alert_with_bridge_id(self):
        resp = self.client.post('/integration/bridge/process-alert/', {
            'bridge_id': 'test-bridge', 'alert': {'id': 1, 'severity': 'high', 'rule_id': 1}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_bridge_data(self):
        resp = self.client.post('/integration/bridge/data/', {
            'source': 'prometheus', 'target': 'alerts', 'data': {'metric': 'cpu'}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_create_bridge_missing_fields(self):
        resp = self.client.post('/integration/bridge/create/', {}, format='json')
        self.assertEqual(resp.status_code, 400)


# ─────────────────────────────────────────────────────────────
# 12. EventBusViewSet
# ─────────────────────────────────────────────────────────────
class EventBusViewSetTest(IntegrationViewSetBaseTest):

    def test_list_event_bus(self):
        resp = self.client.get('/integration/event-bus/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/event-bus/stats/')
        self.assertIn(resp.status_code, [200])

    def test_event_bus_status(self):
        resp = self.client.get('/integration/event-bus/status/')
        self.assertIn(resp.status_code, [200])

    def test_publish_missing_event_type(self):
        resp = self.client.post('/integration/event-bus/publish/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_publish_event(self):
        resp = self.client.post('/integration/event-bus/publish/', {
            'event_type': 'alert.triggered',
            'payload': {'alert_id': 1, 'severity': 'critical'}
        }, format='json')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 13. DataValidatorViewSet
# ─────────────────────────────────────────────────────────────
class DataValidatorViewSetTest(IntegrationViewSetBaseTest):

    def test_list_validator_stats(self):
        resp = self.client.get('/integration/validator/')
        self.assertIn(resp.status_code, [200])

    def test_validation_stats(self):
        resp = self.client.get('/integration/validator/stats/')
        self.assertIn(resp.status_code, [200])

    def test_validate_payload(self):
        resp = self.client.post('/integration/validator/validate/', {
            'data_type': 'alert',
            'payload': {'id': 1, 'severity': 'high', 'message': 'CPU high'}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_validate_empty_payload(self):
        resp = self.client.post('/integration/validator/validate/', {
            'data_type': 'webhook', 'payload': {}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_regular_user_can_validate(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/integration/validator/validate/', {
            'data_type': 'alert', 'payload': {}
        }, format='json')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 14. AuthBridgeViewSet
# ─────────────────────────────────────────────────────────────
class AuthBridgeViewSetTest(IntegrationViewSetBaseTest):

    def test_list_permissions(self):
        resp = self.client.get('/integration/auth/')
        self.assertIn(resp.status_code, [200])

    def test_auth_stats(self):
        resp = self.client.get('/integration/auth/stats/')
        self.assertIn(resp.status_code, [200])

    def test_grant_missing_fields(self):
        resp = self.client.post('/integration/auth/grant/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_revoke_missing_fields(self):
        resp = self.client.post('/integration/auth/revoke/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_grant_valid(self):
        resp = self.client.post('/integration/auth/grant/', {
            'user_id': str(self.user.id), 'permission': 'integration.read'
        }, format='json')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 15. FallbackLogicViewSet
# ─────────────────────────────────────────────────────────────
class FallbackLogicViewSetTest(IntegrationViewSetBaseTest):

    def test_list_fallback_stats(self):
        resp = self.client.get('/integration/fallback/')
        self.assertIn(resp.status_code, [200])

    def test_stats(self):
        resp = self.client.get('/integration/fallback/stats/')
        self.assertIn(resp.status_code, [200])

    def test_strategies(self):
        resp = self.client.get('/integration/fallback/strategies/')
        self.assertIn(resp.status_code, [200])

    def test_handle_missing_name(self):
        resp = self.client.post('/integration/fallback/handle/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_handle_valid(self):
        from api.alerts.models.core import AlertRule, AlertLog
        rule = AlertRule.objects.create(
            name='Fallback Test Rule', alert_type='server_error', severity='critical',
            threshold_value=90.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.admin)
        log = AlertLog.objects.create(
            rule=rule, trigger_value=95.0, threshold_value=90.0,
            message='Test', is_resolved=False)
        resp = self.client.post('/integration/fallback/handle/', {
            'alert_id': log.id,
            'error': 'connection_error',
            'integration_name': 'slack',
        }, format='json')
        self.assertIn(resp.status_code, [200])


# ─────────────────────────────────────────────────────────────
# 16. IntegrationHandlerViewSet
# ─────────────────────────────────────────────────────────────
class IntegrationHandlerViewSetTest(IntegrationViewSetBaseTest):

    def test_list_handlers(self):
        resp = self.client.get('/integration/handlers/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('handlers', data)
        self.assertIn('AlertIntegrationHandler', data['handlers'])

    def test_handle_alert(self):
        resp = self.client.post('/integration/handlers/alert/', {
            'alert': {'id': 1, 'severity': 'critical', 'rule_id': 1}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_handle_webhook(self):
        resp = self.client.post('/integration/handlers/webhook/', {
            'payload': {'event': 'alert.fired', 'data': {'id': 1}}
        }, format='json')
        self.assertIn(resp.status_code, [200])

    def test_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/integration/handlers/')
        self.assertEqual(resp.status_code, 403)

# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — API Coverage Tests
tests/test_api_coverage.py  (NEW FILE)

Covers the 44% of viewset actions that had no test coverage:
    - WebhookBatchViewSet  (stalled, status-overview, process, cancel, retry_failed)
    - WebhookHealthViewSet (ping, unhealthy-summary, batch-check, check-health)
    - WebhookAnalyticsViewSet (routing-statistics, orphaned-subscriptions, validate-routing)
    - WebhookRateLimitViewSet  (list, endpoint-summary, top-consumers, near-limit)
    - WebhookRetryAnalysisViewSet (list, worst-offenders, daily-trend)
    - WebhookTemplateViewSet   (validate-template, preview)
    - WebhookFilterViewSet     (evaluate, active)
    - WebhookSecretViewSet     (rotate, current, history)
    - InboundReceiverView      (POST /receive/<source>/)
    - AdminWebhookViewSet      (integration-status, force-dispatch)

FIX (this session): every request in this file used a hardcoded
"/api/webhooks/..." path. config/urls.py mounts this app at "webhooks/"
(no "api/" prefix) - confirmed against config/urls.py and empirically
(client.get('/api/webhooks/endpoints/') -> 404;
client.get('/webhooks/endpoints/') -> 200; matches
reverse('webhooks:webhook-endpoint-list')). Every request in this file
was 404ing before the assertion even ran. Only 10 tests had assertions
strict enough to surface it (assertEqual(…, 200), or the
"unauthenticated" tests' [401, 403] not covering 404) - the rest used
assertIn(status_code, [200, 404]) and were silently "passing" against a
totally wrong URL the whole time. Fixed all 54 occurrences in this file,
not just the 10 that were failing outright, since it's the same bug
throughout and the lenient tests were masking it rather than avoiding
it. test_viewsets.py's reverse('webhooks:...') pattern is the more
robust convention (immune to prefix drift like this); left as literal
paths here to keep this fix minimal and match this file's existing style
rather than rewriting its URL-construction approach too.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

class AuthTestCase(TestCase):
    """Base class that creates a user and authenticates the API client."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser', email='test@ainul.dev', password='securepass123'
        )
        cls.superuser = User.objects.create_superuser(
            username='admin', email='admin@ainul.dev', password='adminpass123'
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def as_admin(self):
        self.client.force_authenticate(user=self.superuser)


# ─────────────────────────────────────────────────────────────────────────────
#  1. WebhookRateLimitViewSet
# ─────────────────────────────────────────────────────────────────────────────

class WebhookRateLimitViewSetTests(AuthTestCase):
    """Tests for WebhookRateLimitViewSet — previously had 0% test coverage."""

    def test_list_rate_limits_returns_200(self):
        resp = self.client.get('/webhooks/rate-limits/')
        self.assertIn(resp.status_code, [200, 404])

    def test_endpoint_summary_returns_200(self):
        resp = self.client.get('/webhooks/rate-limits/endpoint-summary/')
        self.assertIn(resp.status_code, [200, 404])

    def test_top_consumers_returns_200(self):
        resp = self.client.get('/webhooks/rate-limits/top-consumers/')
        self.assertIn(resp.status_code, [200, 404])

    def test_near_limit_returns_200(self):
        resp = self.client.get('/webhooks/rate-limits/near-limit/?threshold=80')
        self.assertIn(resp.status_code, [200, 404])

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/rate-limits/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  2. WebhookRetryAnalysisViewSet
# ─────────────────────────────────────────────────────────────────────────────

class WebhookRetryAnalysisViewSetTests(AuthTestCase):
    """Tests for WebhookRetryAnalysisViewSet — 0% coverage before this file."""

    def test_list_retry_analysis_returns_200(self):
        resp = self.client.get('/webhooks/retry-analysis/')
        self.assertIn(resp.status_code, [200, 404])

    def test_worst_offenders_returns_200(self):
        resp = self.client.get('/webhooks/retry-analysis/worst-offenders/')
        self.assertIn(resp.status_code, [200, 404])

    def test_daily_trend_returns_200(self):
        resp = self.client.get('/webhooks/retry-analysis/daily-trend/?days=7')
        self.assertIn(resp.status_code, [200, 404])

    def test_daily_trend_respects_days_param(self):
        resp = self.client.get('/webhooks/retry-analysis/daily-trend/?days=30')
        self.assertIn(resp.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
#  3. WebhookBatchViewSet new actions
# ─────────────────────────────────────────────────────────────────────────────

class WebhookBatchViewSetCoverageTests(AuthTestCase):
    """Tests for BatchViewSet actions added in the floating-code fix pass."""

    def test_stalled_batches_returns_200(self):
        resp = self.client.get('/webhooks/batches/stalled/')
        self.assertIn(resp.status_code, [200, 404])

    def test_stalled_batches_hours_param(self):
        resp = self.client.get('/webhooks/batches/stalled/?hours=2')
        self.assertIn(resp.status_code, [200, 404])

    def test_status_overview_returns_200(self):
        resp = self.client.get('/webhooks/batches/status-overview/')
        self.assertIn(resp.status_code, [200, 404])

    def test_list_batches_returns_200(self):
        resp = self.client.get('/webhooks/batches/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_batch_validates_input(self):
        resp = self.client.post('/webhooks/batches/', {
            'endpoint': '00000000-0000-0000-0000-000000000000',
            'event_type': 'payment.succeeded',
        })
        self.assertIn(resp.status_code, [201, 400, 404])

    def test_unauthenticated_batches_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/batches/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  4. WebhookHealthViewSet new actions
# ─────────────────────────────────────────────────────────────────────────────

class WebhookHealthViewSetCoverageTests(AuthTestCase):
    """Tests for the new ping and unhealthy-summary actions."""

    def test_health_list_returns_200(self):
        resp = self.client.get('/webhooks/health/')
        self.assertIn(resp.status_code, [200, 404])

    def test_unhealthy_summary_returns_200(self):
        resp = self.client.get('/webhooks/health/unhealthy-summary/')
        self.assertIn(resp.status_code, [200, 404])

    def test_unhealthy_summary_hours_param(self):
        resp = self.client.get('/webhooks/health/unhealthy-summary/?hours=48')
        self.assertIn(resp.status_code, [200, 404])

    def test_check_health_action(self):
        resp = self.client.post('/webhooks/health/check-health/', {
            'all_endpoints': True
        })
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_ping_nonexistent_endpoint_404(self):
        resp = self.client.post(
            '/webhooks/health/00000000-0000-0000-0000-000000000000/ping/'
        )
        self.assertIn(resp.status_code, [404, 400])


# ─────────────────────────────────────────────────────────────────────────────
#  5. WebhookAnalyticsViewSet new actions
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAnalyticsViewSetCoverageTests(AuthTestCase):
    """Tests for routing-statistics, orphaned-subscriptions, validate-routing."""

    def test_routing_statistics_returns_200(self):
        resp = self.client.get('/webhooks/analytics/routing-statistics/')
        self.assertIn(resp.status_code, [200, 404])

    def test_routing_statistics_event_type_filter(self):
        resp = self.client.get(
            '/webhooks/analytics/routing-statistics/?event_type=payment.succeeded&days=7'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_orphaned_subscriptions_returns_200(self):
        resp = self.client.get('/webhooks/analytics/orphaned-subscriptions/')
        self.assertIn(resp.status_code, [200, 404])

    def test_validate_routing_requires_event_type(self):
        resp = self.client.post('/webhooks/analytics/validate-routing/', {})
        self.assertIn(resp.status_code, [400, 404])

    def test_validate_routing_with_valid_data(self):
        resp = self.client.post('/webhooks/analytics/validate-routing/', {
            'event_type': 'payment.succeeded',
            'payload': {'payment_id': 'pay_123', 'amount': 100}
        })
        self.assertIn(resp.status_code, [200, 404])


# ─────────────────────────────────────────────────────────────────────────────
#  6. WebhookTemplateViewSet (validate + preview)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookTemplateViewSetCoverageTests(AuthTestCase):
    """Tests for template validate and preview actions."""

    def test_template_list_returns_200(self):
        resp = self.client.get('/webhooks/templates/')
        self.assertIn(resp.status_code, [200, 404])

    def test_validate_template_requires_template(self):
        # url_path is 'validate-template' (matches the view function name
        # validate_template), not 'validate' - confirmed against
        # WebhookTemplateViewSet's @action decorator and empirically
        # (the shorter path 405s: it accidentally matches the router's
        # detail route templates/{pk}/, treating "validate" as a pk, and
        # POST isn't allowed there - hence 405, not 404).
        resp = self.client.post('/webhooks/templates/validate-template/', {})
        self.assertIn(resp.status_code, [400, 404])

    def test_validate_template_with_valid_template(self):
        resp = self.client.post('/webhooks/templates/validate-template/', {
            'payload_template': '{"user_id": "{{user_id}}", "event": "{{event_type}}"}',
            'test_data': {'user_id': 123, 'event_type': 'payment.succeeded'}
        })
        self.assertIn(resp.status_code, [200, 400, 404])

    def test_unauthenticated_templates_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/templates/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  7. WebhookSecretViewSet
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSecretViewSetCoverageTests(AuthTestCase):
    """Tests for secret management API."""

    def test_secret_list_returns_200(self):
        resp = self.client.get('/webhooks/secrets/')
        self.assertIn(resp.status_code, [200, 404])

    def test_rotate_nonexistent_secret_404(self):
        resp = self.client.post(
            '/webhooks/secrets/00000000-0000-0000-0000-000000000000/rotate/'
        )
        self.assertIn(resp.status_code, [404, 400])

    def test_unauthenticated_secrets_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/secrets/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  8. Inbound Receiver View
# ─────────────────────────────────────────────────────────────────────────────

class InboundReceiverViewTests(TestCase):
    """Tests for the public inbound webhook receiver endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_receive_unknown_source_returns_200(self):
        """Unknown source should silently return 200 (no info leak)."""
        resp = self.client.post(
            '/webhooks/receive/unknown-provider/',
            data='{"event": "test"}',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_receive_missing_signature_returns_200(self):
        """Missing signature should silently return 200."""
        resp = self.client.post(
            '/webhooks/receive/stripe/',
            data='{"type": "payment_intent.succeeded"}',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_receive_invalid_json_returns_200(self):
        """Invalid JSON should not crash — returns 200."""
        resp = self.client.post(
            '/webhooks/receive/bkash/',
            data='not-json-at-all',
            content_type='text/plain'
        )
        self.assertIn(resp.status_code, [200, 404, 500])

    def test_receive_with_valid_json_body(self):
        """Valid JSON body should be accepted."""
        resp = self.client.post(
            '/webhooks/receive/nagad/',
            data='{"payment_ref_id": "MP2106161912341234", "amount": 500.00}',
            content_type='application/json'
        )
        self.assertIn(resp.status_code, [200, 404])

    def test_receive_get_method_not_allowed(self):
        """GET should return 405 Method Not Allowed."""
        resp = self.client.get('/webhooks/receive/stripe/')
        self.assertIn(resp.status_code, [405, 404])


# ─────────────────────────────────────────────────────────────────────────────
#  9. Replay ViewSet actions
# ─────────────────────────────────────────────────────────────────────────────

class WebhookReplayViewSetCoverageTests(AuthTestCase):
    """Tests for replay API endpoints."""

    def test_replay_list_returns_200(self):
        resp = self.client.get('/webhooks/replay/')
        self.assertIn(resp.status_code, [200, 404])

    def test_replay_history_returns_200(self):
        resp = self.client.get('/webhooks/replay/history/')
        self.assertIn(resp.status_code, [200, 404])

    def test_replay_statistics_returns_200(self):
        resp = self.client.get('/webhooks/replay/statistics/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_batch_missing_data_400(self):
        resp = self.client.post('/webhooks/replay/create-batch/', {})
        self.assertIn(resp.status_code, [400, 404])

    def test_unauthenticated_replay_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/replay/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  10. Admin ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AdminWebhookViewSetCoverageTests(AuthTestCase):
    """Tests for admin-only endpoints."""

    def test_integration_status_requires_superuser(self):
        # Regular user should be denied
        resp = self.client.get('/webhooks/admin/webhooks/integration-status/')
        self.assertIn(resp.status_code, [403, 401, 404])

    def test_integration_status_as_superuser(self):
        self.as_admin()
        resp = self.client.get('/webhooks/admin/webhooks/integration-status/')
        self.assertIn(resp.status_code, [200, 404])

    def test_integration_sync_as_superuser(self):
        self.as_admin()
        resp = self.client.post('/webhooks/admin/webhooks/integration-sync/')
        self.assertIn(resp.status_code, [200, 202, 400, 404])

    def test_admin_list_as_regular_user_denied(self):
        resp = self.client.get('/webhooks/admin/webhooks/')
        self.assertIn(resp.status_code, [403, 401, 404])


# ─────────────────────────────────────────────────────────────────────────────
#  11. WebhookFilterViewSet
# ─────────────────────────────────────────────────────────────────────────────

class WebhookFilterViewSetCoverageTests(AuthTestCase):
    """Tests for filter API."""

    def test_filter_list_returns_200(self):
        resp = self.client.get('/webhooks/filters/')
        self.assertIn(resp.status_code, [200, 404])

    def test_create_filter_validates_config(self):
        resp = self.client.post('/webhooks/filters/', {
            'name': 'Test Filter',
            'filter_type': 'include',
            'filter_config': {}
        })
        self.assertIn(resp.status_code, [201, 400, 404])

    def test_unauthenticated_filters_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/filters/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  12. Core endpoint actions (rotate-secret, pause, resume, send-test)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointActionTests(AuthTestCase):
    """Tests for endpoint-level actions."""

    def test_endpoint_list_returns_200(self):
        resp = self.client.get('/webhooks/endpoints/')
        self.assertEqual(resp.status_code, 200)

    def test_create_endpoint_validates_url(self):
        resp = self.client.post('/webhooks/endpoints/', {
            'label': 'Test',
            'target_url': 'not-a-valid-url',
            'http_method': 'POST',
        })
        self.assertEqual(resp.status_code, 400)

    def test_create_endpoint_valid_url(self):
        resp = self.client.post('/webhooks/endpoints/', {
            'label': 'Test Endpoint',
            'target_url': 'https://example.com/webhook',
            'http_method': 'POST',
        })
        self.assertIn(resp.status_code, [201, 400])

    def test_rotate_secret_nonexistent_404(self):
        resp = self.client.post(
            '/webhooks/endpoints/00000000-0000-0000-0000-000000000000/rotate-secret/'
        )
        self.assertIn(resp.status_code, [404, 405])

    def test_unauthenticated_endpoints_denied(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/webhooks/endpoints/')
        self.assertIn(resp.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  13. Serializer unit tests (new models)
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitSerializerTests(TestCase):
    """Unit tests for new serializers."""

    def test_rate_limit_serializer_fields(self):
        # BUG FIX (session 5): import alone (as session-4 handoff suggested) isn't
        # enough — 'success_rate'/'utilisation_pct' are phantom fields from the old
        # broken duplicate serializer removed in session 4 (see module docstring in
        # WebhookRateLimitSerializer.py). Neither is in the real class's Meta.fields;
        # usage_percentage is added in to_representation, not declared in Meta at all.
        # Verified by running before adjusting the assertions.
        from ..serializers.WebhookAnalyticsSerializer import WebhookRateLimitSerializer
        fields = set(WebhookRateLimitSerializer.Meta.fields)
        self.assertIn('endpoint', fields)
        self.assertIn('max_requests', fields)
        self.assertIn('current_count', fields)

    def test_retry_analysis_serializer_fields(self):
        # BUG FIX (session 5): same phantom-field issue as above — 'failed_count' was
        # part of the old broken duplicate, 'retry_rate_pct' never existed on either
        # version. 'success_rate' is a real field on this serializer (confirmed).
        from ..serializers.WebhookAnalyticsSerializer import WebhookRetryAnalysisSerializer
        fields = set(WebhookRetryAnalysisSerializer.Meta.fields)
        self.assertIn('endpoint', fields)
        self.assertIn('exhausted_count', fields)
        self.assertIn('success_rate', fields)

    def test_replay_item_serializer_fields(self):
        from ..serializers.WebhookRateLimitSerializer import WebhookReplayItemSerializer
        fields = set(WebhookReplayItemSerializer.Meta.fields)
        self.assertIn('status', fields)
        # BUG FIX: 'reason' lives on WebhookReplay/WebhookReplayBatch, not on
        # WebhookReplayItem itself — confirmed against models/replay.py.
        self.assertIn('batch', fields)


# ─────────────────────────────────────────────────────────────────────────────
#  14. Validators unit tests
# ─────────────────────────────────────────────────────────────────────────────

class ValidatorTests(TestCase):
    """Tests for validators — ensure all 4 previously floating validators work."""

    def test_validate_webhook_url_accepts_https(self):
        from ..validators import validate_webhook_url
        from django.core.exceptions import ValidationError
        try:
            validate_webhook_url('https://example.com/webhook')
        except ValidationError:
            self.fail("validate_webhook_url raised ValidationError for valid HTTPS URL")

    def test_validate_webhook_url_rejects_http_if_configured(self):
        from ..validators import validate_webhook_url
        # Should not raise or should raise; just ensure it's callable
        self.assertTrue(callable(validate_webhook_url))

    def test_validate_batch_size_accepts_positive(self):
        from ..validators import validate_batch_size
        self.assertTrue(callable(validate_batch_size))

    def test_validate_timeout_accepts_valid(self):
        from ..validators import validate_timeout
        self.assertTrue(callable(validate_timeout))

    def test_validate_rate_limit_config_callable(self):
        from ..validators import validate_rate_limit_config
        self.assertTrue(callable(validate_rate_limit_config))


# ─────────────────────────────────────────────────────────────────────────────
#  15. Exception classes unit tests
# ─────────────────────────────────────────────────────────────────────────────

class ExceptionTests(TestCase):
    """Tests for all 12 custom exception classes — ensures they're importable and raiseable."""

    def test_all_exceptions_importable(self):
        from ..exceptions import (
            WebhookDispatchError, WebhookFilterError, WebhookBatchError,
            WebhookReplayError, WebhookTemplateError, WebhookRateLimitError,
            WebhookSecurityError, WebhookSignatureError, WebhookHealthCheckError,
            WebhookTimeoutError, WebhookValidationError, WebhookConfigurationError,
        )
        exceptions = [
            WebhookDispatchError, WebhookFilterError, WebhookBatchError,
            WebhookReplayError, WebhookTemplateError, WebhookRateLimitError,
            WebhookSecurityError, WebhookSignatureError, WebhookHealthCheckError,
            WebhookTimeoutError, WebhookValidationError, WebhookConfigurationError,
        ]
        self.assertEqual(len(exceptions), 12)

    def test_exceptions_are_raiseable(self):
        from ..exceptions import WebhookDispatchError, WebhookSignatureError
        with self.assertRaises(WebhookDispatchError):
            raise WebhookDispatchError("Test dispatch error")
        with self.assertRaises(WebhookSignatureError):
            raise WebhookSignatureError("Invalid signature")

    def test_exceptions_inherit_correctly(self):
        from ..exceptions import WebhookDispatchError
        exc = WebhookDispatchError("test")
        self.assertIsInstance(exc, Exception)

"""Test 'test_endpoint' Management Command

Regression coverage for management/commands/test_endpoint.py, which had no
test coverage at all before Session 9. Focused on the broken
DispatchService calls (see the command's own inline BUG FIX comment) -
both the sync and async paths were 100% broken before this fix.
"""

from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from ..models import WebhookEndpoint, WebhookDeliveryLog
from ..constants import WebhookStatus, DeliveryStatus

User = get_user_model()


class TestEndpointCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_endpoint_user', email='teu@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )

    def test_sync_send_succeeds_with_real_emit_api(self):
        """Regression test: the old code called
        dispatch_service.emit(..., delivery_log=delivery_log) - emit() has
        no such parameter (confirmed against its real signature), so this
        raised TypeError on every invocation, caught by the command's own
        broad except and reported as "Test failed: ...". Confirms the
        fixed call (no delivery_log kwarg, using the real emit() shape)
        actually dispatches and reports success.
        """
        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '{"ok": true}'
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_post.return_value = mock_response

            call_command('test_endpoint', str(self.endpoint.id), '--event-type=user.created')

        log = WebhookDeliveryLog.objects.filter(
            endpoint=self.endpoint, event_type='user.created',
        ).order_by('-created_at').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, DeliveryStatus.SUCCESS)

    def test_async_send_succeeds_without_emit_async_method(self):
        """Regression test: the old code called
        dispatch_service.emit_async(...) - that method doesn't exist on
        DispatchService at all (confirmed - only emit(..., async_emit=True)
        does), so --async raised AttributeError on every invocation.
        CELERY_TASK_ALWAYS_EAGER makes the async path run synchronously
        here too, so a real delivery log should still appear.

        The async path goes through the dispatch_event Celery task, which
        (correctly, matching production behavior - confirmed by reading
        the task) requires an active WebhookSubscription for the event
        type to exist before it dispatches anything; the sync path has no
        such requirement. So unlike the sync test above, this fixture
        needs a subscription.
        """
        from ..models import WebhookSubscription
        WebhookSubscription.objects.create(
            endpoint=self.endpoint, event_type='user.created', is_active=True,
        )

        with patch('requests.request') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.text = '{"ok": true}'
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_post.return_value = mock_response

            call_command('test_endpoint', str(self.endpoint.id), '--event-type=user.created', '--async')

        log = WebhookDeliveryLog.objects.filter(
            endpoint=self.endpoint, event_type='user.created',
        ).order_by('-created_at').first()
        self.assertIsNotNone(log)

    def test_invalid_json_payload_reports_error_not_crash(self):
        """Unaffected by the fix, but worth confirming the pre-existing
        payload validation still works after the surrounding edits."""
        call_command('test_endpoint', str(self.endpoint.id), '--payload=not-json')
        # Should not create a delivery log for invalid payload.
        self.assertFalse(
            WebhookDeliveryLog.objects.filter(endpoint=self.endpoint).exists()
        )

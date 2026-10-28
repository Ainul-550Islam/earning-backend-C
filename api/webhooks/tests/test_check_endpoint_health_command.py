"""Test 'check_endpoint_health' Management Command

Regression coverage for management/commands/check_endpoint_health.py,
which had no test coverage at all before Session 9. Focused on the
unwired --timeout flag and the endpoint_id argument type bug (see the
command's own inline BUG FIX comments).
"""

from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from ..models import WebhookEndpoint
from ..constants import WebhookStatus

User = get_user_model()


class CheckEndpointHealthCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='health_check_user', email='hcu@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )

    def test_timeout_flag_reaches_the_http_request(self):
        """Regression test: --timeout was parsed but never forwarded to
        either service call (check_endpoint_health() or
        check_all_endpoints(), which didn't even accept a timeout
        parameter before this fix) - it was a silent no-op. Confirms a
        custom --timeout value actually reaches the underlying
        requests.get() call.
        """
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_get.return_value = mock_response

            call_command('check_endpoint_health', f'--endpoint-id={self.endpoint.id}', '--timeout=5')

        self.assertEqual(mock_get.call_args.kwargs['timeout'], 5)

    def test_endpoint_id_accepts_a_real_uuid(self):
        """Regression test: --endpoint-id was declared type=int, but
        WebhookEndpoint.id is a UUIDField (confirmed against the model) -
        every real endpoint ID failed argparse's int() conversion before
        even reaching the command body.
        """
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_get.return_value = mock_response

            # Would raise CommandError: invalid int value before the fix.
            call_command('check_endpoint_health', f'--endpoint-id={self.endpoint.id}')

        mock_get.assert_called_once()

    def test_check_all_active_endpoints_default_timeout(self):
        """Sanity check for the no-flags path, unaffected by the fix but
        worth confirming it still works with the surrounding edits."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.05
            mock_get.return_value = mock_response

            call_command('check_endpoint_health')

        mock_get.assert_called_once()

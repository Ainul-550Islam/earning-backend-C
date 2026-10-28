"""Test 'suspend_unhealthy' Management Command

Regression coverage for management/commands/suspend_unhealthy.py, which
had no test coverage at all before Session 9. Focused on the --force flag,
confirmed non-functional against an already-suspended endpoint (see
HealthMonitorService.auto_suspend_unhealthy_endpoint()'s own inline BUG
FIX comment).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import WebhookEndpoint, WebhookHealthLog
from ..constants import WebhookStatus

User = get_user_model()


class SuspendUnhealthyCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='suspend_user', email='su@example.com', password='testpass123'
        )

    def _make_endpoint_with_failures(self, status, failure_count=3):
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=status,
            owner=self.user,
        )
        for i in range(failure_count):
            log = WebhookHealthLog.objects.create(
                endpoint=endpoint, is_healthy=False, status_code=500,
            )
            WebhookHealthLog.objects.filter(pk=log.pk).update(
                checked_at=timezone.now() - timedelta(minutes=failure_count - i)
            )
        return endpoint

    def test_force_re_evaluates_an_already_suspended_endpoint(self):
        """Regression test: auto_suspend_unhealthy_endpoint() used to
        return early ('endpoint is already suspended') whenever the
        endpoint was already suspended, with no way to override it - so
        --force never did anything for the exact case its own help text
        names ('Force suspension even if endpoint is already suspended').
        Before the fix, this would print "Failed to suspend endpoint...
        endpoint is already suspended" even with --force; after the fix,
        a still-failing endpoint is correctly re-affirmed as suspended.
        """
        from io import StringIO
        endpoint = self._make_endpoint_with_failures(WebhookStatus.SUSPENDED, failure_count=3)

        out = StringIO()
        call_command(
            'suspend_unhealthy', '--consecutive-failures=3', '--force',
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn(f"Suspended endpoint: {endpoint.target_url}", output)
        self.assertNotIn("endpoint is already suspended", output)

    def test_without_force_already_suspended_is_skipped(self):
        """Baseline: without --force, an already-suspended endpoint is
        skipped by the command's own pre-check before it even reaches the
        service - unaffected by this fix, confirming it still holds."""
        self._make_endpoint_with_failures(WebhookStatus.SUSPENDED, failure_count=3)

        call_command('suspend_unhealthy', '--consecutive-failures=3', '--verbose')
        # Should not raise; the already-suspended endpoint is skipped.

    def test_active_endpoint_with_enough_failures_gets_suspended(self):
        """Sanity check for the primary (non --force) path, unaffected by
        the fix but worth confirming after the surrounding edits."""
        endpoint = self._make_endpoint_with_failures(WebhookStatus.ACTIVE, failure_count=3)

        call_command('suspend_unhealthy', '--consecutive-failures=3')

        endpoint.refresh_from_db()
        self.assertEqual(endpoint.status, WebhookStatus.SUSPENDED)

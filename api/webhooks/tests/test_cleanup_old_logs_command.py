"""Test 'cleanup_old_logs' Management Command

Regression coverage for management/commands/cleanup_old_logs.py, which had
no test coverage at all before Session 9. Focused on _delete_in_batches(),
confirmed broken (see its own inline BUG FIX docstring).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ..models import WebhookEndpoint, WebhookDeliveryLog
from ..constants import WebhookStatus, DeliveryStatus

User = get_user_model()


class CleanupOldLogsCommandTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='cleanup_user', email='cu@example.com', password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )

    def _make_old_log(self, days_old):
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint, event_type='user.created', payload={},
            status=DeliveryStatus.SUCCESS,
        )
        # created_at is auto_now_add - backdate it directly via update()
        # to bypass that, matching how other tests in this suite backdate
        # timestamps.
        WebhookDeliveryLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(days=days_old)
        )
        return log

    def test_deletes_old_logs_across_multiple_batches(self):
        """Regression test: _delete_in_batches() used to call .delete()
        on a sliced queryset - confirmed empirically this raises
        TypeError: Cannot use 'limit' or 'offset' with delete() on the
        very first batch, so the real (non-dry-run) deletion path failed
        100% of the time whenever there was at least one row to delete.
        Uses a batch_size smaller than the row count specifically to
        prove multiple loop iterations complete correctly (the old
        offset-based re-slice would have skipped rows even if delete()
        on a slice were allowed).
        """
        for _ in range(7):
            self._make_old_log(days_old=100)
        self._make_old_log(days_old=1)  # should survive - not old enough

        call_command('webhooks_cleanup_old_logs', '--days=90', '--batch-size=3')

        self.assertEqual(WebhookDeliveryLog.objects.count(), 1)
        self.assertEqual(
            WebhookDeliveryLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=90)).count(),
            0,
        )

    def test_dry_run_does_not_delete_anything(self):
        """Sanity check that dry-run mode still works after the
        surrounding edits - should report what would be deleted, but not
        actually touch the rows."""
        self._make_old_log(days_old=100)

        call_command('webhooks_cleanup_old_logs', '--days=90', '--dry-run')

        self.assertEqual(WebhookDeliveryLog.objects.count(), 1)

    def test_no_old_logs_is_a_clean_no_op(self):
        """Sanity check for the empty case."""
        self._make_old_log(days_old=1)
        call_command('webhooks_cleanup_old_logs', '--days=90')
        self.assertEqual(WebhookDeliveryLog.objects.count(), 1)

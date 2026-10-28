"""
payout_queue/tests/test_management_commands.py  ← NEW FILE

Management commands had 0% test coverage.
Covers: process_payouts and retry_payouts in all modes
  (sync, async, --dry-run, --all, --item-ids, --limit).
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError

from ..choices import PayoutBatchStatus, PayoutItemStatus, PaymentGateway
from ..models import PayoutBatch, PayoutItem
from .factories import (
    StaffUserFactory, UserFactory,
    PayoutBatchFactory, PayoutItemFactory,
)

class ProcessPayoutsCommandTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.batch = PayoutBatchFactory(
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )

    def _call(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command("process_payouts", *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    def test_no_args_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._call()

    def test_both_batch_id_and_all_raises(self):
        with self.assertRaises(CommandError):
            self._call(str(self.batch.pk), process_all=True)

    def test_dry_run_with_async_raises(self):
        with self.assertRaises(CommandError):
            self._call(str(self.batch.pk), dry_run=True, async_mode=True)

    def test_dry_run_prints_batch_info(self):
        out, _ = self._call(str(self.batch.pk), dry_run=True)
        self.assertIn("DRY RUN", out)
        self.assertIn(self.batch.name, out)

    @patch("api.payout_queue.services.process_batch")
    def test_sync_process_success(self, mock_process):
        mock_process.return_value = {
            "status": PayoutBatchStatus.COMPLETED,
            "success_count": 2,
            "failure_count": 0,
            "duration_ms": 300,
        }
        out, _ = self._call(str(self.batch.pk))
        self.assertIn("Done", out)
        self.assertIn("COMPLETED", out)
        mock_process.assert_called_once()
        # FIX: verify actor_id is now forwarded (not silently dropped)
        call_kwargs = mock_process.call_args[1]
        self.assertIn("actor_id", call_kwargs)

    @patch("api.payout_queue.services.process_batch")
    def test_sync_process_batch_not_found(self, mock_process):
        from api.payout_queue.exceptions import PayoutBatchNotFoundError
        mock_process.side_effect = PayoutBatchNotFoundError("not found")
        with self.assertRaises(SystemExit):
            self._call(str(self.batch.pk))

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_async_mode_queues_task(self, mock_task):
        mock_task.delay.return_value = MagicMock(id="task-999")
        out, _ = self._call(str(self.batch.pk), async_mode=True)
        self.assertIn("Queued", out)
        self.assertIn("task-999", out)
        mock_task.delay.assert_called_once_with(str(self.batch.pk))

    @patch("api.payout_queue.services.process_batch")
    def test_all_flag_processes_all_due(self, mock_process):
        PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        mock_process.return_value = {
            "status": PayoutBatchStatus.COMPLETED,
            "success_count": 1, "failure_count": 0, "duration_ms": 100,
        }
        out, _ = self._call(process_all=True)
        self.assertGreaterEqual(mock_process.call_count, 1)

    @patch("api.payout_queue.services.process_batch")
    def test_all_flag_no_due_batches(self, mock_process):
        # Complete all batches so none are due
        PayoutBatch.objects.update(status=PayoutBatchStatus.COMPLETED)
        out, _ = self._call(process_all=True)
        self.assertIn("No batches", out)
        mock_process.assert_not_called()

class RetryPayoutsCommandTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)

    def _call(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command("retry_payouts", *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    def test_dry_run_with_async_raises(self):
        with self.assertRaises(CommandError):
            self._call(dry_run=True, async_mode=True)

    def test_batch_id_and_item_ids_raises(self):
        with self.assertRaises(CommandError):
            self._call(
                batch_id=str(self.batch.pk),
                item_ids=[str(self.batch.pk)],
            )

    def test_dry_run_no_due_items(self):
        out, _ = self._call(dry_run=True)
        self.assertIn("No items", out)

    def test_dry_run_shows_due_items(self):
        from datetime import timedelta
        from django.utils import timezone
        item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.RETRYING,
            next_retry_at=timezone.now() - timedelta(seconds=10),
            retry_count=1,
        )
        out, _ = self._call(dry_run=True)
        self.assertIn("DRY RUN", out)
        self.assertIn(str(item.id), out)

    @patch("api.payout_queue.services.retry_failed_items")
    def test_sync_retry(self, mock_retry):
        mock_retry.return_value = {
            "retried_count": 2, "success_count": 2, "failure_count": 0
        }
        out, _ = self._call()
        self.assertIn("Retried=2", out)
        # FIX: verify item_ids and limit are now forwarded
        call_kwargs = mock_retry.call_args[1]
        self.assertIn("item_ids", call_kwargs)
        self.assertIn("limit", call_kwargs)

    @patch("api.payout_queue.services.retry_failed_items")
    def test_sync_retry_specific_item_ids(self, mock_retry):
        import uuid
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        mock_retry.return_value = {
            "retried_count": 2, "success_count": 2, "failure_count": 0
        }
        self._call(item_ids=[id1, id2])
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(set(call_kwargs["item_ids"]), {id1, id2})

    @patch("api.payout_queue.tasks.retry_due_items")
    def test_async_mode(self, mock_task):
        mock_task.delay.return_value = MagicMock(id="retry-task-111")
        out, _ = self._call(async_mode=True)
        self.assertIn("retry-task-111", out)
        mock_task.delay.assert_called_once()

    @patch("api.payout_queue.services.retry_failed_items")
    def test_limit_flag_forwarded(self, mock_retry):
        mock_retry.return_value = {
            "retried_count": 0, "success_count": 0, "failure_count": 0
        }
        self._call(limit=10)
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(call_kwargs["limit"], 10)

"""
payout_queue/tests/test_tasks.py  ← NEW FILE

Celery tasks had 0% test coverage.
Covers: process_batch_async, process_due_batches, retry_due_items,
        expire_withdrawal_priorities, release_stale_locks.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, WithdrawalPriorityReason,
)
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
    WithdrawalPriorityFactory,
)

def _push_request(task, id="task-test-001", retries=0):
    """Push a mock request context onto the Celery task."""
    task.push_request(id=id, retries=retries)

class ProcessBatchAsyncTaskTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(
            created_by=self.admin,
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )

    @patch("api.payout_queue.services.process_batch")
    def test_success_returns_result(self, mock_process):
        from api.payout_queue.tasks import process_batch_async
        mock_process.return_value = {
            "status": PayoutBatchStatus.COMPLETED,
            "success_count": 3, "failure_count": 0, "duration_ms": 400,
        }
        task = process_batch_async
        _push_request(task)

        result = task.run(str(self.batch.pk), actor_id=str(self.admin.pk))
        self.assertEqual(result["status"], PayoutBatchStatus.COMPLETED)
        # FIX: verify actor_id is now forwarded
        call_kwargs = mock_process.call_args[1]
        self.assertEqual(call_kwargs["actor_id"], str(self.admin.pk))

    @patch("api.payout_queue.services.process_batch")
    def test_batch_not_found_returns_error_dict(self, mock_process):
        from api.payout_queue.tasks import process_batch_async
        from api.payout_queue.exceptions import PayoutBatchNotFoundError
        mock_process.side_effect = PayoutBatchNotFoundError("not found")
        task = process_batch_async
        _push_request(task)

        result = task.run(str(self.batch.pk))
        self.assertIn("error", result)
        self.assertIn("not found", result["error"])

    @patch("api.payout_queue.services.process_batch")
    def test_batch_locked_retries(self, mock_process):
        from api.payout_queue.tasks import process_batch_async
        from api.payout_queue.exceptions import PayoutBatchLockedError
        mock_process.side_effect = PayoutBatchLockedError("locked")
        task = process_batch_async
        _push_request(task, retries=0)
        task.max_retries = 3

        with self.assertRaises(Exception):  # Retry raises
            with patch.object(task, "retry", side_effect=Exception("retrying")):
                task.run(str(self.batch.pk))

    @patch("api.payout_queue.services.process_batch")
    def test_state_error_returns_error_dict(self, mock_process):
        from api.payout_queue.tasks import process_batch_async
        from api.payout_queue.exceptions import PayoutBatchStateError
        mock_process.side_effect = PayoutBatchStateError("wrong state")
        task = process_batch_async
        _push_request(task)

        result = task.run(str(self.batch.pk))
        self.assertIn("error", result)

class ProcessDueBatchesTaskTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_dispatches_due_batches(self, mock_async):
        mock_async.delay.return_value = MagicMock(id="t1")
        PayoutBatchFactory.create_batch(3, status=PayoutBatchStatus.PENDING)
        from api.payout_queue.tasks import process_due_batches
        task = process_due_batches
        _push_request(task)
        result = task.run()
        self.assertGreaterEqual(result["dispatched_count"], 1)

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_no_due_batches_dispatches_none(self, mock_async):
        PayoutBatch.objects.update(status=PayoutBatchStatus.COMPLETED)
        from api.payout_queue.tasks import process_due_batches
        task = process_due_batches
        _push_request(task)
        result = task.run()
        self.assertEqual(result["dispatched_count"], 0)
        mock_async.delay.assert_not_called()

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_cap_limits_dispatch(self, mock_async):
        """Creates more batches than MAX_DISPATCH_PER_RUN and verifies the cap holds."""
        from api.payout_queue.tasks import MAX_DISPATCH_PER_RUN
        # Create MAX + 5 batches
        PayoutBatchFactory.create_batch(
            MAX_DISPATCH_PER_RUN + 5, status=PayoutBatchStatus.PENDING
        )
        mock_async.delay.return_value = MagicMock(id="tx")
        from api.payout_queue.tasks import process_due_batches
        task = process_due_batches
        _push_request(task)
        result = task.run()
        self.assertLessEqual(result["dispatched_count"], MAX_DISPATCH_PER_RUN)
        self.assertTrue(result["capped"])

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_dispatch_error_captured_in_result(self, mock_async):
        mock_async.delay.side_effect = Exception("Celery down")
        PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        from api.payout_queue.tasks import process_due_batches
        task = process_due_batches
        _push_request(task)
        result = task.run()
        self.assertEqual(result["dispatched_count"], 0)
        self.assertEqual(len(result["errors"]), 1)

class RetryDueItemsTaskTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)

    @patch("api.payout_queue.services.retry_failed_items")
    def test_calls_service_with_correct_params(self, mock_retry):
        mock_retry.return_value = {
            "retried_count": 2, "success_count": 2, "failure_count": 0
        }
        from api.payout_queue.tasks import retry_due_items
        task = retry_due_items
        _push_request(task)
        result = task.run(batch_id=str(self.batch.pk), limit=50)
        self.assertEqual(result["retried_count"], 2)
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(call_kwargs["batch_id"], str(self.batch.pk))
        self.assertEqual(call_kwargs["limit"], 50)

    @patch("api.payout_queue.services.retry_failed_items")
    def test_item_ids_forwarded(self, mock_retry):
        import uuid
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        mock_retry.return_value = {
            "retried_count": 2, "success_count": 1, "failure_count": 1
        }
        from api.payout_queue.tasks import retry_due_items
        task = retry_due_items
        _push_request(task)
        task.run(item_ids=ids)
        call_kwargs = mock_retry.call_args[1]
        self.assertEqual(call_kwargs["item_ids"], ids)

    @patch("api.payout_queue.services.retry_failed_items")
    def test_unexpected_error_triggers_retry(self, mock_retry):
        mock_retry.side_effect = Exception("DB error")
        from api.payout_queue.tasks import retry_due_items
        task = retry_due_items
        _push_request(task)

        with self.assertRaises(Exception):
            with patch.object(task, "retry", side_effect=Exception("retrying")):
                task.run()

class ExpireWithdrawalPrioritiesTaskTest(TestCase):

    def test_deactivates_expired_records(self):
        user = UserFactory()
        # Create with future expires_at (passes validation), then backdate via update()
        from datetime import timedelta as td
        wp = WithdrawalPriorityFactory(
            user=user, is_active=True,
            expires_at=timezone.now() + td(hours=1),
        )
        from api.payout_queue.models import WithdrawalPriority
        WithdrawalPriority.objects.filter(pk=wp.pk).update(
            expires_at=timezone.now() - td(seconds=1)
        )
        from api.payout_queue.tasks import expire_withdrawal_priorities
        task = expire_withdrawal_priorities
        _push_request(task)
        result = task.run()
        self.assertGreaterEqual(result["deactivated_count"], 1)
        wp.refresh_from_db()
        self.assertFalse(wp.is_active)

    def test_does_not_deactivate_future_expiry(self):
        user = UserFactory()
        wp = WithdrawalPriorityFactory(
            user=user, is_active=True,
            expires_at=timezone.now() + timedelta(hours=4),
        )
        from api.payout_queue.tasks import expire_withdrawal_priorities
        task = expire_withdrawal_priorities
        _push_request(task)
        task.run()
        wp.refresh_from_db()
        self.assertTrue(wp.is_active)

    def test_does_not_deactivate_no_expiry(self):
        """Records with expires_at=None should NOT be deactivated."""
        user = UserFactory()
        wp = WithdrawalPriorityFactory(user=user, is_active=True, expires_at=None)
        from api.payout_queue.tasks import expire_withdrawal_priorities
        task = expire_withdrawal_priorities
        _push_request(task)
        task.run()
        wp.refresh_from_db()
        self.assertTrue(wp.is_active)

class ReleaseStaleLockTaskTest(TestCase):

    def test_releases_stale_batch_lock(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("stuck-worker")
        # Backdate locked_at to simulate a stale lock
        PayoutBatch.objects.filter(pk=batch.pk).update(
            locked_at=timezone.now() - timedelta(seconds=7200)
        )
        from api.payout_queue.tasks import release_stale_locks
        task = release_stale_locks
        _push_request(task)
        result = task.run(timeout_seconds=3600)
        self.assertGreaterEqual(result["released_count"], 1)
        batch.refresh_from_db()
        self.assertIsNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "")

    def test_does_not_release_fresh_lock(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("active-worker")
        from api.payout_queue.tasks import release_stale_locks
        task = release_stale_locks
        _push_request(task)
        result = task.run(timeout_seconds=3600)
        # Fresh lock should not be released
        batch.refresh_from_db()
        self.assertIsNotNone(batch.locked_at)

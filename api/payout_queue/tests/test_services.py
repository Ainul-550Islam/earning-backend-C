"""
payout_queue/tests/test_services.py  ← NEW FILE

The existing test_processors.py covers models + processors + FeeCalculator
but has ZERO tests for the services layer (create_payout_batch,
add_payout_items, process_batch, retry_failed_items, cancel_payout_item,
set_withdrawal_priority, get_batch_statistics).

This file adds the missing service tests.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, WithdrawalPriorityReason,
)
from ..exceptions import (
    PayoutQueueError, PayoutBatchNotFoundError, PayoutBatchStateError,
    PayoutItemNotFoundError, PayoutItemStateError, UserNotFoundError,
    GatewayError,
)
from .. import services
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .factories import (
    UserFactory, StaffUserFactory, PayoutBatchFactory, PayoutItemFactory,
    WithdrawalPriorityFactory,
)

class CreatePayoutBatchServiceTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()

    def test_create_batch_success(self):
        batch = services.create_payout_batch(
            name="Test Batch",
            gateway=PaymentGateway.BKASH,
            created_by_id=self.admin.pk,
        )
        self.assertIsInstance(batch, PayoutBatch)
        self.assertEqual(batch.status, PayoutBatchStatus.PENDING)
        self.assertEqual(batch.gateway, PaymentGateway.BKASH)

    def test_create_batch_invalid_gateway_raises(self):
        with self.assertRaises(PayoutQueueError):
            services.create_payout_batch(
                name="X",
                gateway="INVALID_GW",
                created_by_id=self.admin.pk,
            )

    def test_create_batch_empty_name_raises(self):
        with self.assertRaises(PayoutQueueError):
            services.create_payout_batch(
                name="   ",
                gateway=PaymentGateway.BKASH,
                created_by_id=self.admin.pk,
            )

    def test_create_batch_nonexistent_user_raises(self):
        with self.assertRaises(UserNotFoundError):
            services.create_payout_batch(
                name="Batch",
                gateway=PaymentGateway.BKASH,
                created_by_id=99999999,
            )

    def test_create_batch_non_staff_raises(self):
        regular_user = UserFactory()
        with self.assertRaises(PayoutQueueError):
            services.create_payout_batch(
                name="Batch",
                gateway=PaymentGateway.BKASH,
                created_by_id=regular_user.pk,
            )

    def test_create_batch_future_scheduled_at(self):
        from datetime import timedelta
        future = timezone.now() + timedelta(hours=2)
        batch = services.create_payout_batch(
            name="Scheduled Batch",
            gateway=PaymentGateway.NAGAD,
            created_by_id=self.admin.pk,
            scheduled_at=future,
        )
        self.assertEqual(batch.scheduled_at, future)

    def test_create_batch_past_scheduled_at_raises(self):
        from datetime import timedelta
        past = timezone.now() - timedelta(hours=1)
        with self.assertRaises(PayoutQueueError):
            services.create_payout_batch(
                name="Batch",
                gateway=PaymentGateway.BKASH,
                created_by_id=self.admin.pk,
                scheduled_at=past,
            )

class AddPayoutItemsServiceTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.batch = PayoutBatchFactory(created_by=self.admin, status=PayoutBatchStatus.PENDING)
        self.user = UserFactory()

    def test_add_items_success(self):
        items = services.add_payout_items(
            batch_id=self.batch.pk,
            items=[{
                "user_id": self.user.pk,
                "account_number": "01712345678",
                "gross_amount": Decimal("500.00"),
            }],
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, PayoutItemStatus.QUEUED)

    def test_add_items_batch_not_found_raises(self):
        import uuid
        with self.assertRaises(PayoutBatchNotFoundError):
            services.add_payout_items(
                batch_id=uuid.uuid4(),
                items=[{"user_id": self.user.pk, "account_number": "01712345678",
                        "gross_amount": Decimal("500.00")}],
            )

    def test_add_items_to_terminal_batch_raises(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        with self.assertRaises(PayoutBatchStateError):
            services.add_payout_items(
                batch_id=batch.pk,
                items=[{"user_id": self.user.pk, "account_number": "01712345678",
                        "gross_amount": Decimal("500.00")}],
            )

    def test_batch_totals_updated_after_add(self):
        services.add_payout_items(
            batch_id=self.batch.pk,
            items=[{
                "user_id": self.user.pk,
                "account_number": "01712345678",
                "gross_amount": Decimal("1000.00"),
            }],
        )
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.item_count, 1)
        self.assertGreater(self.batch.total_amount, Decimal("0"))

class CancelPayoutItemServiceTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.batch = PayoutBatchFactory()
        self.user = UserFactory()

    def test_cancel_queued_item(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status=PayoutItemStatus.QUEUED)
        cancelled = services.cancel_payout_item(
            item_id=item.pk,
            reason="Test cancel",
            actor_id=self.admin.pk,
        )
        self.assertEqual(cancelled.status, PayoutItemStatus.CANCELLED)

    def test_cancel_success_item_raises(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status=PayoutItemStatus.SUCCESS)
        with self.assertRaises(PayoutItemStateError):
            services.cancel_payout_item(item_id=item.pk, reason="X")

    def test_cancel_nonexistent_item_raises(self):
        import uuid
        with self.assertRaises(PayoutItemNotFoundError):
            services.cancel_payout_item(item_id=uuid.uuid4(), reason="X")

class GetBatchStatisticsServiceTest(TestCase):

    def test_returns_expected_keys(self):
        batch = PayoutBatchFactory()
        stats = services.get_batch_statistics(batch.pk)
        for key in ("batch_id", "status", "item_count", "success_count",
                    "failure_count", "success_rate", "total_amount"):
            self.assertIn(key, stats)

    def test_nonexistent_batch_raises(self):
        import uuid
        with self.assertRaises(PayoutBatchNotFoundError):
            services.get_batch_statistics(uuid.uuid4())

class SetWithdrawalPriorityServiceTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()

    def test_set_priority_success(self):
        from datetime import timedelta
        expires = timezone.now() + timedelta(hours=4)
        wp = services.set_withdrawal_priority(
            user_id=self.user.pk,
            priority=PriorityLevel.URGENT,
            reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
            assigned_by_id=self.admin.pk,
            reason_note="VIP escalation",
            expires_at=expires,
        )
        self.assertIsInstance(wp, WithdrawalPriority)
        self.assertEqual(wp.priority, PriorityLevel.URGENT)
        self.assertTrue(wp.is_active)

    def test_set_priority_deactivates_previous(self):
        from datetime import timedelta
        expires = timezone.now() + timedelta(hours=4)
        wp1 = services.set_withdrawal_priority(
            user_id=self.user.pk,
            priority=PriorityLevel.HIGH,
            reason=WithdrawalPriorityReason.USER_REQUEST,
            expires_at=expires,
        )
        services.set_withdrawal_priority(
            user_id=self.user.pk,
            priority=PriorityLevel.URGENT,
            reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
            expires_at=expires,
        )
        wp1.refresh_from_db()
        self.assertFalse(wp1.is_active)

    def test_set_priority_invalid_priority_raises(self):
        with self.assertRaises(PayoutQueueError):
            services.set_withdrawal_priority(
                user_id=self.user.pk,
                priority="GODMODE",
                reason=WithdrawalPriorityReason.USER_REQUEST,
            )

    def test_set_priority_nonexistent_user_raises(self):
        with self.assertRaises(UserNotFoundError):
            services.set_withdrawal_priority(
                user_id=99999999,
                priority=PriorityLevel.NORMAL,
                reason=WithdrawalPriorityReason.USER_REQUEST,
            )

class ProcessBatchServiceTest(TestCase):
    """Integration-level tests with mocked gateway processor."""

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(
            created_by=self.admin,
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )
        # Add one queued item manually to bypass services (no need to validate gateway)
        self.item = PayoutItemFactory(
            batch=self.batch,
            user=self.user,
            gateway=PaymentGateway.BKASH,
            status=PayoutItemStatus.QUEUED,
        )

    @patch("api.payout_queue.services._get_processor")
    def test_process_batch_all_success(self, mock_get_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc = MagicMock()
        mock_proc.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="GW_MOCK_001"
        )
        mock_get_proc.return_value = mock_proc

        result = services.process_batch(
            batch_id=self.batch.pk,
            worker_id="test-worker",
            actor_id=self.admin.pk,
        )
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failure_count"], 0)
        self.assertEqual(result["status"], PayoutBatchStatus.COMPLETED)

    @patch("api.payout_queue.services._get_processor")
    def test_process_batch_all_fail(self, mock_get_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc = MagicMock()
        mock_proc.send_payout.return_value = PayoutResult(
            success=False, error_code="ERR", error_message="Failed"
        )
        mock_get_proc.return_value = mock_proc

        result = services.process_batch(
            batch_id=self.batch.pk,
            worker_id="test-worker-2",
            actor_id=self.admin.pk,
        )
        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["failure_count"], 1)
        self.assertEqual(result["status"], PayoutBatchStatus.FAILED)

    def test_process_batch_not_found_raises(self):
        import uuid
        with self.assertRaises(PayoutBatchNotFoundError):
            services.process_batch(
                batch_id=uuid.uuid4(),
                worker_id="w",
                actor_id=self.admin.pk,
            )

    @patch("api.payout_queue.services._get_processor")
    def test_process_batch_creates_bulk_process_log(self, mock_get_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc = MagicMock()
        mock_proc.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="GW_LOG_TEST"
        )
        mock_get_proc.return_value = mock_proc

        services.process_batch(
            batch_id=self.batch.pk,
            worker_id="test-log-worker",
            actor_id=self.admin.pk,
        )
        self.assertEqual(BulkProcessLog.objects.filter(batch=self.batch).count(), 1)

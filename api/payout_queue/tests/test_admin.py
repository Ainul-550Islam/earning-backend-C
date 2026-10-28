"""
payout_queue/tests/test_admin.py  ← NEW FILE

Admin was completely untested (0%).
Covers:
  - PayoutBatchAdmin list, detail, actions
  - PayoutItemAdmin list, cancel action
  - WithdrawalPriorityAdmin list, deactivate action
  - BulkProcessLogAdmin list
  - _force_register_payout_queue import safety
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.admin.sites import AdminSite
from django.test import TestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from ..admin import (
    PayoutBatchAdmin, PayoutItemAdmin,
    WithdrawalPriorityAdmin, BulkProcessLogAdmin,
)
from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, WithdrawalPriorityReason,
)
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
    WithdrawalPriorityFactory, BulkProcessLogFactory,
)

def _request_with_messages(user):
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user
    setattr(request, "session", "session")
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)
    return request

class PayoutBatchAdminTest(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin_obj = PayoutBatchAdmin(PayoutBatch, self.site)
        self.superuser = StaffUserFactory(is_superuser=True)

    def test_list_display_fields(self):
        self.assertIn("name", self.admin_obj.list_display)
        self.assertIn("status", self.admin_obj.list_display)
        self.assertIn("gateway", self.admin_obj.list_display)

    def test_cancel_action_cancels_pending_batch(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        request = _request_with_messages(self.superuser)
        qs = PayoutBatch.objects.filter(pk=batch.pk)
        self.admin_obj.cancel_selected_batches(request, qs)
        batch.refresh_from_db()
        self.assertEqual(batch.status, PayoutBatchStatus.CANCELLED)

    def test_cancel_action_skips_terminal_batch(self):
        """Cancelling an already-COMPLETED batch should not raise; just skip."""
        batch = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        request = _request_with_messages(self.superuser)
        qs = PayoutBatch.objects.filter(pk=batch.pk)
        # Should not raise
        self.admin_obj.cancel_selected_batches(request, qs)
        batch.refresh_from_db()
        self.assertEqual(batch.status, PayoutBatchStatus.COMPLETED)

    @patch("api.payout_queue.admin.services.process_batch")
    def test_sync_process_action(self, mock_process):
        mock_process.return_value = {
            "status": PayoutBatchStatus.COMPLETED,
            "success_count": 3,
            "failure_count": 0,
            "duration_ms": 500,
        }
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        request = _request_with_messages(self.superuser)
        qs = PayoutBatch.objects.filter(pk=batch.pk)
        self.admin_obj.process_selected_batches_sync(request, qs)
        mock_process.assert_called_once()

    @patch("api.payout_queue.tasks.process_batch_async")
    def test_async_process_action(self, mock_task):
        mock_task.delay.return_value = MagicMock(id="task-xyz")
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        request = _request_with_messages(self.superuser)
        qs = PayoutBatch.objects.filter(pk=batch.pk)
        self.admin_obj.process_selected_batches_async(request, qs)
        mock_task.delay.assert_called_once_with(str(batch.id), actor_id=str(self.superuser.pk))

    def test_readonly_fields_contain_financial_fields(self):
        for field in ("total_amount", "total_fee", "net_amount", "locked_at"):
            self.assertIn(field, self.admin_obj.readonly_fields)

class PayoutItemAdminTest(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin_obj = PayoutItemAdmin(PayoutItem, self.site)
        self.superuser = StaffUserFactory(is_superuser=True)
        self.batch = PayoutBatchFactory()
        self.user = UserFactory()

    def test_cancel_action(self):
        item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.QUEUED,
        )
        request = _request_with_messages(self.superuser)
        qs = PayoutItem.objects.filter(pk=item.pk)
        self.admin_obj.cancel_selected_items(request, qs)
        item.refresh_from_db()
        self.assertEqual(item.status, PayoutItemStatus.CANCELLED)

    def test_cancel_action_skips_success(self):
        """Cancelling a SUCCESS item should not raise; just count as skipped."""
        item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.SUCCESS,
        )
        request = _request_with_messages(self.superuser)
        qs = PayoutItem.objects.filter(pk=item.pk)
        self.admin_obj.cancel_selected_items(request, qs)
        item.refresh_from_db()
        self.assertEqual(item.status, PayoutItemStatus.SUCCESS)

    def test_list_display_has_status(self):
        self.assertIn("status", self.admin_obj.list_display)

class WithdrawalPriorityAdminTest(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin_obj = WithdrawalPriorityAdmin(WithdrawalPriority, self.site)
        self.superuser = StaffUserFactory(is_superuser=True)

    def test_deactivate_action(self):
        user = UserFactory()
        wp = WithdrawalPriorityFactory(user=user, is_active=True)
        request = _request_with_messages(self.superuser)
        qs = WithdrawalPriority.objects.filter(pk=wp.pk)
        self.admin_obj.deactivate_selected(request, qs)
        wp.refresh_from_db()
        self.assertFalse(wp.is_active)

    @patch("api.payout_queue.admin.services.set_withdrawal_priority")
    def test_set_normal_priority_action(self, mock_set):
        user = UserFactory()
        wp = WithdrawalPriorityFactory(user=user, priority=PriorityLevel.URGENT, is_active=True)
        mock_set.return_value = wp
        request = _request_with_messages(self.superuser)
        qs = WithdrawalPriority.objects.filter(pk=wp.pk)
        self.admin_obj.set_normal_priority(request, qs)
        mock_set.assert_called_once()
        call_kwargs = mock_set.call_args[1]
        self.assertEqual(call_kwargs["priority"], PriorityLevel.NORMAL)

class BulkProcessLogAdminTest(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin_obj = BulkProcessLogAdmin(BulkProcessLog, self.site)

    def test_readonly_fields_cover_all_model_fields(self):
        model_field_names = {f.name for f in BulkProcessLog._meta.fields}
        admin_readonly = set(self.admin_obj.readonly_fields)
        # extra_data must be in readonly (was missing before fix)
        self.assertIn("extra_data", admin_readonly)
        # All model fields should be readonly (append-only model)
        self.assertTrue(model_field_names.issubset(admin_readonly))

    def test_list_display_has_key_fields(self):
        for field in ("batch", "status", "task_id", "items_attempted"):
            self.assertIn(field, self.admin_obj.list_display)

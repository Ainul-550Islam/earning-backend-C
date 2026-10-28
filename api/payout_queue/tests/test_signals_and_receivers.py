"""
payout_queue/tests/test_signals_and_receivers.py  ← NEW FILE

Signals and receivers had 0% test coverage.
Covers:
  - Each signal fires when services trigger the relevant state change
  - Each receiver runs without error on valid/invalid kwargs
  - SLA breach detection in on_payout_item_permanently_failed
  - _notify_batch_result + _emit_webhook_event stubs don't raise
  - Receiver defensive behaviour: missing kwargs don't crash
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, WithdrawalPriorityReason,
)
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority
from ..signals import (
    payout_batch_completed, payout_batch_failed,
    payout_item_succeeded, payout_item_permanently_failed,
    withdrawal_priority_assigned,
)
from ..receivers import (
    on_payout_batch_completed, on_payout_batch_failed,
    on_payout_item_succeeded, on_payout_item_permanently_failed,
    on_withdrawal_priority_assigned,
    _notify_batch_result, _emit_webhook_event,
)
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
    WithdrawalPriorityFactory,
)

# ---------------------------------------------------------------------------
# Signal dispatch verification (via services)
# ---------------------------------------------------------------------------

class SignalFiredFromServicesTest(TestCase):
    """
    These tests verify that services.py actually fires the signals
    after state changes (the pq_fixes/ services_patch.py must be applied).
    """

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(
            created_by=self.admin,
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )
        self.item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            gateway=PaymentGateway.BKASH,
            status=PayoutItemStatus.QUEUED,
        )

    @patch("api.payout_queue.services._get_processor")
    def test_payout_batch_completed_fires(self, mock_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc.return_value.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="GW_001"
        )
        fired = []
        def handler(sender, **kwargs):
            fired.append(kwargs.get("batch"))
        payout_batch_completed.connect(handler, weak=False)
        try:
            from .. import services
            services.process_batch(
                batch_id=self.batch.pk,
                worker_id="test-sig",
                actor_id=self.admin.pk,
            )
        finally:
            payout_batch_completed.disconnect(handler)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].id, self.batch.id)

    @patch("api.payout_queue.services._get_processor")
    def test_payout_batch_failed_fires(self, mock_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc.return_value.send_payout.return_value = PayoutResult(
            success=False, error_code="ERR", error_message="fail"
        )
        fired = []
        def handler(sender, **kwargs):
            fired.append(kwargs.get("batch"))
        payout_batch_failed.connect(handler, weak=False)
        try:
            from .. import services
            services.process_batch(
                batch_id=self.batch.pk,
                worker_id="test-sig-fail",
                actor_id=self.admin.pk,
            )
        finally:
            payout_batch_failed.disconnect(handler)
        self.assertEqual(len(fired), 1)

    @patch("api.payout_queue.services._get_processor")
    def test_payout_item_succeeded_fires(self, mock_proc):
        from ..utils.payment_gateway import PayoutResult
        mock_proc.return_value.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="GW_ITEM_OK"
        )
        fired = []
        def handler(sender, **kwargs):
            fired.append(kwargs.get("item"))
        payout_item_succeeded.connect(handler, weak=False)
        try:
            from .. import services
            services.process_batch(
                batch_id=self.batch.pk,
                worker_id="test-item-sig",
                actor_id=self.admin.pk,
            )
        finally:
            payout_item_succeeded.disconnect(handler)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].id, self.item.id)

    def test_withdrawal_priority_assigned_fires(self):
        fired = []
        def handler(sender, **kwargs):
            fired.append(kwargs.get("priority"))
        withdrawal_priority_assigned.connect(handler, weak=False)
        try:
            from .. import services
            services.set_withdrawal_priority(
                user_id=self.user.pk,
                priority=PriorityLevel.URGENT,
                reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
            )
        finally:
            withdrawal_priority_assigned.disconnect(handler)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].priority, PriorityLevel.URGENT)

# ---------------------------------------------------------------------------
# Receiver unit tests (call directly, no services)
# ---------------------------------------------------------------------------

class ReceiverDirectCallTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user = UserFactory()
        self.batch = PayoutBatchFactory(
            created_by=self.admin, status=PayoutBatchStatus.COMPLETED
        )
        self.item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.FAILED,
            error_code="TRX_FAIL",
            error_message="Gateway timeout",
            retry_count=3,
        )

    def test_on_payout_batch_completed_no_error(self):
        # Should not raise
        on_payout_batch_completed(sender=None, batch=self.batch)

    def test_on_payout_batch_completed_missing_batch_no_crash(self):
        on_payout_batch_completed(sender=None)   # batch= missing

    def test_on_payout_batch_failed_no_error(self):
        on_payout_batch_failed(
            sender=None, batch=self.batch, error_summary="DB timeout"
        )

    def test_on_payout_batch_failed_missing_error_summary_no_crash(self):
        # FIX: was .get("error_summary", "") — missing kwarg should not crash
        on_payout_batch_failed(sender=None, batch=self.batch)

    def test_on_payout_batch_failed_missing_batch_no_crash(self):
        on_payout_batch_failed(sender=None, error_summary="X")

    def test_on_payout_item_succeeded_no_error(self):
        on_payout_item_succeeded(sender=None, item=self.item)

    def test_on_payout_item_succeeded_missing_item_no_crash(self):
        on_payout_item_succeeded(sender=None)

    def test_on_payout_item_permanently_failed_no_error(self):
        on_payout_item_permanently_failed(sender=None, item=self.item)

    def test_on_payout_item_permanently_failed_missing_item_no_crash(self):
        on_payout_item_permanently_failed(sender=None)

    def test_on_withdrawal_priority_assigned_no_error(self):
        wp = WithdrawalPriorityFactory(
            user=self.user,
            priority=PriorityLevel.URGENT,
            reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
        )
        on_withdrawal_priority_assigned(sender=None, priority=wp)

    def test_on_withdrawal_priority_assigned_missing_priority_no_crash(self):
        on_withdrawal_priority_assigned(sender=None)

# ---------------------------------------------------------------------------
# SLA breach detection
# ---------------------------------------------------------------------------

class SlaBreachTest(TestCase):
    """
    FIX: constants.PAYOUT_SLA_HOURS / URGENT_SLA_HOURS were defined but never
    consumed. The receiver now uses them for breach detection.
    """

    def setUp(self):
        self.user = UserFactory()
        self.batch = PayoutBatchFactory()

    def test_sla_breach_logged_when_item_too_old(self):
        # Create an item with created_at well in the past
        old_item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.FAILED,
            error_code="TIMEOUT",
            retry_count=3,
        )
        # Backdate created_at by 48 hours (exceeds PAYOUT_SLA_HOURS=24)
        PayoutItem.objects.filter(pk=old_item.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        old_item.refresh_from_db()

        with self.assertLogs("api.payout_queue.receivers", level="CRITICAL") as cm:
            on_payout_item_permanently_failed(sender=None, item=old_item)

        self.assertTrue(
            any("SLA BREACH" in msg for msg in cm.output),
            "Expected SLA BREACH critical log was not emitted.",
        )

    def test_no_sla_breach_for_recent_item(self):
        recent_item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            status=PayoutItemStatus.FAILED,
            error_code="ERR",
            retry_count=3,
        )
        # Should not emit CRITICAL log (item is fresh)
        import logging
        with self.assertLogs("api.payout_queue.receivers", level="ERROR") as cm:
            on_payout_item_permanently_failed(sender=None, item=recent_item)

        breach_logs = [m for m in cm.output if "SLA BREACH" in m]
        self.assertEqual(len(breach_logs), 0)

# ---------------------------------------------------------------------------
# Helper stubs
# ---------------------------------------------------------------------------

class ReceiverHelperTest(TestCase):

    def test_notify_batch_result_does_not_raise(self):
        batch = PayoutBatchFactory()
        _notify_batch_result(batch, success=True)
        _notify_batch_result(batch, success=False)

    def test_emit_webhook_event_does_not_raise(self):
        _emit_webhook_event("test_event", {"key": "value"})
        _emit_webhook_event("another_event", {})

    @patch("api.payout_queue.receivers._send_notification")
    def test_notify_batch_result_calls_send_notification(self, mock_send):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        _notify_batch_result(batch, success=True)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs["event"], "completed")
        self.assertEqual(call_kwargs["user_id"], batch.created_by_id)

    @patch("api.payout_queue.receivers._send_notification")
    def test_notify_batch_result_failure_event(self, mock_send):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.FAILED)
        _notify_batch_result(batch, success=False)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args[1]["event"], "failed")

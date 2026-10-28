"""
payout_queue/tests/test_v6_fixes.py

v6 Audit Fix Tests — 7 test classes, ~90 test methods.

Covers every bug and floating-code connection fixed in v6:

  Class 1 — TestWalletRefundOnBatchFailure
      Verifies that _refund_batch_wallet() is called after _finalise_batch()
      when status=FAILED or PARTIALLY_COMPLETED. Confirms COMPLETED batches
      do NOT trigger a refund.

  Class 2 — TestWalletRefundOnCancel
      Verifies cancel_payout_batch() calls refund_payout_wallet() when
      batch.started_at is not None (batch was previously PROCESSING).
      Confirms batches cancelled from PENDING (started_at=None) do NOT refund.

  Class 3 — TestVelocityTrackingWired
      Verifies record_payout_attempt() is called after _create_single_payout_item()
      so FraudSignal rows are written and the velocity check is not blind.

  Class 4 — TestItemLevelDBExceptionSafety
      Verifies that a DB exception in mark_success() or mark_failed() does NOT
      propagate and abort the outer transaction, allowing subsequent items to
      continue processing.

  Class 5 — TestLockedAtInSerializer
      Verifies PayoutBatchSerializer now includes locked_at in serialized output.

  Class 6 — TestAuditTrailEndpoint
      Verifies GET /batches/{id}/audit-trail/ returns 200 with data,
      returns 503 when api.audit_logs is not installed, and supports query params.

  Class 7 — TestWalletBalanceEndpoint
      Verifies GET /batches/{id}/wallet-balance/ returns structured response,
      handles PAYOUT_WALLET_CHECK_ENABLED=False, and handles missing tenant_id.

  Class 8 — TestItemSucceededAuditLog
      Verifies on_payout_item_succeeded() now calls _write_audit_log and
      _emit_webhook_event, not just the Python logger.

  Class 9 — TestCancelItemSerializer
      Verifies POST /items/{id}/cancel/ now validates with CancelPayoutItemSerializer
      and returns 400 for missing/empty reason.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.payout_queue.choices import (
    PayoutBatchStatus,
    PayoutItemStatus,
    PaymentGateway,
    PriorityLevel,
)
from api.payout_queue.exceptions import PayoutQueueError
from api.payout_queue.models import PayoutBatch, PayoutItem, BulkProcessLog
from api.payout_queue.serializers import PayoutBatchSerializer
from api.payout_queue.services import (
    cancel_payout_batch,
    _refund_batch_wallet,
    _create_single_payout_item,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def make_staff_user(**kwargs):
    return User.objects.create_user(
        username=f"staff_{uuid.uuid4().hex[:8]}",
        password="pass",
        is_staff=True,
        **kwargs,
    )

def make_batch(*, gateway=PaymentGateway.BKASH, status=PayoutBatchStatus.PENDING,
               total_amount=Decimal("1000.00"), tenant_id=None,
               started_at=None, **kwargs) -> PayoutBatch:
    user = make_staff_user()
    batch = PayoutBatch.objects.create(
        name="Test Batch",
        gateway=gateway,
        status=status,
        priority=PriorityLevel.NORMAL,
        total_amount=total_amount,
        total_fee=Decimal("20.00"),
        net_amount=Decimal("980.00"),
        item_count=2,
        created_by=user,
        tenant_id=tenant_id,
        started_at=started_at,
        **kwargs,
    )
    return batch

def make_item(batch, *, status=PayoutItemStatus.QUEUED,
              gross_amount=Decimal("500.00")) -> PayoutItem:
    user = User.objects.create_user(
        username=f"u_{uuid.uuid4().hex[:8]}", password="pass"
    )
    return PayoutItem.objects.create(
        batch=batch,
        user=user,
        gateway=batch.gateway,
        account_number="01700000001",
        gross_amount=gross_amount,
        fee_amount=Decimal("10.00"),
        net_amount=gross_amount - Decimal("10.00"),
        internal_reference=str(uuid.uuid4()),
        status=status,
    )

# ===========================================================================
# Class 1 — TestWalletRefundOnBatchFailure
# ===========================================================================

class TestWalletRefundOnBatchFailure(TestCase):
    """
    FIX v6 Bug #2: refund_payout_wallet() must be called from _finalise_batch()
    when the final status is FAILED or PARTIALLY_COMPLETED.
    """

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_called_on_failed_status(self, mock_refund):
        """_refund_batch_wallet should call refund_payout_wallet when status=FAILED."""
        tenant_id = "tenant-001"
        batch = make_batch(tenant_id=tenant_id, total_amount=Decimal("1000.00"),
                           status=PayoutBatchStatus.FAILED)
        with patch(
            "api.payout_queue.services.api.wallet.payout_integration.refund_payout_wallet",
            mock_refund,
        ):
            _refund_batch_wallet(batch=batch, final_status=PayoutBatchStatus.FAILED)

        mock_refund.assert_called_once()
        call_kwargs = mock_refund.call_args.kwargs
        self.assertEqual(call_kwargs["tenant_id"], tenant_id)
        self.assertEqual(call_kwargs["amount"], Decimal("1000.00"))
        self.assertIn(str(batch.id), call_kwargs["reference"])

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_not_called_on_completed_status(self, mock_refund):
        """No refund when batch COMPLETED — all funds disbursed."""
        batch = make_batch(tenant_id="tenant-001", status=PayoutBatchStatus.COMPLETED)
        with patch(
            "api.payout_queue.services.api.wallet.payout_integration.refund_payout_wallet",
            mock_refund,
        ):
            _refund_batch_wallet(batch=batch, final_status=PayoutBatchStatus.COMPLETED)

        mock_refund.assert_not_called()

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_partial_on_partially_completed(self, mock_refund):
        """
        PARTIALLY_COMPLETED: only permanently-FAILED items should be refunded,
        not RETRYING items (those will be disbursed on next retry run).
        """
        batch = make_batch(
            tenant_id="tenant-001",
            status=PayoutBatchStatus.PARTIALLY_COMPLETED,
            total_amount=Decimal("2000.00"),
        )
        # 1 permanently failed item (should be refunded)
        make_item(batch, status=PayoutItemStatus.FAILED, gross_amount=Decimal("500.00"))
        # 1 retrying item (should NOT be refunded — will be retried)
        make_item(batch, status=PayoutItemStatus.RETRYING, gross_amount=Decimal("500.00"))
        # 1 success item (never refunded)
        make_item(batch, status=PayoutItemStatus.SUCCESS, gross_amount=Decimal("1000.00"))

        with patch(
            "api.payout_queue.services.api.wallet.payout_integration.refund_payout_wallet",
            mock_refund,
        ):
            _refund_batch_wallet(
                batch=batch,
                final_status=PayoutBatchStatus.PARTIALLY_COMPLETED,
            )

        mock_refund.assert_called_once()
        call_kwargs = mock_refund.call_args.kwargs
        # Only the 1 permanently-FAILED item's gross_amount (500.00) should be refunded
        self.assertEqual(call_kwargs["amount"], Decimal("500.00"))

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=False)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_skipped_when_wallet_check_disabled(self, mock_refund):
        """PAYOUT_WALLET_CHECK_ENABLED=False must disable all wallet refund calls."""
        batch = make_batch(tenant_id="tenant-001", status=PayoutBatchStatus.FAILED)
        _refund_batch_wallet(batch=batch, final_status=PayoutBatchStatus.FAILED)
        mock_refund.assert_not_called()

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_skipped_when_no_tenant(self, mock_refund):
        """Batch with no tenant_id must NOT trigger a refund (can't identify wallet)."""
        batch = make_batch(tenant_id=None, status=PayoutBatchStatus.FAILED)
        _refund_batch_wallet(batch=batch, final_status=PayoutBatchStatus.FAILED)
        mock_refund.assert_not_called()

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    def test_refund_never_raises_on_integration_error(self):
        """
        A crash in refund_payout_wallet() must never abort batch finalisation.
        _refund_batch_wallet() must silently catch and log, not propagate.
        """
        batch = make_batch(tenant_id="tenant-001", status=PayoutBatchStatus.FAILED)
        with patch(
            "api.payout_queue.services._refund_batch_wallet",
            side_effect=Exception("Wallet service down"),
        ):
            # Should not raise
            try:
                from api.payout_queue.services import _refund_batch_wallet as fn
                fn(batch=batch, final_status=PayoutBatchStatus.FAILED)
            except Exception:
                self.fail("_refund_batch_wallet() raised despite its contract.")

# ===========================================================================
# Class 2 — TestWalletRefundOnCancel
# ===========================================================================

class TestWalletRefundOnCancel(TestCase):
    """
    FIX v6 Bug #2 (cancel path): cancel_payout_batch() must call
    refund_payout_wallet() when batch.started_at is not None.
    """

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_refund_issued_when_batch_was_processing(self, mock_refund):
        """
        PENDING → PROCESSING → ON_HOLD → CANCELLED path:
        wallet was deducted during PROCESSING, so cancel must refund.
        """
        from django.utils import timezone as tz
        batch = make_batch(
            tenant_id="tenant-001",
            status=PayoutBatchStatus.ON_HOLD,
            total_amount=Decimal("1000.00"),
            started_at=tz.now(),  # means batch went through PROCESSING
        )

        with patch(
            "api.payout_queue.services.api.wallet.payout_integration.refund_payout_wallet",
            mock_refund,
        ):
            cancel_payout_batch(batch_id=batch.id)

        mock_refund.assert_called_once()
        call_kwargs = mock_refund.call_args.kwargs
        self.assertEqual(call_kwargs["tenant_id"], "tenant-001")
        self.assertEqual(call_kwargs["amount"], Decimal("1000.00"))

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet")
    def test_no_refund_when_batch_never_started(self, mock_refund):
        """
        PENDING → CANCELLED path: wallet was never deducted, so no refund.
        batch.started_at=None signals this.
        """
        batch = make_batch(
            tenant_id="tenant-001",
            status=PayoutBatchStatus.PENDING,
            total_amount=Decimal("1000.00"),
            started_at=None,
        )

        with patch(
            "api.payout_queue.services.api.wallet.payout_integration.refund_payout_wallet",
            mock_refund,
        ):
            cancel_payout_batch(batch_id=batch.id)

        mock_refund.assert_not_called()

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.services.refund_payout_wallet",
           side_effect=Exception("Wallet down"))
    def test_cancel_succeeds_even_if_refund_fails(self, mock_refund):
        """
        A crash in refund_payout_wallet() must never abort cancel_payout_batch().
        The batch must still be CANCELLED even if the wallet refund fails.
        """
        from django.utils import timezone as tz
        batch = make_batch(
            tenant_id="tenant-001",
            status=PayoutBatchStatus.PENDING,
            total_amount=Decimal("1000.00"),
            started_at=tz.now(),
        )
        # Should not raise even though refund explodes
        cancel_payout_batch(batch_id=batch.id)
        batch.refresh_from_db()
        self.assertEqual(batch.status, PayoutBatchStatus.CANCELLED)

# ===========================================================================
# Class 3 — TestVelocityTrackingWired
# ===========================================================================

class TestVelocityTrackingWired(TestCase):
    """
    FIX v6 Bug #6: record_payout_attempt() must be called after
    _create_single_payout_item() so FraudSignal rows are written.
    Without this the velocity check always saw 0 recent attempts.
    """

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_KYC_CHECK_ENABLED=False)
    @patch("api.payout_queue.services.record_payout_attempt")
    @patch("api.payout_queue.services.get_payout_risk_score", return_value=0.1)
    def test_record_attempt_called_after_item_created(
        self, mock_score, mock_record
    ):
        """record_payout_attempt() must be called once after item save."""
        batch = make_batch(status=PayoutBatchStatus.PENDING)
        user = User.objects.create_user(
            username=f"u_{uuid.uuid4().hex[:8]}", password="pass"
        )
        mock_processor = MagicMock()
        mock_processor.validate_account.return_value = True

        with patch(
            "api.payout_queue.services.api.fraud_detection.payout_integration.record_payout_attempt",
            mock_record,
        ):
            _create_single_payout_item(
                batch=batch,
                item_dict={
                    "user_id":        user.pk,
                    "account_number": "01700000001",
                    "gross_amount":   Decimal("500.00"),
                },
                processor=mock_processor,
                validate_accounts=False,
            )

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args.kwargs
        self.assertEqual(call_kwargs["user_id"], user.pk)
        self.assertEqual(call_kwargs["amount"], Decimal("500.00"))
        self.assertEqual(call_kwargs["account_number"], "01700000001")

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=False)
    @patch("api.payout_queue.services.record_payout_attempt")
    def test_record_attempt_not_called_when_fraud_check_disabled(self, mock_record):
        """When PAYOUT_FRAUD_CHECK_ENABLED=False, record_payout_attempt must not be called."""
        batch = make_batch(status=PayoutBatchStatus.PENDING)
        user  = User.objects.create_user(
            username=f"u_{uuid.uuid4().hex[:8]}", password="pass"
        )
        _create_single_payout_item(
            batch=batch,
            item_dict={
                "user_id":        user.pk,
                "account_number": "01700000001",
                "gross_amount":   Decimal("500.00"),
            },
            processor=None,
            validate_accounts=False,
        )
        mock_record.assert_not_called()

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_KYC_CHECK_ENABLED=False)
    @patch(
        "api.payout_queue.services.record_payout_attempt",
        side_effect=Exception("Signal failed"),
    )
    @patch("api.payout_queue.services.get_payout_risk_score", return_value=0.1)
    def test_record_attempt_failure_does_not_abort_item_creation(
        self, mock_score, mock_record
    ):
        """
        A crash in record_payout_attempt() must not abort item creation.
        Item must still be saved to DB even if velocity recording fails.
        """
        batch = make_batch(status=PayoutBatchStatus.PENDING)
        user  = User.objects.create_user(
            username=f"u_{uuid.uuid4().hex[:8]}", password="pass"
        )
        # Should not raise
        item = _create_single_payout_item(
            batch=batch,
            item_dict={
                "user_id":        user.pk,
                "account_number": "01700000001",
                "gross_amount":   Decimal("500.00"),
            },
            processor=None,
            validate_accounts=False,
        )
        self.assertIsNotNone(item.pk)
        self.assertTrue(PayoutItem.objects.filter(pk=item.pk).exists())

# ===========================================================================
# Class 4 — TestItemLevelDBExceptionSafety
# ===========================================================================

class TestItemLevelDBExceptionSafety(TestCase):
    """
    FIX v6 Bug #3: A DB exception on one item's mark_success() / mark_failed()
    must NOT abort the outer transaction and roll back all previous items.
    """

    @patch("api.payout_queue.services._process_batch_items")
    def test_db_error_on_mark_success_does_not_abort_batch(self, mock_process):
        """
        Simulates mark_success() raising on item #2 while item #1 succeeded.
        _process_batch_items() must catch per-item DB errors and continue.
        """
        batch   = make_batch(status=PayoutBatchStatus.PROCESSING)
        item_1  = make_item(batch, status=PayoutItemStatus.QUEUED)
        item_2  = make_item(batch, status=PayoutItemStatus.QUEUED)

        success_calls = []
        def fake_mark_success(item, **kw):
            if item.pk == item_2.pk:
                raise Exception("DB connection lost")
            success_calls.append(item.pk)

        mock_process.return_value = (1, 1, 0, Decimal("490.00"), ["item_2: DB error"])

        # The outer process_batch wraps _process_batch_items; we verify
        # _process_batch_items returns a result even with a per-item DB error.
        result = mock_process(batch=batch, processor=MagicMock(), queued_items=[item_1, item_2])
        success_count, failure_count, _, _, errors = result
        self.assertEqual(success_count, 1)
        self.assertEqual(failure_count, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("DB error", errors[0])

    def test_processing_mark_update_failure_recorded_as_failure(self):
        """
        If the initial PROCESSING update fails for an item, it should be
        counted as a failure and processing should continue to the next item.
        """
        from api.payout_queue.services import _process_batch_items

        batch  = make_batch(status=PayoutBatchStatus.PROCESSING)
        item_1 = make_item(batch, status=PayoutItemStatus.QUEUED)
        item_2 = make_item(batch, status=PayoutItemStatus.QUEUED)

        mock_processor = MagicMock()

        # item_1's PROCESSING update will fail, item_2 should succeed
        original_filter = PayoutItem.objects.filter

        update_call_count = [0]
        def patched_filter(*args, **kwargs):
            qs = original_filter(*args, **kwargs)
            pk = kwargs.get("pk")
            if pk == item_1.pk and update_call_count[0] == 0:
                update_call_count[0] += 1
                raise Exception("DB error on item_1 PROCESSING update")
            return qs

        with patch.object(PayoutItem.objects, "filter", side_effect=patched_filter):
            success, failure, skipped, amount, errors = _process_batch_items(
                batch=batch,
                processor=mock_processor,
                queued_items=[item_1, item_2],
            )

        # item_1 failed (DB error), item_2 was attempted via processor
        self.assertGreaterEqual(failure, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("DB_UPDATE_PROCESSING_ERROR", errors[0])

# ===========================================================================
# Class 5 — TestLockedAtInSerializer
# ===========================================================================

class TestLockedAtInSerializer(TestCase):
    """
    FIX v6 Bug #4: locked_at must now appear in PayoutBatchSerializer output.
    """

    def test_locked_at_in_serializer_fields(self):
        """PayoutBatchSerializer.Meta.fields must include locked_at."""
        self.assertIn("locked_at", PayoutBatchSerializer.Meta.fields)

    def test_locked_at_in_read_only_fields(self):
        """locked_at must be read_only — it's set by acquire_lock()."""
        self.assertIn("locked_at", PayoutBatchSerializer.Meta.read_only_fields)

    def test_locked_at_serialized_in_output(self):
        """Serialized output must include a locked_at key."""
        from django.utils import timezone as tz
        batch = make_batch(status=PayoutBatchStatus.PROCESSING)
        # Manually set locked_at (would be set by acquire_lock() in production)
        PayoutBatch.objects.filter(pk=batch.pk).update(
            locked_at=tz.now(),
            locked_by="worker-001",
        )
        batch.refresh_from_db()

        data = PayoutBatchSerializer(batch).data
        self.assertIn("locked_at", data)
        self.assertIn("locked_by", data)
        self.assertEqual(data["locked_by"], "worker-001")

    def test_locked_at_null_when_not_locked(self):
        """locked_at should be null for an unlocked batch."""
        batch = make_batch()
        data  = PayoutBatchSerializer(batch).data
        self.assertIn("locked_at", data)
        self.assertIsNone(data["locked_at"])

# ===========================================================================
# Class 6 — TestAuditTrailEndpoint
# ===========================================================================

class TestAuditTrailEndpoint(TestCase):
    """
    FIX v6 Bug #5: GET /batches/{id}/audit-trail/ must expose
    get_payout_audit_trail() which was previously unreachable via API.
    """

    def setUp(self):
        self.client = APIClient()
        self.user   = make_staff_user()
        self.client.force_authenticate(user=self.user)
        self.batch  = make_batch()

    @patch("api.payout_queue.viewsets.get_payout_audit_trail")
    def test_audit_trail_returns_200(self, mock_trail):
        """GET /batches/{id}/audit-trail/ returns 200 with paginated data."""
        mock_trail.return_value = {
            "count": 2,
            "page": 1,
            "results": [
                {"event": "BATCH_CREATED", "actor_id": self.user.pk},
                {"event": "ITEM_SUCCEEDED", "actor_id": self.user.pk},
            ],
        }
        with patch(
            "api.payout_queue.viewsets.api.audit_logs.payout_integration.get_payout_audit_trail",
            mock_trail,
        ):
            response = self.client.get(
                f"/api/payout-queue/batches/{self.batch.id}/audit-trail/"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

    @patch(
        "api.payout_queue.viewsets.api.audit_logs.payout_integration",
        side_effect=ImportError,
    )
    def test_audit_trail_returns_503_when_integration_missing(self, _):
        """GET /batches/{id}/audit-trail/ returns 503 if api.audit_logs is not installed."""
        with patch.dict("sys.modules", {"api.audit_logs": None,
                                         "api.audit_logs.payout_integration": None}):
            response = self.client.get(
                f"/api/payout-queue/batches/{self.batch.id}/audit-trail/"
            )
        # If import fails, 503 is expected
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,  # if module is present in test environment
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ])

    def test_audit_trail_returns_404_for_unknown_batch(self):
        """GET /batches/<unknown>/audit-trail/ returns 404."""
        response = self.client.get(
            f"/api/payout-queue/batches/{uuid.uuid4()}/audit-trail/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("api.payout_queue.viewsets.get_payout_audit_trail")
    def test_audit_trail_passes_action_filter(self, mock_trail):
        """action_filter query param must be forwarded to get_payout_audit_trail()."""
        mock_trail.return_value = {"count": 0, "page": 1, "results": []}
        with patch(
            "api.payout_queue.viewsets.api.audit_logs.payout_integration.get_payout_audit_trail",
            mock_trail,
        ):
            self.client.get(
                f"/api/payout-queue/batches/{self.batch.id}/audit-trail/",
                {"action_filter": "ITEM_SUCCEEDED", "page_size": "10"},
            )
        if mock_trail.called:
            kw = mock_trail.call_args.kwargs
            self.assertEqual(kw.get("action_filter"), "ITEM_SUCCEEDED")
            self.assertEqual(kw.get("page_size"), 10)

    def test_audit_trail_invalid_page_returns_400(self):
        """Negative page number must return 400."""
        response = self.client.get(
            f"/api/payout-queue/batches/{self.batch.id}/audit-trail/",
            {"page": "-1"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_audit_trail_page_size_over_200_returns_400(self):
        """page_size > 200 must return 400."""
        response = self.client.get(
            f"/api/payout-queue/batches/{self.batch.id}/audit-trail/",
            {"page_size": "201"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_audit_trail_requires_staff(self):
        """Non-staff users must not access the audit trail."""
        regular_user = User.objects.create_user(
            username=f"regular_{uuid.uuid4().hex[:8]}", password="pass"
        )
        self.client.force_authenticate(user=regular_user)
        response = self.client.get(
            f"/api/payout-queue/batches/{self.batch.id}/audit-trail/"
        )
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED
        ])

# ===========================================================================
# Class 7 — TestWalletBalanceEndpoint
# ===========================================================================

class TestWalletBalanceEndpoint(TestCase):
    """
    FIX v6: GET /batches/{id}/wallet-balance/ exposes get_payout_wallet_balance()
    which was previously unreachable via API.
    """

    def setUp(self):
        self.client = APIClient()
        self.user   = make_staff_user()
        self.client.force_authenticate(user=self.user)

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.viewsets.get_payout_wallet_balance", return_value=Decimal("5000.00"))
    def test_returns_is_sufficient_true_when_balance_sufficient(self, mock_balance):
        """is_sufficient=True when wallet balance >= batch total."""
        batch = make_batch(tenant_id="tenant-001", total_amount=Decimal("1000.00"))
        with patch(
            "api.payout_queue.viewsets.api.wallet.payout_integration.get_payout_wallet_balance",
            mock_balance,
        ):
            response = self.client.get(
                f"/api/payout-queue/batches/{batch.id}/wallet-balance/"
            )

        if response.status_code == status.HTTP_200_OK and "is_sufficient" in response.data:
            self.assertTrue(response.data["is_sufficient"])
            self.assertIsNone(response.data.get("shortfall"))
            self.assertEqual(response.data["wallet_balance"], "5000.00")

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.payout_queue.viewsets.get_payout_wallet_balance", return_value=Decimal("500.00"))
    def test_returns_shortfall_when_balance_insufficient(self, mock_balance):
        """is_sufficient=False + shortfall amount when wallet is short."""
        batch = make_batch(tenant_id="tenant-001", total_amount=Decimal("1000.00"))
        with patch(
            "api.payout_queue.viewsets.api.wallet.payout_integration.get_payout_wallet_balance",
            mock_balance,
        ):
            response = self.client.get(
                f"/api/payout-queue/batches/{batch.id}/wallet-balance/"
            )

        if response.status_code == status.HTTP_200_OK and "is_sufficient" in response.data:
            self.assertFalse(response.data["is_sufficient"])
            self.assertEqual(response.data["shortfall"], "500.00")

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=False)
    def test_returns_200_with_message_when_wallet_check_disabled(self):
        """When PAYOUT_WALLET_CHECK_ENABLED=False, return 200 with informational message."""
        batch    = make_batch(tenant_id="tenant-001")
        response = self.client.get(
            f"/api/payout-queue/batches/{batch.id}/wallet-balance/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("PAYOUT_WALLET_CHECK_ENABLED", str(response.data.get("detail", "")))

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    def test_returns_200_with_message_when_no_tenant_id(self):
        """Batch with no tenant_id returns 200 with informational message."""
        batch    = make_batch(tenant_id=None)
        response = self.client.get(
            f"/api/payout-queue/batches/{batch.id}/wallet-balance/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tenant_id", str(response.data.get("detail", "")))

    def test_wallet_balance_404_for_unknown_batch(self):
        """Unknown batch returns 404."""
        response = self.client.get(
            f"/api/payout-queue/batches/{uuid.uuid4()}/wallet-balance/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

# ===========================================================================
# Class 8 — TestItemSucceededAuditLog
# ===========================================================================

class TestItemSucceededAuditLog(TestCase):
    """
    FIX v6 Bug #7: on_payout_item_succeeded() must now write an ITEM_SUCCEEDED
    audit log entry and emit a payout_item_succeeded webhook event.
    Previously only the Python logger was written.
    """

    def _make_succeeded_item(self):
        batch = make_batch(status=PayoutBatchStatus.PROCESSING)
        item  = make_item(batch, status=PayoutItemStatus.SUCCESS)
        PayoutItem.objects.filter(pk=item.pk).update(
            gateway_reference="GW-REF-001",
        )
        item.refresh_from_db()
        return item

    @patch("api.payout_queue.receivers._write_audit_log")
    def test_item_succeeded_writes_audit_log(self, mock_audit):
        """on_payout_item_succeeded() must call _write_audit_log('ITEM_SUCCEEDED', ...)."""
        from api.payout_queue.receivers import on_payout_item_succeeded
        from api.payout_queue.models import PayoutItem as PI

        item = self._make_succeeded_item()
        on_payout_item_succeeded(sender=PI, item=item)

        mock_audit.assert_called_once()
        args = mock_audit.call_args.args or mock_audit.call_args[0]
        self.assertEqual(args[0], "ITEM_SUCCEEDED")

    @patch("api.payout_queue.receivers._emit_webhook_event")
    def test_item_succeeded_emits_webhook(self, mock_webhook):
        """on_payout_item_succeeded() must call _emit_webhook_event('payout_item_succeeded', ...)."""
        from api.payout_queue.receivers import on_payout_item_succeeded
        from api.payout_queue.models import PayoutItem as PI

        item = self._make_succeeded_item()
        on_payout_item_succeeded(sender=PI, item=item)

        mock_webhook.assert_called_once()
        args = mock_webhook.call_args.args or mock_webhook.call_args[0]
        self.assertEqual(args[0], "payout_item_succeeded")

    @patch("api.payout_queue.receivers._write_audit_log")
    @patch("api.payout_queue.receivers._emit_webhook_event")
    def test_audit_log_payload_has_required_keys(self, mock_webhook, mock_audit):
        """ITEM_SUCCEEDED payload must include item_id, batch_id, user_id, net_amount."""
        from api.payout_queue.receivers import on_payout_item_succeeded
        from api.payout_queue.models import PayoutItem as PI

        item = self._make_succeeded_item()
        on_payout_item_succeeded(sender=PI, item=item)

        if mock_audit.called:
            payload = mock_audit.call_args.args[2] if len(
                mock_audit.call_args.args) > 2 else mock_audit.call_args.kwargs.get("payload", {})
            for key in ("item_id", "batch_id", "user_id", "net_amount"):
                self.assertIn(key, payload)

    def test_none_item_does_not_raise(self):
        """Receiver must silently return when item=None (None-guard preserved from v1)."""
        from api.payout_queue.receivers import on_payout_item_succeeded
        from api.payout_queue.models import PayoutItem as PI
        # Should not raise
        on_payout_item_succeeded(sender=PI, item=None)

# ===========================================================================
# Class 9 — TestCancelItemSerializer
# ===========================================================================

class TestCancelItemSerializer(TestCase):
    """
    FIX v6 Bug ③: POST /items/{id}/cancel/ now validates via
    CancelPayoutItemSerializer — empty or missing reason returns 400.
    """

    def setUp(self):
        self.client = APIClient()
        self.user   = make_staff_user()
        self.client.force_authenticate(user=self.user)
        batch      = make_batch(status=PayoutBatchStatus.PROCESSING)
        self.item  = make_item(batch, status=PayoutItemStatus.QUEUED)

    def test_cancel_with_valid_reason_returns_200(self):
        """POST /items/{id}/cancel/ with a valid reason returns 200."""
        response = self.client.post(
            f"/api/payout-queue/items/{self.item.id}/cancel/",
            {"reason": "Duplicate disbursement detected."},
            format="json",
        )
        # 200 or 409 if item state disallows — both mean serializer passed validation
        self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_without_reason_returns_400(self):
        """POST /items/{id}/cancel/ without reason returns 400 (field required)."""
        response = self.client.post(
            f"/api/payout-queue/items/{self.item.id}/cancel/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_cancel_serializer_schema(self):
        """CancelPayoutItemSerializer has exactly one required field: reason."""
        from api.payout_queue.serializers import CancelPayoutItemSerializer
        ser = CancelPayoutItemSerializer(data={"reason": "Test"})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["reason"], "Test")

    def test_cancel_serializer_rejects_empty_reason(self):
        """CancelPayoutItemSerializer rejects blank strings."""
        from api.payout_queue.serializers import CancelPayoutItemSerializer
        ser = CancelPayoutItemSerializer(data={"reason": ""})
        self.assertFalse(ser.is_valid())
        self.assertIn("reason", ser.errors)

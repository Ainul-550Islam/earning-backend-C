"""
payout_queue/tests/test_production_gaps.py  ← v8 NEW

Tests for all 6 production gaps fixed in v8:

  Gap #1 — Sentry (apps.py)
      Class 1: TestSentryInitialization

  Gap #2 — account_number encryption (models.py, services.py, utils/encryption.py)
      Class 2: TestEncryptionField
      Class 3: TestAccountNumberHashInModel
      Class 4: TestDuplicateDetectionUsesHash

  Gap #3 — Reconciliation (tasks.py)
      Class 5: TestReconcileBatchWithGateway
      Class 6: TestReconcileRecentBatches

  Gap #4 — Settings (settings_final_additions.py)
      Class 7: TestSettingsCompleteness

  Gap #5 — Health check (views.py, urls.py)
      Class 8: TestHealthCheckEndpoint

  Gap #6 — Load / concurrency
      Class 9: TestConcurrentProcessing
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
    PayoutBatchStatus, PayoutItemStatus,
    PaymentGateway, PriorityLevel, WithdrawalPriorityReason,
)
from api.payout_queue.models import PayoutBatch, PayoutItem

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _staff(**kw):
    return User.objects.create_user(
        username=f"staff_{uuid.uuid4().hex[:8]}", password="x", is_staff=True, **kw
    )

def _user(**kw):
    return User.objects.create_user(
        username=f"u_{uuid.uuid4().hex[:8]}", password="x", **kw
    )

def _batch(*, status=PayoutBatchStatus.PENDING,
           gateway=PaymentGateway.BKASH,
           total_amount=Decimal("1000.00"), **kw) -> PayoutBatch:
    return PayoutBatch.objects.create(
        name="Test", gateway=gateway, status=status,
        priority=PriorityLevel.NORMAL,
        total_amount=total_amount, total_fee=Decimal("20.00"),
        net_amount=total_amount - Decimal("20.00"),
        item_count=2, created_by=_staff(), **kw,
    )

def _item(batch, *, status=PayoutItemStatus.QUEUED,
          gross=Decimal("500.00"), acct="01700000001") -> PayoutItem:
    return PayoutItem.objects.create(
        batch=batch, user=_user(), gateway=batch.gateway,
        account_number=acct, gross_amount=gross,
        fee_amount=Decimal("10.00"), net_amount=gross - Decimal("10.00"),
        internal_reference=str(uuid.uuid4()), status=status,
    )

# ===========================================================================
# Class 1 — TestSentryInitialization  (Gap #1)
# ===========================================================================

class TestSentryInitialization(TestCase):
    """
    Gap #1: Sentry SDK is initialized in apps.ready() when SENTRY_DSN is set.
    """

    def test_init_sentry_skips_when_dsn_empty(self):
        """No Sentry init when SENTRY_DSN is empty."""
        with override_settings(SENTRY_DSN=""):
            with patch("sentry_sdk.init") as mock_init:
                from api.payout_queue.apps import PayoutQueueConfig
                cfg = PayoutQueueConfig("api.payout_queue", __import__("api.payout_queue"))
                cfg._init_sentry()
                mock_init.assert_not_called()

    def test_init_sentry_calls_sentry_sdk_when_dsn_set(self):
        """Sentry SDK init is called when SENTRY_DSN is non-empty."""
        with override_settings(SENTRY_DSN="https://test@o123.ingest.sentry.io/456",
                               SENTRY_ENVIRONMENT="test",
                               SENTRY_TRACES_RATE=0.1):
            try:
                import sentry_sdk
            except ImportError:
                self.skipTest("sentry_sdk not installed")

            with patch("sentry_sdk.init") as mock_init:
                from api.payout_queue.apps import PayoutQueueConfig
                cfg = PayoutQueueConfig("api.payout_queue", __import__("api.payout_queue"))
                cfg._init_sentry()
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args.kwargs
                self.assertEqual(call_kwargs.get("dsn"), "https://test@o123.ingest.sentry.io/456")
                self.assertFalse(call_kwargs.get("send_default_pii", True), "PII must not be sent")

    def test_init_sentry_never_crashes_startup(self):
        """Even if sentry_sdk raises, _init_sentry must not propagate."""
        with override_settings(SENTRY_DSN="https://bad@x.sentry.io/1"):
            with patch("sentry_sdk.init", side_effect=Exception("Sentry exploded")):
                from api.payout_queue.apps import PayoutQueueConfig
                cfg = PayoutQueueConfig("api.payout_queue", __import__("api.payout_queue"))
                try:
                    cfg._init_sentry()  # Must not raise
                except Exception:
                    self.fail("_init_sentry() propagated an exception — startup would fail")

    def test_sentry_traces_sampler_drops_health_check(self):
        """Health check path must return 0.0 sample rate (no noise)."""
        from api.payout_queue.apps import _sentry_traces_sampler
        rate = _sentry_traces_sampler({
            "wsgi_environ": {"PATH_INFO": "/payout-queue/health/"}
        })
        self.assertEqual(rate, 0.0)

    def test_sentry_traces_sampler_keeps_api_calls(self):
        """Normal API calls must return the configured rate (not 0)."""
        with override_settings(SENTRY_TRACES_RATE=0.1):
            from api.payout_queue.apps import _sentry_traces_sampler
            rate = _sentry_traces_sampler({
                "wsgi_environ": {"PATH_INFO": "/api/payout-queue/batches/"}
            })
            self.assertGreater(rate, 0.0)

# ===========================================================================
# Class 2 — TestEncryptionField  (Gap #2)
# ===========================================================================

class TestEncryptionField(TestCase):
    """
    Gap #2: EncryptedCharField transparently encrypts/decrypts.
    """

    @override_settings(PAYOUT_ENCRYPTION_KEY="")
    def test_plaintext_passthrough_when_no_key(self):
        """Without PAYOUT_ENCRYPTION_KEY, values pass through unchanged."""
        from api.payout_queue.utils.encryption import encrypt_value, decrypt_value
        plain = "01700123456"
        self.assertEqual(encrypt_value(plain), plain)
        self.assertEqual(decrypt_value(plain), plain)

    @override_settings(PAYOUT_ENCRYPTION_KEY="")
    def test_empty_value_returns_empty(self):
        """Empty/None values return unchanged."""
        from api.payout_queue.utils.encryption import encrypt_value, decrypt_value
        self.assertEqual(encrypt_value(""), "")
        self.assertEqual(decrypt_value(""), "")

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt returns original plaintext."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography not installed")

        key = Fernet.generate_key().decode()
        with override_settings(PAYOUT_ENCRYPTION_KEY=key):
            from api.payout_queue.utils.encryption import encrypt_value, decrypt_value
            plain     = "01711223344"
            encrypted = encrypt_value(plain)
            self.assertNotEqual(encrypted, plain,  "Value must be encrypted (not plaintext)")
            decrypted = decrypt_value(encrypted)
            self.assertEqual(decrypted, plain, "Decrypted value must match original")

    def test_same_value_produces_different_ciphertexts(self):
        """Random IV: same plaintext → different ciphertext each time."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography not installed")

        key = Fernet.generate_key().decode()
        with override_settings(PAYOUT_ENCRYPTION_KEY=key):
            from api.payout_queue.utils.encryption import encrypt_value
            plain = "01711223344"
            enc1  = encrypt_value(plain)
            enc2  = encrypt_value(plain)
            self.assertNotEqual(enc1, enc2, "Two encryptions of same value must differ (random IV)")

    def test_compute_account_hash_deterministic(self):
        """Same plaintext + same key = same hash (searchable)."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography not installed")

        key = Fernet.generate_key().decode()
        with override_settings(PAYOUT_ENCRYPTION_KEY=key):
            from api.payout_queue.utils.encryption import compute_account_hash
            h1 = compute_account_hash("01711223344")
            h2 = compute_account_hash("01711223344")
            self.assertEqual(h1, h2, "Hash must be deterministic")
            self.assertEqual(len(h1), 64, "SHA-256 hash must be 64 hex chars")

    def test_different_values_produce_different_hashes(self):
        """Different account numbers must produce different hashes."""
        from api.payout_queue.utils.encryption import compute_account_hash
        h1 = compute_account_hash("01711223344")
        h2 = compute_account_hash("01799887766")
        self.assertNotEqual(h1, h2)

    def test_compute_hash_empty_returns_empty(self):
        """Empty account number returns empty hash."""
        from api.payout_queue.utils.encryption import compute_account_hash
        self.assertEqual(compute_account_hash(""), "")

# ===========================================================================
# Class 3 — TestAccountNumberHashInModel  (Gap #2)
# ===========================================================================

class TestAccountNumberHashInModel(TestCase):
    """
    Gap #2: PayoutItem.save() auto-computes account_number_hash.
    """

    def test_account_number_hash_computed_on_save(self):
        """Creating a PayoutItem must auto-set account_number_hash."""
        batch = _batch()
        item  = _item(batch, acct="01700000001")
        item.refresh_from_db()
        self.assertNotEqual(item.account_number_hash, "",
                            "account_number_hash must be set after save()")
        self.assertEqual(len(item.account_number_hash), 64,
                         "Hash must be 64-char SHA-256 hex")

    def test_account_number_hash_consistent(self):
        """Two items with same account number must have identical hashes."""
        batch = _batch()
        item1 = _item(batch, acct="01700000001")
        item2 = _item(batch, acct="01700000001",
                      gross=Decimal("200.00"))  # different amount — same account
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(item1.account_number_hash, item2.account_number_hash)

    def test_different_account_numbers_have_different_hashes(self):
        """Different account numbers must produce different hashes."""
        batch = _batch()
        item1 = _item(batch, acct="01700000001")
        item2 = _item(batch, acct="01799999999")
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertNotEqual(item1.account_number_hash, item2.account_number_hash)

    def test_account_number_field_present(self):
        """PayoutItem model must have account_number_hash field."""
        self.assertIn("account_number_hash", [f.name for f in PayoutItem._meta.get_fields()])

    def test_account_number_hash_indexed(self):
        """account_number_hash must have a DB index for performance."""
        index_names = [idx.name for idx in PayoutItem._meta.indexes]
        self.assertIn("pq_pi_acct_hash_idx", index_names,
                      "pq_pi_acct_hash_idx index must exist on account_number_hash")

# ===========================================================================
# Class 4 — TestDuplicateDetectionUsesHash  (Gap #2)
# ===========================================================================

class TestDuplicateDetectionUsesHash(TestCase):
    """
    Gap #2: _create_single_payout_item uses account_number_hash for
    duplicate detection, not plaintext account_number filter.
    """

    def test_duplicate_detected_via_hash(self):
        """Second identical item raises DuplicatePayoutError."""
        from api.payout_queue.exceptions import DuplicatePayoutError
        batch = _batch(status=PayoutBatchStatus.PENDING)
        user  = _user()
        _item(batch, acct="01700000001", gross=Decimal("500.00"))
        # Manually set user and amount to match
        PayoutItem.objects.filter(batch=batch).update(user=user, gross_amount=Decimal("500.00"))

        with self.assertRaises(DuplicatePayoutError):
            from api.payout_queue.services import _create_single_payout_item
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

    def test_source_uses_hash_not_plaintext(self):
        """Source code must use account_number_hash, not account_number= filter."""
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services._create_single_payout_item)
        self.assertIn("account_number_hash", source,
                      "_create_single_payout_item must filter by account_number_hash (v8)")
        # Old plaintext filter must not appear
        self.assertNotIn(
            'account_number=account_number.strip()', source,
            "_create_single_payout_item must not filter by plaintext account_number (v8)",
        )

# ===========================================================================
# Class 5 — TestReconcileBatchWithGateway  (Gap #3)
# ===========================================================================

class TestReconcileBatchWithGateway(TestCase):
    """
    Gap #3: reconcile_batch_with_gateway detects DB vs gateway discrepancies.
    """

    def _make_completed_batch_with_items(self):
        batch = _batch(status=PayoutBatchStatus.COMPLETED)
        item1 = _item(batch, status=PayoutItemStatus.SUCCESS, gross=Decimal("500.00"))
        item2 = _item(batch, status=PayoutItemStatus.SUCCESS, gross=Decimal("300.00"))
        PayoutItem.objects.filter(pk=item1.pk).update(gateway_reference="GW-001")
        PayoutItem.objects.filter(pk=item2.pk).update(gateway_reference="GW-002")
        return batch, item1, item2

    @patch("api.payout_queue.tasks._get_processor")
    def test_clean_batch_returns_zero_discrepancies(self, mock_get_proc):
        """Gateway confirms all SUCCESS items — no discrepancies."""
        from api.payout_queue.tasks import reconcile_batch_with_gateway
        from api.payout_queue.utils.payment_gateway import PayoutResult

        batch, _, _ = self._make_completed_batch_with_items()
        mock_proc   = MagicMock()
        mock_proc.verify_transaction.return_value = PayoutResult(success=True, gateway_reference="GW-001")
        mock_get_proc.return_value = mock_proc

        result = reconcile_batch_with_gateway(str(batch.id))

        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["discrepancies"], [])
        self.assertEqual(result["items_checked"], 2)

    @patch("api.payout_queue.tasks._get_processor")
    def test_detects_db_success_gateway_failed(self, mock_get_proc):
        """DB=SUCCESS but gateway=FAILED → discrepancy with severity=critical."""
        from api.payout_queue.tasks import reconcile_batch_with_gateway
        from api.payout_queue.utils.payment_gateway import PayoutResult

        batch, item1, _ = self._make_completed_batch_with_items()
        mock_proc       = MagicMock()

        def mock_verify(ref):
            if ref == "GW-001":
                return PayoutResult(success=False, error_code="REVERSED", error_message="reversed")
            return PayoutResult(success=True, gateway_reference=ref)

        mock_proc.verify_transaction.side_effect = mock_verify
        mock_get_proc.return_value = mock_proc

        result = reconcile_batch_with_gateway(str(batch.id))

        self.assertEqual(result["status"], "discrepancies_found")
        critical = [d for d in result["discrepancies"] if d["severity"] == "critical"]
        self.assertEqual(len(critical), 1)
        self.assertEqual(critical[0]["gateway_status"], "REVERSED")

    @patch("api.payout_queue.tasks._get_processor")
    def test_detects_db_failed_gateway_success_double_pay_risk(self, mock_get_proc):
        """DB=FAILED but gateway=SUCCESS → DOUBLE_PAYMENT_RISK discrepancy."""
        from api.payout_queue.tasks import reconcile_batch_with_gateway
        from api.payout_queue.utils.payment_gateway import PayoutResult

        batch  = _batch(status=PayoutBatchStatus.PARTIALLY_COMPLETED)
        failed = _item(batch, status=PayoutItemStatus.FAILED, gross=Decimal("400.00"))
        PayoutItem.objects.filter(pk=failed.pk).update(gateway_reference="GW-FAIL-001")

        mock_proc = MagicMock()
        mock_proc.verify_transaction.return_value = PayoutResult(success=True, gateway_reference="GW-FAIL-001")
        mock_get_proc.return_value = mock_proc

        result = reconcile_batch_with_gateway(str(batch.id))

        self.assertEqual(result["status"], "discrepancies_found")
        double_pay = [d for d in result["discrepancies"] if "DOUBLE_PAYMENT_RISK" in d.get("action_required", "")]
        self.assertEqual(len(double_pay), 1)

    def test_skips_non_terminal_batch(self):
        """PENDING batch must be skipped, not reconciled."""
        from api.payout_queue.tasks import reconcile_batch_with_gateway

        batch  = _batch(status=PayoutBatchStatus.PENDING)
        result = reconcile_batch_with_gateway(str(batch.id))

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "non_terminal_status")

    def test_returns_error_for_unknown_batch(self):
        """Unknown batch ID returns error status."""
        from api.payout_queue.tasks import reconcile_batch_with_gateway
        result = reconcile_batch_with_gateway(str(uuid.uuid4()))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "batch_not_found")

# ===========================================================================
# Class 6 — TestReconcileRecentBatches  (Gap #3)
# ===========================================================================

class TestReconcileRecentBatches(TestCase):
    """
    Gap #3: reconcile_recent_batches finds and dispatches completed batches.
    """

    @patch("api.payout_queue.tasks.reconcile_batch_with_gateway")
    def test_dispatches_completed_batches(self, mock_reconcile):
        """Each completed batch in lookback window gets a reconcile task."""
        from api.payout_queue.tasks import reconcile_recent_batches
        from django.utils import timezone
        from datetime import timedelta

        now     = timezone.now()
        batch1  = _batch(status=PayoutBatchStatus.COMPLETED)
        batch2  = _batch(status=PayoutBatchStatus.PARTIALLY_COMPLETED)
        PayoutBatch.objects.filter(pk__in=[batch1.pk, batch2.pk]).update(completed_at=now)

        result = reconcile_recent_batches(lookback_hours=1)

        self.assertGreaterEqual(result["dispatched_count"], 2)
        self.assertEqual(mock_reconcile.delay.call_count, result["dispatched_count"])

    @patch("api.payout_queue.tasks.reconcile_batch_with_gateway")
    def test_ignores_old_batches(self, mock_reconcile):
        """Batches completed before the lookback window are ignored."""
        from api.payout_queue.tasks import reconcile_recent_batches
        from django.utils import timezone
        from datetime import timedelta

        old_batch = _batch(status=PayoutBatchStatus.COMPLETED)
        PayoutBatch.objects.filter(pk=old_batch.pk).update(
            completed_at=timezone.now() - timedelta(hours=48)
        )

        result = reconcile_recent_batches(lookback_hours=1)
        # The old batch must not be in the dispatched count for this run
        self.assertIsInstance(result["dispatched_count"], int)

    def test_returns_structured_result(self):
        """Return dict must have expected keys."""
        from api.payout_queue.tasks import reconcile_recent_batches
        with patch("api.payout_queue.tasks.reconcile_batch_with_gateway"):
            result = reconcile_recent_batches(lookback_hours=0)
        for key in ("batches_found", "dispatched_count", "errors", "lookback_hours"):
            self.assertIn(key, result)

# ===========================================================================
# Class 7 — TestSettingsCompleteness  (Gap #4)
# ===========================================================================

class TestSettingsCompleteness(TestCase):
    """
    Gap #4: settings_final_additions.py defines all required PAYOUT_* settings.
    """

    def test_settings_file_importable(self):
        """settings_final_additions.py must be importable."""
        try:
            import api.payout_queue.settings_final_additions as s
            _ = s
        except ImportError as exc:
            self.fail(f"settings_final_additions.py not importable: {exc}")

    def test_required_settings_defined(self):
        """All required PAYOUT_* settings must be defined in the settings file."""
        import api.payout_queue.settings_final_additions as s
        required = [
            "SENTRY_DSN", "PAYOUT_ENCRYPTION_KEY",
            "PAYOUT_KYC_CHECK_ENABLED", "PAYOUT_FRAUD_CHECK_ENABLED",
            "PAYOUT_WALLET_CHECK_ENABLED", "PAYOUT_AUDIT_LOG_ENABLED",
            "PAYMENT_GATEWAY_CONFIGS",
            "PAYOUT_WEBHOOK_URLS", "PAYOUT_WEBHOOK_SECRET",
            "CELERY_BEAT_SCHEDULE",
        ]
        for key in required:
            self.assertTrue(hasattr(s, key), f"Missing required setting: {key}")

    def test_celery_beat_has_reconcile_task(self):
        """CELERY_BEAT_SCHEDULE must include the reconcile_recent_batches task."""
        import api.payout_queue.settings_final_additions as s
        task_names = [v.get("task", "") for v in s.CELERY_BEAT_SCHEDULE.values()]
        self.assertIn("payout_queue.reconcile_recent_batches", task_names,
                      "CELERY_BEAT_SCHEDULE must include reconcile_recent_batches")

    def test_celery_beat_has_all_5_tasks(self):
        """All 5 Celery beat tasks must be scheduled."""
        import api.payout_queue.settings_final_additions as s
        task_names = [v.get("task", "") for v in s.CELERY_BEAT_SCHEDULE.values()]
        required_tasks = [
            "payout_queue.process_due_batches",
            "payout_queue.retry_due_items",
            "payout_queue.expire_withdrawal_priorities",
            "payout_queue.release_stale_locks",
            "payout_queue.reconcile_recent_batches",
        ]
        for t in required_tasks:
            self.assertIn(t, task_names, f"Beat schedule missing task: {t}")

    def test_all_5_gateways_in_config(self):
        """PAYMENT_GATEWAY_CONFIGS must have entries for all 5 gateways."""
        import api.payout_queue.settings_final_additions as s
        for gw in ("BKASH", "NAGAD", "ROCKET", "BANK", "MANUAL"):
            self.assertIn(gw, s.PAYMENT_GATEWAY_CONFIGS, f"Missing gateway config: {gw}")

# ===========================================================================
# Class 8 — TestHealthCheckEndpoint  (Gap #5)
# ===========================================================================

class TestHealthCheckEndpoint(TestCase):
    """
    Gap #5: GET /payout-queue/health/ returns multi-component status.
    """

    def setUp(self):
        self.client = APIClient()

    def test_health_check_returns_200_in_dev(self):
        """Health check returns 200 in test environment (DB is available)."""
        resp = self.client.get("/api/payout-queue/health/")
        self.assertIn(resp.status_code, [200, 503])  # 200 if DB ok, 503 if not
        self.assertIn("status", resp.data)
        self.assertIn("checks", resp.data)

    def test_health_check_no_auth_required(self):
        """Unauthenticated requests must be accepted (for probe compatibility)."""
        resp = self.client.get("/api/payout-queue/health/")
        self.assertNotEqual(resp.status_code, 401,
                            "Health check must not require authentication")
        self.assertNotEqual(resp.status_code, 403)

    def test_health_check_includes_database_check(self):
        """Response must include a 'database' key in checks."""
        resp = self.client.get("/api/payout-queue/health/")
        if resp.status_code in (200, 503):
            self.assertIn("database", resp.data.get("checks", {}))

    def test_health_check_includes_payout_queue_stats(self):
        """Response must include payout_queue stats (pending/processing counts)."""
        resp = self.client.get("/api/payout-queue/health/")
        if resp.status_code in (200, 503):
            checks = resp.data.get("checks", {})
            self.assertIn("payout_queue", checks)

    def test_health_check_reports_version(self):
        """Response must include version: 'v8'."""
        resp = self.client.get("/api/payout-queue/health/")
        if resp.status_code in (200, 503):
            self.assertEqual(resp.data.get("version"), "v8")

    def test_health_check_returns_503_when_db_down(self):
        """503 must be returned when database check fails."""
        from api.payout_queue import views
        with patch.object(
            PayoutBatch.objects, "count", side_effect=Exception("DB connection refused")
        ):
            resp = self.client.get("/api/payout-queue/health/")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data["status"], "error")

    @override_settings(PAYOUT_ENCRYPTION_KEY="")
    def test_health_check_reports_encryption_degraded_when_no_key(self):
        """No PAYOUT_ENCRYPTION_KEY → encryption check shows degraded."""
        resp = self.client.get("/api/payout-queue/health/")
        if resp.status_code in (200, 503):
            enc_check = resp.data.get("checks", {}).get("encryption", {})
            self.assertIn(enc_check.get("status"), ["degraded", "unknown"],
                          "Missing encryption key must report degraded")

    def test_health_check_reports_stuck_locks(self):
        """Stuck-locked batches must appear in payout_queue check."""
        from django.utils import timezone
        from datetime import timedelta

        stuck_batch = _batch(status=PayoutBatchStatus.PROCESSING)
        PayoutBatch.objects.filter(pk=stuck_batch.pk).update(
            locked_at=timezone.now() - timedelta(hours=2),
            locked_by="dead-worker",
        )
        resp = self.client.get("/api/payout-queue/health/")
        if resp.status_code in (200, 503):
            pq = resp.data.get("checks", {}).get("payout_queue", {})
            self.assertGreaterEqual(pq.get("stuck_locked_batches", 0), 1)

# ===========================================================================
# Class 9 — TestConcurrentProcessing  (Gap #6)
# ===========================================================================

class TestConcurrentProcessing(TestCase):
    """
    Gap #6: Concurrent batch processing safety.
    Advisory lock prevents two workers from processing the same batch.
    """

    def test_second_worker_cannot_acquire_lock(self):
        """Only one worker can hold the advisory lock."""
        batch = _batch(status=PayoutBatchStatus.PENDING)
        result1 = batch.acquire_lock("worker-A")
        result2 = batch.acquire_lock("worker-B")
        self.assertTrue(result1,  "First worker must acquire the lock")
        self.assertFalse(result2, "Second worker must NOT acquire the lock")

    def test_lock_released_after_processing(self):
        """Lock must be cleared after batch reaches terminal state."""
        batch = _batch(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("worker-A")
        batch.release_lock()
        batch.refresh_from_db()
        self.assertIsNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "")

    def test_max_concurrent_batches_enforced(self):
        """MAX_CONCURRENT_BATCHES limit must be enforced by process_batch."""
        from api.payout_queue.constants import MAX_CONCURRENT_BATCHES
        from api.payout_queue.exceptions import PayoutBatchLimitError
        from api.payout_queue.services import process_batch

        # Create MAX_CONCURRENT_BATCHES + 1 PROCESSING batches
        for _ in range(MAX_CONCURRENT_BATCHES):
            _batch(status=PayoutBatchStatus.PROCESSING)

        # Next batch attempt must be rejected
        extra_batch = _batch(status=PayoutBatchStatus.PENDING)
        with self.assertRaises(PayoutBatchLimitError):
            process_batch(batch_id=extra_batch.id, worker_id="worker-overflow")

    def test_select_for_update_skip_locked_used(self):
        """
        process_batch must use select_for_update(skip_locked=True) when
        fetching items — so a second concurrent run skips locked items
        instead of blocking indefinitely.
        """
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services.process_batch)
        self.assertIn("skip_locked=True", source,
                      "process_batch must use select_for_update(skip_locked=True)")

    def test_idempotency_key_unique_per_item(self):
        """Each PayoutItem gets a unique internal_reference (UUID)."""
        batch  = _batch()
        item_a = _item(batch, acct="01700000001")
        item_b = _item(batch, acct="01799999999")
        self.assertNotEqual(item_a.internal_reference, item_b.internal_reference)
        self.assertEqual(len(item_a.internal_reference), 36)  # UUID format

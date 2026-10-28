"""
payout_queue/tests/test_v7_dry.py

DRY v7 — Missing coverage tests.

Covers every new pattern introduced in DRY v7 that had zero prior coverage:

  Class 1  — TestAppendOnlyModelMixin
      Both WithdrawalPriority and BulkProcessLog still enforce append-only
      via the shared AppendOnlyModel mixin (not duplicated save() blocks).
      Error message uses the model-specific _append_only_label.

  Class 2  — TestLockReleaseFieldsConstant
      PayoutBatch._LOCK_RELEASE_FIELDS drives release_lock() and
      mark_failed_with_release(); the dict values are authoritative.

  Class 3  — TestWebhookRetryDelay
      _webhook_retry_delay(retries) returns 30 / 60 / 120 for 0 / 1 / 2 retries.

  Class 4  — TestBkashAppHeaders
      BkashProcessor._app_headers(token) returns the correct dict.
      _execute_payment and _query_payment both use it (not inline dicts).

  Class 5  — TestRocketBuildHeaders
      RocketProcessor._build_headers() returns the correct dict.
      _post_payment and verify_transaction both use it.

  Class 6  — TestBasePayoutCommand
      validate_shared_options raises on dry_run + async combo.
      make_worker_id: uses provided value / generates with correct prefix.
      add_arguments: shared flags registered on both subcommands.

  Class 7  — TestGetBatchLocked
      _get_batch_locked: returns batch / raises PayoutBatchNotFoundError
      for missing pk / raises for None.

  Class 8  — TestGetItemLocked
      _get_item_locked: returns item / raises PayoutItemNotFoundError
      for missing pk / raises for None.

  Class 9  — TestDoTransitionBatch
      hold_payout_batch and resume_payout_batch delegate body to
      _do_transition_batch; batch ends in expected status.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.payout_queue.choices import (
    PayoutBatchStatus, PayoutItemStatus,
    PaymentGateway, PriorityLevel,
    WithdrawalPriorityReason,
)
from api.payout_queue.exceptions import (
    PayoutBatchNotFoundError, PayoutItemNotFoundError, PayoutQueueError,
)
from api.payout_queue.models import (
    PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_staff(**kwargs):
    return User.objects.create_user(
        username=f"staff_{uuid.uuid4().hex[:8]}", password="x", is_staff=True, **kwargs
    )

def _make_user(**kwargs):
    return User.objects.create_user(
        username=f"u_{uuid.uuid4().hex[:8]}", password="x", **kwargs
    )

def _make_batch(*, status=PayoutBatchStatus.PENDING,
                gateway=PaymentGateway.BKASH,
                total_amount=Decimal("1000.00"),
                tenant_id=None, **kw) -> PayoutBatch:
    return PayoutBatch.objects.create(
        name="DRY-test batch",
        gateway=gateway,
        status=status,
        priority=PriorityLevel.NORMAL,
        total_amount=total_amount,
        total_fee=Decimal("20.00"),
        net_amount=Decimal("980.00"),
        item_count=2,
        created_by=_make_staff(),
        tenant_id=tenant_id,
        **kw,
    )

def _make_item(batch, *, status=PayoutItemStatus.QUEUED,
               gross_amount=Decimal("500.00")) -> PayoutItem:
    return PayoutItem.objects.create(
        batch=batch,
        user=_make_user(),
        gateway=batch.gateway,
        account_number="01700000001",
        gross_amount=gross_amount,
        fee_amount=Decimal("10.00"),
        net_amount=gross_amount - Decimal("10.00"),
        internal_reference=str(uuid.uuid4()),
        status=status,
    )

# ===========================================================================
# Class 1 — TestAppendOnlyModelMixin
# ===========================================================================

class TestAppendOnlyModelMixin(TestCase):
    """
    DRY v7: AppendOnlyModel mixin drives both WithdrawalPriority and
    BulkProcessLog. Tests confirm the mixin — not individual model overrides.
    """

    # ── WithdrawalPriority ────────────────────────────────────────────

    def test_withdrawal_priority_cannot_be_updated(self):
        """WithdrawalPriority.save() raises ValidationError when pk is set."""
        user = _make_user()
        wp   = WithdrawalPriority.objects.create(
            user=user,
            priority=PriorityLevel.NORMAL,
            reason=WithdrawalPriorityReason.MANUAL_REVIEW,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            wp.save()

    def test_withdrawal_priority_error_message_uses_label(self):
        """Error message should contain 'WithdrawalPriority' (from _append_only_label)."""
        user = _make_user()
        wp   = WithdrawalPriority.objects.create(
            user=user,
            priority=PriorityLevel.NORMAL,
            reason=WithdrawalPriorityReason.MANUAL_REVIEW,
            is_active=True,
        )
        try:
            wp.save()
            self.fail("Expected ValidationError not raised.")
        except ValidationError as exc:
            self.assertIn("WithdrawalPriority", str(exc))

    def test_withdrawal_priority_new_record_creates_fine(self):
        """Creating a new WithdrawalPriority (pk=None) must NOT raise."""
        user = _make_user()
        wp   = WithdrawalPriority(
            user=user,
            priority=PriorityLevel.NORMAL,
            reason=WithdrawalPriorityReason.MANUAL_REVIEW,
            is_active=True,
        )
        self.assertIsNone(wp.pk)
        wp.save()
        self.assertIsNotNone(wp.pk)

    # ── BulkProcessLog ────────────────────────────────────────────────

    def test_bulk_process_log_cannot_be_updated(self):
        """BulkProcessLog.save() raises ValidationError when pk is set."""
        batch = _make_batch()
        log   = BulkProcessLog.objects.create(
            batch=batch,
            status="SUCCESS",
            items_attempted=1,
            items_succeeded=1,
            items_failed=0,
            items_skipped=0,
        )
        with self.assertRaises(ValidationError):
            log.save()

    def test_bulk_process_log_error_message_uses_label(self):
        """Error message should contain 'BulkProcessLog' (from _append_only_label)."""
        batch = _make_batch()
        log   = BulkProcessLog.objects.create(
            batch=batch,
            status="SUCCESS",
            items_attempted=1,
            items_succeeded=1,
            items_failed=0,
            items_skipped=0,
        )
        try:
            log.save()
            self.fail("Expected ValidationError not raised.")
        except ValidationError as exc:
            self.assertIn("BulkProcessLog", str(exc))

    def test_bulk_process_log_new_record_creates_fine(self):
        """Creating a new BulkProcessLog (pk=None) must NOT raise."""
        batch = _make_batch()
        log   = BulkProcessLog(
            batch=batch,
            status="SUCCESS",
            items_attempted=1,
            items_succeeded=1,
            items_failed=0,
            items_skipped=0,
        )
        self.assertIsNone(log.pk)
        log.save()
        self.assertIsNotNone(log.pk)

    def test_both_models_share_same_mixin(self):
        """Both models must inherit AppendOnlyModel (not independent save() overrides)."""
        from api.payout_queue.models import AppendOnlyModel
        self.assertTrue(issubclass(WithdrawalPriority, AppendOnlyModel))
        self.assertTrue(issubclass(BulkProcessLog, AppendOnlyModel))

    def test_append_only_label_differs_per_model(self):
        """Each model must have its own _append_only_label string."""
        self.assertEqual(WithdrawalPriority._append_only_label, "WithdrawalPriority")
        self.assertEqual(BulkProcessLog._append_only_label, "BulkProcessLog")

# ===========================================================================
# Class 2 — TestLockReleaseFieldsConstant
# ===========================================================================

class TestLockReleaseFieldsConstant(TestCase):
    """
    DRY v7: PayoutBatch._LOCK_RELEASE_FIELDS is the single definition
    of lock-clearing values used by release_lock() and
    mark_failed_with_release().
    """

    def test_lock_release_fields_keys(self):
        """Constant must contain locked_at and locked_by keys."""
        fields = PayoutBatch._LOCK_RELEASE_FIELDS
        self.assertIn("locked_at", fields)
        self.assertIn("locked_by", fields)

    def test_lock_release_fields_values(self):
        """locked_at must be None; locked_by must be empty string."""
        fields = PayoutBatch._LOCK_RELEASE_FIELDS
        self.assertIsNone(fields["locked_at"])
        self.assertEqual(fields["locked_by"], "")

    def test_release_lock_clears_both_fields(self):
        """release_lock() must set locked_at=None and locked_by='' on the row."""
        from django.utils import timezone
        batch = _make_batch()
        PayoutBatch.objects.filter(pk=batch.pk).update(
            locked_at=timezone.now(),
            locked_by="worker-001",
        )
        batch.refresh_from_db()
        self.assertIsNotNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "worker-001")

        batch.release_lock()
        batch.refresh_from_db()
        self.assertIsNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "")

    def test_mark_failed_with_release_clears_both_fields(self):
        """mark_failed_with_release() must also clear locked_at and locked_by."""
        from django.utils import timezone
        batch = _make_batch(status=PayoutBatchStatus.PROCESSING)
        PayoutBatch.objects.filter(pk=batch.pk).update(
            locked_at=timezone.now(),
            locked_by="worker-002",
        )
        batch.refresh_from_db()

        batch.mark_failed_with_release("test error")
        batch.refresh_from_db()
        self.assertIsNone(batch.locked_at)
        self.assertEqual(batch.locked_by, "")
        self.assertEqual(batch.status, PayoutBatchStatus.FAILED)

# ===========================================================================
# Class 3 — TestWebhookRetryDelay
# ===========================================================================

class TestWebhookRetryDelay(TestCase):
    """
    DRY v7: _webhook_retry_delay() is the single definition of the
    exponential back-off formula used by deliver_webhook_event().
    """

    def setUp(self):
        from api.payout_queue.tasks import _webhook_retry_delay
        self._fn = _webhook_retry_delay

    def test_retries_0_returns_30(self):
        """First attempt (0 previous retries) → 30s delay."""
        self.assertEqual(self._fn(0), 30)

    def test_retries_1_returns_60(self):
        """Second attempt → 60s delay."""
        self.assertEqual(self._fn(1), 60)

    def test_retries_2_returns_120(self):
        """Third attempt → 120s delay."""
        self.assertEqual(self._fn(2), 120)

    def test_always_positive(self):
        """Delay must always be a positive integer."""
        for n in range(5):
            result = self._fn(n)
            self.assertIsInstance(result, int)
            self.assertGreater(result, 0)

    def test_delay_doubles_each_retry(self):
        """Each retry should double the previous delay (exponential back-off)."""
        prev = self._fn(0)
        for n in range(1, 4):
            curr = self._fn(n)
            self.assertEqual(curr, prev * 2)
            prev = curr

    def test_deliver_webhook_uses_helper_not_inline_formula(self):
        """deliver_webhook_event must call _webhook_retry_delay, not inline formula."""
        import inspect
        import api.payout_queue.tasks as tasks_module
        source = inspect.getsource(tasks_module.deliver_webhook_event)
        # The inline formula (hardcoded multiplication) must not appear
        self.assertNotIn("30 * (2 **", source,
            "deliver_webhook_event still contains inline formula — "
            "should use _webhook_retry_delay()")
        self.assertIn("_webhook_retry_delay", source)

# ===========================================================================
# Class 4 — TestBkashAppHeaders
# ===========================================================================

class TestBkashAppHeaders(TestCase):
    """
    DRY v7: BkashProcessor._app_headers(token) replaces the two identical
    inline dicts in _execute_payment and _query_payment.
    """

    def _make_processor(self):
        from api.payout_queue.processors.bkash import BkashProcessor
        return BkashProcessor({
            "app_key":    "test_app_key",
            "app_secret": "test_secret",
            "username":   "test_user",
            "password":   "test_pass",
            "base_url":   "https://tokenized.sandbox.bka.sh/v1.2.0-beta",
        })

    def test_app_headers_structure(self):
        """_app_headers must return Content-Type, Authorization, X-APP-Key."""
        p       = self._make_processor()
        headers = p._app_headers("Bearer mytoken123")
        self.assertEqual(headers["Content-Type"],  "application/json")
        self.assertEqual(headers["Authorization"], "Bearer mytoken123")
        self.assertEqual(headers["X-APP-Key"],     "test_app_key")

    def test_app_headers_uses_config_app_key(self):
        """X-APP-Key must come from self.config['app_key']."""
        from api.payout_queue.processors.bkash import BkashProcessor
        p       = BkashProcessor({"app_key": "MY_KEY", "app_secret": "s",
                                  "username": "u", "password": "p",
                                  "base_url": "http://x"})
        headers = p._app_headers("tok")
        self.assertEqual(headers["X-APP-Key"], "MY_KEY")

    @patch("api.payout_queue.processors.bkash.requests.post")
    def test_execute_payment_uses_app_headers(self, mock_post):
        """_execute_payment must call self._app_headers, not build headers inline."""
        p   = self._make_processor()
        mock_post.return_value                  = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"statusCode": "0000", "trxID": "T1"}

        with patch.object(p, "_app_headers", wraps=p._app_headers) as spy:
            p._execute_payment(
                token="tok",
                account_number="01700000001",
                amount=Decimal("100.00"),
                reference="ref-001",
            )
            spy.assert_called_once_with("tok")

    @patch("api.payout_queue.processors.bkash.requests.post")
    def test_query_payment_uses_app_headers(self, mock_post):
        """_query_payment must call self._app_headers, not build headers inline."""
        p = self._make_processor()
        mock_post.return_value                   = MagicMock()
        mock_post.return_value.raise_for_status  = MagicMock()
        mock_post.return_value.json.return_value = {"transactionStatus": "Completed"}

        with patch.object(p, "_app_headers", wraps=p._app_headers) as spy:
            p._query_payment(token="tok", trx_id="TRX123")
            spy.assert_called_once_with("tok")

    def test_get_grant_token_does_not_use_app_headers(self):
        """_get_grant_token uses credential headers (username+pass), NOT _app_headers."""
        import inspect
        from api.payout_queue.processors.bkash import BkashProcessor
        source = inspect.getsource(BkashProcessor._get_grant_token)
        # Grant token uses username/password, not app_headers
        self.assertIn("username", source)
        self.assertIn("password", source)
        self.assertNotIn("_app_headers", source)

# ===========================================================================
# Class 5 — TestRocketBuildHeaders
# ===========================================================================

class TestRocketBuildHeaders(TestCase):
    """
    DRY v7: RocketProcessor._build_headers() replaces the two identical
    inline dicts in _post_payment and verify_transaction.
    Mirrors the existing pattern in nagad.py.
    """

    def _make_processor(self):
        from api.payout_queue.processors.rocket import RocketProcessor
        return RocketProcessor({
            "api_key":          "rocket_test_key",
            "merchant_number":  "01800000000",
            "base_url":         "https://rocket.example.com",
        })

    def test_build_headers_structure(self):
        """_build_headers must return Authorization + Content-Type."""
        p       = self._make_processor()
        headers = p._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer rocket_test_key")
        self.assertEqual(headers["Content-Type"],  "application/json")

    def test_build_headers_uses_config_api_key(self):
        """Authorization value must come from self.config['api_key']."""
        from api.payout_queue.processors.rocket import RocketProcessor
        p       = RocketProcessor({"api_key": "MY_API_KEY", "merchant_number": "0",
                                   "base_url": "http://x"})
        headers = p._build_headers()
        self.assertEqual(headers["Authorization"], "Bearer MY_API_KEY")

    @patch("api.payout_queue.processors.rocket.requests.post")
    def test_post_payment_uses_build_headers(self, mock_post):
        """_post_payment must call self._build_headers(), not inline dict."""
        p = self._make_processor()
        mock_post.return_value                   = MagicMock()
        mock_post.return_value.raise_for_status  = MagicMock()
        mock_post.return_value.json.return_value = {"status_code": "000",
                                                    "transaction_id": "R1"}
        with patch.object(p, "_build_headers", wraps=p._build_headers) as spy:
            p._post_payment(
                account_number="01700000001",
                amount=Decimal("200.00"),
                reference="ref-002",
            )
            spy.assert_called_once()

    @patch("api.payout_queue.processors.rocket.requests.post")
    def test_verify_transaction_uses_build_headers(self, mock_post):
        """verify_transaction must call self._build_headers(), not inline dict."""
        p = self._make_processor()
        mock_post.return_value                   = MagicMock()
        mock_post.return_value.raise_for_status  = MagicMock()
        mock_post.return_value.json.return_value = {"status_code": "000"}
        with patch.object(p, "_build_headers", wraps=p._build_headers) as spy:
            p.verify_transaction("TXN123")
            spy.assert_called_once()

    def test_no_inline_header_dict_in_post_payment(self):
        """_post_payment source must not contain the hardcoded header string."""
        import inspect
        from api.payout_queue.processors.rocket import RocketProcessor
        source = inspect.getsource(RocketProcessor._post_payment)
        # Must not build headers inline
        self.assertNotIn('"Authorization": f"Bearer', source,
            "_post_payment still builds headers inline — should use _build_headers()")
        self.assertIn("_build_headers", source)

    def test_no_inline_header_dict_in_verify_transaction(self):
        """verify_transaction source must not contain the hardcoded header string."""
        import inspect
        from api.payout_queue.processors.rocket import RocketProcessor
        source = inspect.getsource(RocketProcessor.verify_transaction)
        self.assertNotIn('"Authorization": f"Bearer', source,
            "verify_transaction still builds headers inline — should use _build_headers()")
        self.assertIn("_build_headers", source)

# ===========================================================================
# Class 6 — TestBasePayoutCommand
# ===========================================================================

class TestBasePayoutCommand(TestCase):
    """
    DRY v7: BasePayoutCommand owns the shared --async / --worker-id / --dry-run
    argument definitions and validate_shared_options / make_worker_id helpers.
    """

    def _get_base(self):
        from api.payout_queue.management.commands.base_payout_command import (
            BasePayoutCommand,
        )
        return BasePayoutCommand

    # ── validate_shared_options ───────────────────────────────────────

    def test_validate_raises_when_dry_run_and_async(self):
        """validate_shared_options must raise CommandError for dry_run + async."""
        from django.core.management.base import CommandError
        cmd = self._get_base()()
        with self.assertRaises(CommandError):
            cmd.validate_shared_options({"dry_run": True, "async_mode": True})

    def test_validate_passes_dry_run_only(self):
        """dry_run without async must not raise."""
        cmd = self._get_base()()
        cmd.validate_shared_options({"dry_run": True, "async_mode": False})  # no raise

    def test_validate_passes_async_only(self):
        """async without dry_run must not raise."""
        cmd = self._get_base()()
        cmd.validate_shared_options({"dry_run": False, "async_mode": True})  # no raise

    def test_validate_passes_neither(self):
        """Neither flag set must not raise."""
        cmd = self._get_base()()
        cmd.validate_shared_options({"dry_run": False, "async_mode": False})  # no raise

    # ── make_worker_id ────────────────────────────────────────────────

    def test_make_worker_id_uses_provided_value(self):
        """When --worker-id is supplied, make_worker_id returns it verbatim."""
        cmd = self._get_base()()
        result = cmd.make_worker_id({"worker_id": "my-custom-worker"})
        self.assertEqual(result, "my-custom-worker")

    def test_make_worker_id_generates_default_with_prefix(self):
        """Without --worker-id, make_worker_id generates '<prefix>-<uuid8>'."""
        cmd                          = self._get_base()()
        cmd._default_worker_prefix   = "test-prefix"
        result                       = cmd.make_worker_id({"worker_id": None})
        self.assertTrue(result.startswith("test-prefix-"))
        # UUID suffix should be 8 chars
        suffix = result[len("test-prefix-"):]
        self.assertEqual(len(suffix), 8)

    def test_make_worker_id_empty_string_generates_default(self):
        """Empty string for worker_id is treated as not supplied."""
        cmd                        = self._get_base()()
        cmd._default_worker_prefix = "mgmt"
        result                     = cmd.make_worker_id({"worker_id": ""})
        self.assertTrue(result.startswith("mgmt-"))

    # ── process_payouts inherits correctly ────────────────────────────

    def test_process_payouts_inherits_base(self):
        """process_payouts.Command must be a subclass of BasePayoutCommand."""
        from api.payout_queue.management.commands.base_payout_command import (
            BasePayoutCommand,
        )
        from api.payout_queue.management.commands.process_payouts import Command
        self.assertTrue(issubclass(Command, BasePayoutCommand))

    def test_retry_payouts_inherits_base(self):
        """retry_payouts.Command must be a subclass of BasePayoutCommand."""
        from api.payout_queue.management.commands.base_payout_command import (
            BasePayoutCommand,
        )
        from api.payout_queue.management.commands.retry_payouts import Command
        self.assertTrue(issubclass(Command, BasePayoutCommand))

    def test_process_payouts_worker_prefix(self):
        """process_payouts._default_worker_prefix must be 'mgmt'."""
        from api.payout_queue.management.commands.process_payouts import Command
        self.assertEqual(Command._default_worker_prefix, "mgmt")

    def test_retry_payouts_worker_prefix(self):
        """retry_payouts._default_worker_prefix must be 'retry-mgmt'."""
        from api.payout_queue.management.commands.retry_payouts import Command
        self.assertEqual(Command._default_worker_prefix, "retry-mgmt")

    # ── Shared flags registered by super().add_arguments ─────────────

    def _parser_for(self, command_module_path: str):
        """Return an argparse parser built by the given command's add_arguments."""
        import importlib
        import argparse
        mod = importlib.import_module(command_module_path)
        cmd = mod.Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)
        return parser

    def test_process_payouts_has_async_flag(self):
        parser  = self._parser_for(
            "api.payout_queue.management.commands.process_payouts"
        )
        ns      = parser.parse_args([])
        self.assertFalse(ns.async_mode)

    def test_process_payouts_has_dry_run_flag(self):
        parser = self._parser_for(
            "api.payout_queue.management.commands.process_payouts"
        )
        ns     = parser.parse_args(["--dry-run"])
        self.assertTrue(ns.dry_run)

    def test_retry_payouts_has_async_flag(self):
        parser = self._parser_for(
            "api.payout_queue.management.commands.retry_payouts"
        )
        ns     = parser.parse_args([])
        self.assertFalse(ns.async_mode)

    def test_retry_payouts_has_worker_id_flag(self):
        parser = self._parser_for(
            "api.payout_queue.management.commands.retry_payouts"
        )
        ns     = parser.parse_args(["--worker-id", "my-worker"])
        self.assertEqual(ns.worker_id, "my-worker")

# ===========================================================================
# Class 7 — TestGetBatchLocked
# ===========================================================================

class TestGetBatchLocked(TestCase):
    """
    DRY v7: _get_batch_locked(batch_id) replaced 5× identical
    select_for_update patterns in services.py.
    """

    def setUp(self):
        from api.payout_queue.services import _get_batch_locked
        self._fn = _get_batch_locked

    def test_returns_batch_when_found(self):
        """Must return the PayoutBatch object for a valid pk."""
        batch  = _make_batch()
        result = self._fn(batch.id)
        self.assertEqual(result.id, batch.id)

    def test_raises_not_found_for_missing_pk(self):
        """Non-existent UUID must raise PayoutBatchNotFoundError."""
        fake_id = uuid.uuid4()
        with self.assertRaises(PayoutBatchNotFoundError):
            self._fn(fake_id)

    def test_raises_for_none_batch_id(self):
        """None must raise PayoutBatchNotFoundError (not a generic TypeError)."""
        with self.assertRaises(PayoutBatchNotFoundError):
            self._fn(None)

    def test_error_message_contains_pk(self):
        """Error message must reference the missing pk."""
        fake_id = uuid.uuid4()
        try:
            self._fn(fake_id)
            self.fail("Expected PayoutBatchNotFoundError")
        except PayoutBatchNotFoundError as exc:
            self.assertIn(str(fake_id), str(exc))

    def test_replaces_select_for_update_pattern_in_hold(self):
        """hold_payout_batch must use _get_batch_locked, not inline pattern."""
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services.hold_payout_batch)
        self.assertIn("_get_batch_locked", source)
        # Old pattern must not appear
        self.assertNotIn("select_for_update().get(pk=batch_id)", source)

    def test_replaces_select_for_update_pattern_in_resume(self):
        """resume_payout_batch must use _get_batch_locked."""
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services.resume_payout_batch)
        self.assertNotIn("select_for_update().get(pk=batch_id)", source)

# ===========================================================================
# Class 8 — TestGetItemLocked
# ===========================================================================

class TestGetItemLocked(TestCase):
    """
    DRY v7: _get_item_locked(item_id) replaced 2× identical
    try/except DoesNotExist blocks in skip_payout_item and cancel_payout_item.
    """

    def setUp(self):
        from api.payout_queue.services import _get_item_locked
        self._fn = _get_item_locked

    def test_returns_item_when_found(self):
        """Must return the PayoutItem for a valid pk."""
        batch  = _make_batch()
        item   = _make_item(batch)
        result = self._fn(item.id)
        self.assertEqual(result.id, item.id)

    def test_raises_not_found_for_missing_pk(self):
        """Non-existent UUID must raise PayoutItemNotFoundError."""
        with self.assertRaises(PayoutItemNotFoundError):
            self._fn(uuid.uuid4())

    def test_raises_for_none_item_id(self):
        """None must raise PayoutItemNotFoundError."""
        with self.assertRaises(PayoutItemNotFoundError):
            self._fn(None)

    def test_replaces_pattern_in_skip_payout_item(self):
        """skip_payout_item must use _get_item_locked, not inline try/except."""
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services.skip_payout_item)
        self.assertIn("_get_item_locked", source)
        self.assertNotIn("select_for_update().get(pk=item_id)", source)

    def test_replaces_pattern_in_cancel_payout_item(self):
        """cancel_payout_item must use _get_item_locked."""
        import inspect
        from api.payout_queue import services
        source = inspect.getsource(services.cancel_payout_item)
        self.assertIn("_get_item_locked", source)

# ===========================================================================
# Class 9 — TestDoTransitionBatch
# ===========================================================================

class TestDoTransitionBatch(TestCase):
    """
    DRY v7: _do_transition_batch() is the shared 4-step body used by
    hold_payout_batch() and resume_payout_batch().
    cancel_payout_batch() calls it then adds wallet-refund logic.
    """

    def test_hold_transitions_to_on_hold(self):
        """hold_payout_batch must leave batch in ON_HOLD status."""
        from api.payout_queue import services
        batch = _make_batch(status=PayoutBatchStatus.PENDING)
        result = services.hold_payout_batch(batch_id=batch.id)
        result.refresh_from_db()
        self.assertEqual(result.status, PayoutBatchStatus.ON_HOLD)

    def test_resume_transitions_to_pending(self):
        """resume_payout_batch must leave batch in PENDING status."""
        from api.payout_queue import services
        batch = _make_batch(status=PayoutBatchStatus.ON_HOLD)
        result = services.resume_payout_batch(batch_id=batch.id)
        result.refresh_from_db()
        self.assertEqual(result.status, PayoutBatchStatus.PENDING)

    def test_hold_with_note(self):
        """Custom note must be stored."""
        from api.payout_queue import services
        batch  = _make_batch(status=PayoutBatchStatus.PENDING)
        result = services.hold_payout_batch(
            batch_id=batch.id, note="Waiting for ops approval."
        )
        result.refresh_from_db()
        self.assertIn("Waiting for ops approval.", result.note)

    def test_resume_with_note(self):
        """Custom note must be stored."""
        from api.payout_queue import services
        batch  = _make_batch(status=PayoutBatchStatus.ON_HOLD)
        result = services.resume_payout_batch(
            batch_id=batch.id, note="Ops approved."
        )
        result.refresh_from_db()
        self.assertIn("Ops approved.", result.note)

    def test_hold_raises_for_unknown_batch(self):
        """hold_payout_batch must raise PayoutBatchNotFoundError for unknown id."""
        from api.payout_queue import services
        with self.assertRaises(PayoutBatchNotFoundError):
            services.hold_payout_batch(batch_id=uuid.uuid4())

    def test_resume_raises_for_unknown_batch(self):
        """resume_payout_batch must raise PayoutBatchNotFoundError for unknown id."""
        from api.payout_queue import services
        with self.assertRaises(PayoutBatchNotFoundError):
            services.resume_payout_batch(batch_id=uuid.uuid4())

    def test_do_transition_batch_is_used_by_hold_and_resume(self):
        """
        Source inspection: hold and resume must call _do_transition_batch,
        not contain the inline 4-step pattern themselves.
        """
        import inspect
        from api.payout_queue import services

        for fn in (services.hold_payout_batch, services.resume_payout_batch):
            src = inspect.getsource(fn)
            self.assertIn(
                "_do_transition_batch", src,
                f"{fn.__name__} does not call _do_transition_batch()",
            )

    def test_cancel_calls_do_transition_then_refund_path(self):
        """
        cancel_payout_batch calls _do_transition_batch (for the transition)
        then adds its own wallet-refund block (v6 fix).
        Both must appear in source.
        """
        import inspect
        from api.payout_queue import services
        src = inspect.getsource(services.cancel_payout_batch)
        self.assertIn("_do_transition_batch", src)
        # The wallet-refund path is unique to cancel (not in hold/resume)
        self.assertIn("PAYOUT_WALLET_CHECK_ENABLED", src)

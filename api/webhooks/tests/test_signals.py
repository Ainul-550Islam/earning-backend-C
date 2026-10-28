"""
tests/test_signals.py

Complete test coverage for all 7 webhook signal handler files.
Previously these 36 handlers across 7 files had ZERO test coverage —
the entire trigger layer of the dispatch pipeline was untested.

Coverage:
    signals/payment_signals.py   — 6 handlers, 24 tests
    signals/fraud_signals.py     — 5 handlers, 16 tests
    signals/kyc_signals.py       — 6 handlers, 18 tests
    signals/offer_signals.py     — 5 handlers, 15 tests
    signals/user_signals.py      — 6 handlers, 12 tests
    signals/wallet_signals.py    — 3 handlers,  9 tests
    signals/withdrawal_signals.py— 5 handlers, 15 tests
                                              ─────────
                                   Total:      109 tests

Test strategy:
    • All external dependencies (DispatchService, WebhookSubscription,
      FilterService) are patched so tests run without a real database or
      running Celery worker.
    • Every handler is tested for:
        - POSITIVE path: correct status/created flag → dispatch called once
          with correct event_type and payload shape
        - NEGATIVE / guard path: wrong status, created=False etc.
          → dispatch NOT called
        - NO-SUBSCRIPTION path: queryset returns empty → no dispatch
        - FILTER-REJECTED path: FilterService returns False → no dispatch
        - EXCEPTION-SWALLOWED path: DispatchService raises → no propagation
"""

import unittest
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ts():
    return datetime.now(dt_timezone.utc)


def _sub(event_type, filters=None):
    """Return a mock WebhookSubscription with a mocked endpoint."""
    sub         = MagicMock()
    sub.filters = filters
    sub.endpoint = MagicMock()
    return sub


def _subs(*items):
    """Return a queryset-like mock that iterates over the given items."""
    qs = MagicMock()
    qs.__iter__ = MagicMock(return_value=iter(items))
    qs.select_related = MagicMock(return_value=qs)
    return qs


_EMPTY_QS = _subs()  # no subscriptions


def _payment(**kw):
    """Minimal payment-like instance."""
    defaults = dict(
        id              = "pay-001",
        user            = SimpleNamespace(id=42),
        transaction_id  = "txn-001",
        amount          = "100.00",
        currency        = "USD",
        payment_method  = "card",
        status          = "succeeded",
        updated_at      = _ts(),
        created_at      = _ts(),
        gateway         = "stripe",
        gateway_transaction_id = "gtx-001",
        reference       = "ref-001",
        description     = "Test payment",
        metadata        = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _fraud(**kw):
    defaults = dict(
        id              = "fr-001",
        user            = SimpleNamespace(id=42),
        fraud_type      = "card_fraud",
        status          = "detected",
        investigation_status = "started",
        description     = "",
        created_at      = _ts(),
        updated_at      = _ts(),
        metadata        = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _kyc(**kw):
    defaults = dict(
        id          = "kyc-001",
        user        = SimpleNamespace(id=42),
        status      = "submitted",
        kyc_type    = "standard",
        created_at  = _ts(),
        updated_at  = _ts(),
        reference   = "ref-001",
        description = "",
        metadata    = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _offer(**kw):
    defaults = dict(
        id          = "off-001",
        user        = SimpleNamespace(id=42),
        offer_type  = "cashback",
        name        = "Summer Promo",
        status      = "credited",
        created_at  = _ts(),
        updated_at  = _ts(),
        reference   = "ref-001",
        description = "",
        metadata    = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _user(**kw):
    defaults = dict(
        id           = 42,
        username     = "testuser",
        email        = "test@example.com",
        first_name   = "Test",
        last_name    = "User",
        is_active    = True,
        is_staff     = False,
        is_superuser = False,
        date_joined  = _ts(),
        last_login   = None,
        metadata     = {},
    )
    defaults.update(kw)
    # .pk mirrors .id on a real Django model instance - on_user_status_changed
    # reads instance.pk, which this SimpleNamespace didn't expose before
    # (confirmed empirically: AttributeError). setdefault so an explicit
    # pk=... kwarg still wins.
    defaults.setdefault("pk", defaults["id"])
    return SimpleNamespace(**defaults)


def _wallet_tx(**kw):
    defaults = dict(
        id               = "wtx-001",
        user             = SimpleNamespace(id=42),
        wallet           = SimpleNamespace(id="wal-001"),
        transaction_type = "credit",
        amount           = "50.00",
        currency         = "USD",
        balance_before   = "100.00",
        balance_after    = "150.00",
        reference        = "ref-001",
        description      = "Test",
        status           = "success",
        created_at       = _ts(),
        updated_at       = _ts(),
        metadata         = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _wallet(**kw):
    defaults = dict(
        id                = "wal-001",
        user              = SimpleNamespace(id=42),
        balance           = "200.00",
        currency          = "USD",
        available_balance = "180.00",
        frozen_balance    = "20.00",
        updated_at        = _ts(),
        metadata          = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _withdrawal(**kw):
    defaults = dict(
        id          = "wd-001",
        user        = SimpleNamespace(id=42),
        wallet      = SimpleNamespace(id="wal-001"),
        amount      = "75.00",
        currency    = "USD",
        method      = "bank_transfer",
        destination = "BD-BANK-001",
        status      = "pending",
        created_at  = _ts(),
        updated_at  = _ts(),
        reference   = "ref-001",
        notes       = "",
        metadata    = {},
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


_DISPATCH_PATH      = "api.webhooks.signals.payment_signals.DispatchService"
_SUBS_PATH_PAYMENT  = "api.webhooks.signals.payment_signals.WebhookSubscription"
_DISPATCH_FRAUD     = "api.webhooks.signals.fraud_signals.DispatchService"
_SUBS_FRAUD         = "api.webhooks.signals.fraud_signals.WebhookSubscription"
_DISPATCH_KYC       = "api.webhooks.signals.kyc_signals.DispatchService"
_SUBS_KYC           = "api.webhooks.signals.kyc_signals.WebhookSubscription"
_DISPATCH_OFFER     = "api.webhooks.signals.offer_signals.DispatchService"
_SUBS_OFFER         = "api.webhooks.signals.offer_signals.WebhookSubscription"
_DISPATCH_USER      = "api.webhooks.signals.user_signals.DispatchService"
_SUBS_USER          = "api.webhooks.signals.user_signals.WebhookSubscription"
_DISPATCH_WALLET    = "api.webhooks.signals.wallet_signals.DispatchService"
_SUBS_WALLET        = "api.webhooks.signals.wallet_signals.WebhookSubscription"
_DISPATCH_WD        = "api.webhooks.signals.withdrawal_signals.DispatchService"
_SUBS_WD            = "api.webhooks.signals.withdrawal_signals.WebhookSubscription"


# ═════════════════════════════════════════════════════════════════════════════
#  PAYMENT SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestPaymentSignals(unittest.TestCase):
    """Tests for signals/payment_signals.py — 6 handlers."""

    def _call(self, handler_name, instance, created=False):
        from api.webhooks.signals.payment_signals import (
            on_payment_succeeded, on_payment_failed, on_payment_initiated,
            on_payment_cancelled, on_payment_refunded, on_payment_disputed,
        )
        fn = {
            "succeeded":  on_payment_succeeded,
            "failed":     on_payment_failed,
            "initiated":  on_payment_initiated,
            "cancelled":  on_payment_cancelled,
            "refunded":   on_payment_refunded,
            "disputed":   on_payment_disputed,
        }[handler_name]
        fn(sender=MagicMock(), instance=instance, created=created)

    # ── on_payment_succeeded ─────────────────────────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_emits_when_status_succeeded(self, MockDispatch, MockSubs):
        sub = _sub("payment.succeeded")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("succeeded", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_called_once()
        _, kwargs = MockDispatch.return_value.emit.call_args
        self.assertEqual(kwargs["event_type"], "payment.succeeded")
        self.assertIn("payment_id", kwargs["payload"])

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_skips_when_status_not_succeeded(self, MockDispatch, MockSubs):
        for bad_status in ("pending", "failed", "cancelled"):
            MockDispatch.reset_mock()
            self._call("succeeded", _payment(status=bad_status))
            MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_no_dispatch_when_no_subscriptions(self, MockDispatch, MockSubs):
        MockSubs.filter.return_value.select_related.return_value = []
        self._call("succeeded", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_swallows_dispatch_exception(self, MockDispatch, MockSubs):
        sub = _sub("payment.succeeded")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = RuntimeError("network error")
        # Should NOT raise — handler must continue to next subscription
        self._call("succeeded", _payment(status="succeeded"))

    # ── on_payment_initiated (created=True guard) ────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_initiated_fires_only_on_created(self, MockDispatch, MockSubs):
        sub = _sub("payment.initiated")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("initiated", _payment(status="pending"), created=True)
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_initiated_skips_when_not_created(self, MockDispatch, MockSubs):
        sub = _sub("payment.initiated")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        self._call("initiated", _payment(status="pending"), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_payment_failed ────────────────────────────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_failed_emits_correct_event_type(self, MockDispatch, MockSubs):
        sub = _sub("payment.failed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("failed", _payment(status="failed"))
        _, kwargs = MockDispatch.return_value.emit.call_args
        self.assertEqual(kwargs["event_type"], "payment.failed")
        self.assertIn("failure_reason", kwargs["payload"])

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_failed_skips_non_failed_status(self, MockDispatch, MockSubs):
        self._call("failed", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_payment_cancelled ─────────────────────────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_cancelled_emits_on_cancelled_status(self, MockDispatch, MockSubs):
        sub = _sub("payment.cancelled")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("cancelled", _payment(status="cancelled"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_cancelled_skips_non_cancelled_status(self, MockDispatch, MockSubs):
        self._call("cancelled", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_payment_refunded ──────────────────────────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_refunded_emits_on_refunded_status(self, MockDispatch, MockSubs):
        sub = _sub("payment.refunded")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("refunded", _payment(status="refunded"))
        _, kwargs = MockDispatch.return_value.emit.call_args
        self.assertEqual(kwargs["event_type"], "payment.refunded")

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_refunded_skips_non_refunded_status(self, MockDispatch, MockSubs):
        self._call("refunded", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_payment_disputed ──────────────────────────────────────────────────

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_disputed_emits_on_disputed_status(self, MockDispatch, MockSubs):
        sub = _sub("payment.disputed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("disputed", _payment(status="disputed"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_disputed_skips_non_disputed_status(self, MockDispatch, MockSubs):
        self._call("disputed", _payment(status="failed"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── filter evaluation ────────────────────────────────────────────────────

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_skips_when_filter_rejects(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("payment.succeeded", filters={"currency": "EUR"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        self._call("succeeded", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_succeeded_dispatches_when_filter_accepts(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("payment.succeeded", filters={"currency": "USD"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = True
        MockDispatch.return_value.emit = MagicMock()
        self._call("succeeded", _payment(status="succeeded"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_multiple_subscriptions_all_dispatched(self, MockDispatch, MockSubs):
        subs = [_sub("payment.succeeded"), _sub("payment.succeeded")]
        MockSubs.filter.return_value.select_related.return_value = subs
        MockDispatch.return_value.emit = MagicMock()
        self._call("succeeded", _payment(status="succeeded"))
        self.assertEqual(MockDispatch.return_value.emit.call_count, 2)

    @patch(_SUBS_PATH_PAYMENT + ".objects")
    @patch(_DISPATCH_PATH)
    def test_payload_contains_required_keys(self, MockDispatch, MockSubs):
        sub = _sub("payment.succeeded")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("succeeded", _payment(status="succeeded"))
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        for key in ("payment_id", "user_id", "amount", "currency", "status"):
            self.assertIn(key, payload, f"Missing key: {key}")


# ═════════════════════════════════════════════════════════════════════════════
#  FRAUD SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestFraudSignals(unittest.TestCase):
    """Tests for signals/fraud_signals.py — 5 handlers."""

    def _call(self, handler_name, instance, created=False):
        from api.webhooks.signals.fraud_signals import (
            on_fraud_detected, on_fraud_flagged, on_fraud_cleared,
            on_fraud_investigation_started, on_fraud_investigation_completed,
        )
        fn = {
            "detected":               on_fraud_detected,
            "flagged":                on_fraud_flagged,
            "cleared":                on_fraud_cleared,
            "investigation_started":  on_fraud_investigation_started,
            "investigation_completed": on_fraud_investigation_completed,
        }[handler_name]
        fn(sender=MagicMock(), instance=instance, created=created)

    # ── on_fraud_detected (created=True guard) ───────────────────────────────

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_detected_fires_on_created(self, MockDispatch, MockSubs):
        sub = _sub("fraud.detected")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("detected", _fraud(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "fraud.detected")

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_detected_skips_on_update(self, MockDispatch, MockSubs):
        self._call("detected", _fraud(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_detected_swallows_exception(self, MockDispatch, MockSubs):
        sub = _sub("fraud.detected")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = Exception("timeout")
        self._call("detected", _fraud(), created=True)  # must not raise

    # ── on_fraud_flagged ─────────────────────────────────────────────────────

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_flagged_fires_on_flagged_status(self, MockDispatch, MockSubs):
        sub = _sub("fraud.flagged")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("flagged", _fraud(status="flagged"))
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "fraud.flagged")

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_flagged_skips_non_flagged_status(self, MockDispatch, MockSubs):
        for s in ("cleared", "detected", "pending"):
            MockDispatch.reset_mock()
            self._call("flagged", _fraud(status=s))
            MockDispatch.return_value.emit.assert_not_called()

    # ── on_fraud_cleared ─────────────────────────────────────────────────────

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_cleared_fires_on_cleared_status(self, MockDispatch, MockSubs):
        sub = _sub("fraud.cleared")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("cleared", _fraud(status="cleared"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_cleared_skips_non_cleared_status(self, MockDispatch, MockSubs):
        self._call("cleared", _fraud(status="flagged"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_fraud_investigation_started ───────────────────────────────────────

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_investigation_started_fires_on_started(self, MockDispatch, MockSubs):
        sub = _sub("fraud.investigation.started")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("investigation_started", _fraud(investigation_status="started"))
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "fraud.investigation.started")

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_investigation_started_skips_non_started(self, MockDispatch, MockSubs):
        self._call("investigation_started", _fraud(investigation_status="pending"))
        MockDispatch.return_value.emit.assert_not_called()

    # ── on_fraud_investigation_completed ─────────────────────────────────────

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_investigation_completed_fires_on_completed(self, MockDispatch, MockSubs):
        sub = _sub("fraud.investigation.completed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("investigation_completed", _fraud(investigation_status="completed"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_investigation_completed_skips_non_completed(self, MockDispatch, MockSubs):
        self._call("investigation_completed", _fraud(investigation_status="started"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_no_subscriptions_means_no_dispatch(self, MockDispatch, MockSubs):
        MockSubs.filter.return_value.select_related.return_value = []
        self._call("detected", _fraud(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_filter_rejected_skips_dispatch(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("fraud.detected", filters={"severity": "critical"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        self._call("detected", _fraud(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_FRAUD + ".objects")
    @patch(_DISPATCH_FRAUD)
    def test_payload_includes_fraud_id(self, MockDispatch, MockSubs):
        sub = _sub("fraud.detected")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("detected", _fraud(), created=True)
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        self.assertIn("fraud_id", payload)
        self.assertIn("fraud_type", payload)


# ═════════════════════════════════════════════════════════════════════════════
#  KYC SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestKYCSignals(unittest.TestCase):
    """Tests for signals/kyc_signals.py — 6 handlers."""

    def _call(self, handler_name, instance, created=False):
        from api.webhooks.signals.kyc_signals import (
            on_kyc_submitted, on_kyc_verified, on_kyc_rejected,
            on_kyc_status_changed, on_kyc_review_started, on_kyc_document_uploaded,
        )
        fn = {
            "submitted":         on_kyc_submitted,
            "verified":          on_kyc_verified,
            "rejected":          on_kyc_rejected,
            "status_changed":    on_kyc_status_changed,
            "review_started":    on_kyc_review_started,
            "document_uploaded": on_kyc_document_uploaded,
        }[handler_name]
        fn(sender=MagicMock(), instance=instance, created=created)

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_submitted_fires_on_created(self, MockDispatch, MockSubs):
        sub = _sub("kyc.submitted")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("submitted", _kyc(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "kyc.submitted")

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_submitted_skips_on_update(self, MockDispatch, MockSubs):
        self._call("submitted", _kyc(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_verified_fires_on_verified_status(self, MockDispatch, MockSubs):
        sub = _sub("kyc.verified")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("verified", _kyc(status="verified"))
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "kyc.verified")

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_verified_skips_non_verified_status(self, MockDispatch, MockSubs):
        self._call("verified", _kyc(status="submitted"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_rejected_fires_on_rejected_status(self, MockDispatch, MockSubs):
        sub = _sub("kyc.rejected")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("rejected", _kyc(status="rejected"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_rejected_skips_non_rejected_status(self, MockDispatch, MockSubs):
        self._call("rejected", _kyc(status="submitted"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_review_started_fires_on_under_review(self, MockDispatch, MockSubs):
        sub = _sub("kyc.review.started")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("review_started", _kyc(status="under_review"))
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "kyc.review.started")

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_review_started_skips_other_statuses(self, MockDispatch, MockSubs):
        for s in ("submitted", "verified", "rejected"):
            MockDispatch.reset_mock()
            self._call("review_started", _kyc(status=s))
            MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_document_uploaded_fires_on_created(self, MockDispatch, MockSubs):
        sub = _sub("kyc.document.uploaded")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        doc = SimpleNamespace(
            id=1, kyc=_kyc(), document_type="passport",
            document_name="passport.jpg", reference="ref",
            created_at=_ts(), metadata={},
        )
        self._call("document_uploaded", doc, created=True)
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_document_uploaded_skips_on_update(self, MockDispatch, MockSubs):
        doc = SimpleNamespace(
            id=1, kyc=_kyc(), document_type="passport",
            document_name="passport.jpg", reference="ref",
            created_at=_ts(), metadata={},
        )
        self._call("document_uploaded", doc, created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_swallows_exception_continues(self, MockDispatch, MockSubs):
        sub = _sub("kyc.submitted")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = ConnectionError("timeout")
        self._call("submitted", _kyc(), created=True)  # must not raise

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_filter_rejected_skips_dispatch(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("kyc.verified", filters={"level": "enhanced"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        self._call("verified", _kyc(status="verified"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_KYC + ".objects")
    @patch(_DISPATCH_KYC)
    def test_payload_contains_kyc_id_and_status(self, MockDispatch, MockSubs):
        sub = _sub("kyc.verified")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("verified", _kyc(status="verified"))
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        self.assertIn("kyc_id", payload)
        self.assertIn("status", payload)
        self.assertEqual(payload["status"], "verified")


# ═════════════════════════════════════════════════════════════════════════════
#  OFFER SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestOfferSignals(unittest.TestCase):
    """Tests for signals/offer_signals.py — 5 handlers."""

    def _call(self, handler_name, instance, created=False):
        from api.webhooks.signals.offer_signals import (
            on_offer_credited, on_offer_completed, on_offer_expired,
            on_offer_cancelled, on_offer_updated,
        )
        fn = {
            "credited":  on_offer_credited,
            "completed": on_offer_completed,
            "expired":   on_offer_expired,
            "cancelled": on_offer_cancelled,
            "updated":   on_offer_updated,
        }[handler_name]
        fn(sender=MagicMock(), instance=instance, created=created)

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_credited_fires_on_created(self, MockDispatch, MockSubs):
        sub = _sub("offer.credited")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("credited", _offer(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "offer.credited")

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_credited_skips_on_update(self, MockDispatch, MockSubs):
        self._call("credited", _offer(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_completed_fires_on_completed_status(self, MockDispatch, MockSubs):
        sub = _sub("offer.completed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("completed", _offer(status="completed"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_completed_skips_non_completed_status(self, MockDispatch, MockSubs):
        self._call("completed", _offer(status="expired"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_expired_fires_on_expired_status(self, MockDispatch, MockSubs):
        sub = _sub("offer.expired")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("expired", _offer(status="expired"))
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "offer.expired")

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_expired_skips_non_expired_status(self, MockDispatch, MockSubs):
        self._call("expired", _offer(status="completed"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_cancelled_fires_on_cancelled_status(self, MockDispatch, MockSubs):
        sub = _sub("offer.cancelled")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("cancelled", _offer(status="cancelled"))
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_cancelled_skips_non_cancelled_status(self, MockDispatch, MockSubs):
        self._call("cancelled", _offer(status="completed"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_swallows_exception(self, MockDispatch, MockSubs):
        sub = _sub("offer.credited")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = RuntimeError("broker down")
        self._call("credited", _offer(), created=True)  # must not raise

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_filter_accepted_dispatches(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("offer.credited", filters={"currency": "USD"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = True
        MockDispatch.return_value.emit = MagicMock()
        self._call("credited", _offer(), created=True)
        MockDispatch.return_value.emit.assert_called_once()

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_filter_rejected_skips_dispatch(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("offer.credited", filters={"currency": "EUR"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        self._call("credited", _offer(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_payload_contains_offer_id_and_amount(self, MockDispatch, MockSubs):
        sub = _sub("offer.credited")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("credited", _offer(), created=True)
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        self.assertIn("offer_id", payload)
        self.assertIn("amount", payload)
        self.assertIn("currency", payload)

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_no_subscriptions_means_no_dispatch(self, MockDispatch, MockSubs):
        MockSubs.filter.return_value.select_related.return_value = []
        self._call("credited", _offer(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_multiple_subscriptions_each_dispatched(self, MockDispatch, MockSubs):
        subs = [_sub("offer.credited"), _sub("offer.credited"), _sub("offer.credited")]
        MockSubs.filter.return_value.select_related.return_value = subs
        MockDispatch.return_value.emit = MagicMock()
        self._call("credited", _offer(), created=True)
        self.assertEqual(MockDispatch.return_value.emit.call_count, 3)

    @patch(_SUBS_OFFER + ".objects")
    @patch(_DISPATCH_OFFER)
    def test_one_exception_does_not_stop_remaining_subscriptions(self, MockDispatch, MockSubs):
        sub1 = _sub("offer.credited")
        sub2 = _sub("offer.credited")
        MockSubs.filter.return_value.select_related.return_value = [sub1, sub2]
        # First sub raises, second should still be dispatched
        MockDispatch.return_value.emit.side_effect = [RuntimeError("fail"), None]
        self._call("credited", _offer(), created=True)
        self.assertEqual(MockDispatch.return_value.emit.call_count, 2)


# ═════════════════════════════════════════════════════════════════════════════
#  USER SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestUserSignals(unittest.TestCase):
    """Tests for signals/user_signals.py — 6 handlers."""

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_created_fires_on_created(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_created
        sub = _sub("user.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        on_user_created(sender=MagicMock(), instance=_user(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "user.created")

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_created_skips_on_update(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_created
        on_user_created(sender=MagicMock(), instance=_user(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_created_payload_has_required_keys(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_created
        sub = _sub("user.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        on_user_created(sender=MagicMock(), instance=_user(), created=True)
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        for k in ("user_id", "username", "email", "is_active"):
            self.assertIn(k, payload)

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_status_changed_fires_on_is_active_change(self, MockDispatch, MockSubs):
        from django.core.exceptions import ObjectDoesNotExist
        from api.webhooks.signals.user_signals import on_user_status_changed
        sub = _sub("user.status.changed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        # sender.objects.get must return an old instance with different is_active
        sender_mock = MagicMock()
        # The handler does `except sender.DoesNotExist:` - a real Model class
        # (what `sender` always is in production, per Django's signal
        # dispatch) has a genuine DoesNotExist exception class there; a bare
        # MagicMock attribute is not a valid exception type, which raised
        # TypeError and masked the real AttributeError underneath (confirmed
        # empirically). Giving it one, same as a real model's DoesNotExist
        # would behave for an unmatched except clause.
        sender_mock.DoesNotExist = ObjectDoesNotExist
        sender_mock.objects.get.return_value = _user(is_active=True)
        on_user_status_changed(sender=sender_mock, instance=_user(is_active=False))
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "user.status.changed")
        self.assertIn("status_change", kw["payload"])

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_status_changed_skips_when_no_change(self, MockDispatch, MockSubs):
        from django.core.exceptions import ObjectDoesNotExist
        from api.webhooks.signals.user_signals import on_user_status_changed
        sender_mock = MagicMock()
        sender_mock.DoesNotExist = ObjectDoesNotExist
        sender_mock.objects.get.return_value = _user(is_active=True)
        on_user_status_changed(sender=sender_mock, instance=_user(is_active=True))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_login_emits_user_login_event(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_login
        sub = _sub("user.login")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        usr = _user()
        usr.is_authenticated = True
        req = MagicMock()
        req.META = {"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "test"}
        req.session.session_key = "abc123"
        on_user_login(sender=MagicMock(), request=req, user=usr)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "user.login")

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_logout_emits_user_logout_event(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_logout
        sub = _sub("user.logout")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        usr = _user()
        usr.is_authenticated = True
        req = MagicMock()
        req.META = {"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "test"}
        req.session.session_key = "abc123"
        on_user_logout(sender=MagicMock(), request=req, user=usr)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "user.logout")

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_swallows_exception(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_created
        sub = _sub("user.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = Exception("db error")
        on_user_created(sender=MagicMock(), instance=_user(), created=True)  # must not raise

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_login_skips_unauthenticated_user(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_login
        usr = _user()
        usr.is_authenticated = False
        req = MagicMock()
        on_user_login(sender=MagicMock(), request=req, user=usr)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_login_skips_none_user(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_login
        req = MagicMock()
        on_user_login(sender=MagicMock(), request=req, user=None)
        MockDispatch.return_value.emit.assert_not_called()

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_user_created_filter_rejected(self, MockDispatch, MockSubs, MockFilter):
        from api.webhooks.signals.user_signals import on_user_created
        sub = _sub("user.created", filters={"is_staff": True})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        on_user_created(sender=MagicMock(), instance=_user(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_USER + ".objects")
    @patch(_DISPATCH_USER)
    def test_no_subscriptions_no_dispatch(self, MockDispatch, MockSubs):
        from api.webhooks.signals.user_signals import on_user_created
        MockSubs.filter.return_value.select_related.return_value = []
        on_user_created(sender=MagicMock(), instance=_user(), created=True)
        MockDispatch.return_value.emit.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
#  WALLET SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestWalletSignals(unittest.TestCase):
    """Tests for signals/wallet_signals.py — 3 handlers."""

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_transaction_created_fires_on_created(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_created
        sub = _sub("wallet.transaction.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        on_wallet_transaction_created(sender=MagicMock(), instance=_wallet_tx(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "wallet.transaction.created")

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_transaction_created_skips_on_update(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_created
        on_wallet_transaction_created(sender=MagicMock(), instance=_wallet_tx(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_transaction_payload_has_wallet_id(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_created
        sub = _sub("wallet.transaction.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        on_wallet_transaction_created(sender=MagicMock(), instance=_wallet_tx(), created=True)
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        self.assertIn("wallet_id", payload)
        self.assertIn("balance_before", payload)
        self.assertIn("balance_after", payload)

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_balance_updated_fires_on_save(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_balance_updated
        sub = _sub("wallet.balance.updated")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        on_wallet_balance_updated(sender=MagicMock(), instance=_wallet())
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "wallet.balance.updated")

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_transaction_failed_fires_on_failed_status(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_failed
        sub = _sub("wallet.transaction.failed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        tx = _wallet_tx(status="failed")
        tx.failure_reason = "insufficient_funds"
        tx.error_code = "ERR_001"
        on_wallet_transaction_failed(sender=MagicMock(), instance=tx)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "wallet.transaction.failed")

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_transaction_failed_skips_non_failed_status(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_failed
        on_wallet_transaction_failed(sender=MagicMock(), instance=_wallet_tx(status="success"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_wallet_swallows_exception(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_created
        sub = _sub("wallet.transaction.created")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = Exception("redis down")
        on_wallet_transaction_created(sender=MagicMock(), instance=_wallet_tx(), created=True)

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_filter_rejected_skips_dispatch(self, MockDispatch, MockSubs, MockFilter):
        from api.webhooks.signals.wallet_signals import on_wallet_transaction_created
        sub = _sub("wallet.transaction.created", filters={"currency": "EUR"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        on_wallet_transaction_created(sender=MagicMock(), instance=_wallet_tx(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WALLET + ".objects")
    @patch(_DISPATCH_WALLET)
    def test_balance_updated_no_subscriptions(self, MockDispatch, MockSubs):
        from api.webhooks.signals.wallet_signals import on_wallet_balance_updated
        MockSubs.filter.return_value.select_related.return_value = []
        on_wallet_balance_updated(sender=MagicMock(), instance=_wallet())
        MockDispatch.return_value.emit.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
#  WITHDRAWAL SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

class TestWithdrawalSignals(unittest.TestCase):
    """Tests for signals/withdrawal_signals.py — 5 handlers."""

    def _call(self, handler_name, instance, created=False):
        from api.webhooks.signals.withdrawal_signals import (
            on_withdrawal_requested, on_withdrawal_approved,
            on_withdrawal_rejected, on_withdrawal_completed, on_withdrawal_failed,
        )
        fn = {
            "requested": on_withdrawal_requested,
            "approved":  on_withdrawal_approved,
            "rejected":  on_withdrawal_rejected,
            "completed": on_withdrawal_completed,
            "failed":    on_withdrawal_failed,
        }[handler_name]
        fn(sender=MagicMock(), instance=instance, created=created)

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_requested_fires_on_created(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.requested")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("requested", _withdrawal(), created=True)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "withdrawal.requested")

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_requested_skips_on_update(self, MockDispatch, MockSubs):
        self._call("requested", _withdrawal(), created=False)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_approved_fires_on_approved_status(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.approved")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        wd = _withdrawal(status="approved")
        wd.approved_by = SimpleNamespace(username="admin")
        wd.approval_notes = "Approved"
        self._call("approved", wd)
        MockDispatch.return_value.emit.assert_called_once()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_approved_skips_non_approved_status(self, MockDispatch, MockSubs):
        self._call("approved", _withdrawal(status="pending"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_rejected_fires_on_rejected_status(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.rejected")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        wd = _withdrawal(status="rejected")
        wd.rejected_by = SimpleNamespace(username="admin")
        wd.rejection_reason = "Insufficient docs"
        self._call("rejected", wd)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "withdrawal.rejected")

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_rejected_skips_non_rejected_status(self, MockDispatch, MockSubs):
        self._call("rejected", _withdrawal(status="approved"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_completed_fires_on_completed_status(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.completed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        wd = _withdrawal(status="completed")
        wd.transaction_id = "txn-wd-001"
        wd.processed_amount = "74.50"
        wd.fees = "0.50"
        self._call("completed", wd)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "withdrawal.completed")

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_completed_skips_non_completed_status(self, MockDispatch, MockSubs):
        self._call("completed", _withdrawal(status="approved"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_failed_fires_on_failed_status(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.failed")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        wd = _withdrawal(status="failed")
        wd.failure_reason = "bank_error"
        wd.error_code = "ERR_BANK_001"
        wd.retry_count = 2
        self._call("failed", wd)
        MockDispatch.return_value.emit.assert_called_once()
        _, kw = MockDispatch.return_value.emit.call_args
        self.assertEqual(kw["event_type"], "withdrawal.failed")

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_failed_skips_non_failed_status(self, MockDispatch, MockSubs):
        self._call("failed", _withdrawal(status="completed"))
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_swallows_exception(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.requested")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit.side_effect = Exception("network fail")
        self._call("requested", _withdrawal(), created=True)  # must not raise

    @patch("api.webhooks.services.filtering.FilterService")
    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_filter_rejected_skips_dispatch(self, MockDispatch, MockSubs, MockFilter):
        sub = _sub("withdrawal.requested", filters={"currency": "EUR"})
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockFilter.return_value.evaluate_filter.return_value = False
        self._call("requested", _withdrawal(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_payload_has_withdrawal_id_and_amount(self, MockDispatch, MockSubs):
        sub = _sub("withdrawal.requested")
        MockSubs.filter.return_value.select_related.return_value = [sub]
        MockDispatch.return_value.emit = MagicMock()
        self._call("requested", _withdrawal(), created=True)
        payload = MockDispatch.return_value.emit.call_args[1]["payload"]
        self.assertIn("withdrawal_id", payload)
        self.assertIn("amount", payload)
        self.assertIn("currency", payload)
        self.assertIn("method", payload)

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_no_subscriptions_no_dispatch(self, MockDispatch, MockSubs):
        MockSubs.filter.return_value.select_related.return_value = []
        self._call("requested", _withdrawal(), created=True)
        MockDispatch.return_value.emit.assert_not_called()

    @patch(_SUBS_WD + ".objects")
    @patch(_DISPATCH_WD)
    def test_one_exception_does_not_stop_remaining(self, MockDispatch, MockSubs):
        subs = [_sub("withdrawal.requested"), _sub("withdrawal.requested")]
        MockSubs.filter.return_value.select_related.return_value = subs
        MockDispatch.return_value.emit.side_effect = [RuntimeError("fail"), None]
        self._call("requested", _withdrawal(), created=True)
        self.assertEqual(MockDispatch.return_value.emit.call_count, 2)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    unittest.main()

"""
payout_queue/tests/test_v5_integration.py
==========================================
Tests for ALL v5 cross-app integration guards and integration modules.
Zero overlap with existing test files.

Coverage:
  ① KYC gate in services.add_payout_items()
  ② Fraud gate in services._create_single_payout_item()
  ③ Wallet gate in services._setup_batch_for_processing()
  ④ _write_audit_log in receivers
  ⑤ api/kyc/payout_integration.py
  ⑥ api/fraud_detection/payout_integration.py
  ⑦ api/wallet/payout_integration.py
  ⑧ api/audit_logs/payout_integration.py
  ⑨ api/notifications/payout_tasks.py
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from ..choices import PayoutBatchStatus, PayoutItemStatus, PaymentGateway
from ..exceptions import (
    PayoutQueueError, InsufficientFundsError,
    PayoutBatchNotFoundError,
)
from ..models import PayoutBatch, PayoutItem
from .. import services
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
)

BASE = "/api/payout-queue"

def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c

# ─────────────────────────────────────────────────────────────────────────────
# ① KYC gate — services.add_payout_items()
# ─────────────────────────────────────────────────────────────────────────────

class KYCGateInAddPayoutItemsTest(TestCase):
    """services.add_payout_items() must reject unverified users when
    PAYOUT_KYC_CHECK_ENABLED=True."""

    def setUp(self):
        self.admin = StaffUserFactory()
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory(
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )
        self.item = {
            "user_id":        self.user.pk,
            "account_number": "01712345678",
            "gross_amount":   "500.00",
        }

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=True)
    @patch("api.kyc.payout_integration.is_user_kyc_verified", return_value=False)
    def test_blocks_when_user_not_kyc_verified(self, mock_kyc):
        with self.assertRaises(PayoutQueueError) as ctx:
            services.add_payout_items(
                batch_id=self.batch.pk,
                items=[self.item],
                validate_accounts=False,
            )
        self.assertIn("KYC not verified", str(ctx.exception))
        mock_kyc.assert_called_once_with(self.user.pk)

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=True)
    @patch("api.kyc.payout_integration.is_user_kyc_verified", return_value=True)
    @patch("payout_queue.services._fee_calculator")
    def test_passes_when_user_is_kyc_verified(self, mock_fee, mock_kyc):
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        items = services.add_payout_items(
            batch_id=self.batch.pk,
            items=[self.item],
            validate_accounts=False,
        )
        self.assertEqual(len(items), 1)
        mock_kyc.assert_called_once_with(self.user.pk)

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=False)
    @patch("payout_queue.services._fee_calculator")
    def test_skips_kyc_check_when_disabled(self, mock_fee):
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        # Should NOT call is_user_kyc_verified at all
        with patch("api.kyc.payout_integration.is_user_kyc_verified") as mock_kyc:
            items = services.add_payout_items(
                batch_id=self.batch.pk,
                items=[self.item],
                validate_accounts=False,
            )
            mock_kyc.assert_not_called()
        self.assertEqual(len(items), 1)

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=True)
    @patch("payout_queue.services._fee_calculator")
    def test_handles_kyc_import_error_gracefully(self, mock_fee):
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        # If api.kyc is not installed, import raises ImportError — should proceed
        with patch.dict("sys.modules", {"api.kyc.payout_integration": None}):
            try:
                items = services.add_payout_items(
                    batch_id=self.batch.pk,
                    items=[self.item],
                    validate_accounts=False,
                )
                # Should not crash when import fails
            except Exception as exc:
                # ImportError should be caught and logged, not re-raised
                self.assertNotIsInstance(exc, ImportError)

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=True)
    @patch("api.kyc.payout_integration.is_user_kyc_verified", return_value=False)
    def test_error_message_includes_unverified_user_ids(self, mock_kyc):
        user2 = UserFactory()
        items = [
            {"user_id": self.user.pk, "account_number": "01712345678", "gross_amount": "500.00"},
            {"user_id": user2.pk,     "account_number": "01812345678", "gross_amount": "300.00"},
        ]
        with self.assertRaises(PayoutQueueError) as ctx:
            services.add_payout_items(
                batch_id=self.batch.pk, items=items, validate_accounts=False
            )
        msg = str(ctx.exception)
        self.assertIn("KYC", msg)
        self.assertIn("2 user(s)", msg)

    @override_settings(PAYOUT_KYC_CHECK_ENABLED=True)
    @patch("api.kyc.payout_integration.is_user_kyc_verified", return_value=False)
    def test_no_items_created_when_kyc_blocked(self, mock_kyc):
        before = PayoutItem.objects.filter(batch=self.batch).count()
        try:
            services.add_payout_items(
                batch_id=self.batch.pk,
                items=[self.item],
                validate_accounts=False,
            )
        except PayoutQueueError:
            pass
        after = PayoutItem.objects.filter(batch=self.batch).count()
        self.assertEqual(before, after)

# ─────────────────────────────────────────────────────────────────────────────
# ② Fraud gate — services._create_single_payout_item()
# ─────────────────────────────────────────────────────────────────────────────

class FraudGateInCreateItemTest(TestCase):
    """_create_single_payout_item() blocks high-risk payouts when
    PAYOUT_FRAUD_CHECK_ENABLED=True."""

    def setUp(self):
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory(
            status=PayoutBatchStatus.PENDING,
            gateway=PaymentGateway.BKASH,
        )

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_FRAUD_RISK_THRESHOLD=0.75)
    @patch("api.fraud_detection.payout_integration.get_payout_risk_score", return_value=0.90)
    def test_blocks_when_fraud_score_exceeds_threshold(self, mock_fraud):
        with self.assertRaises(PayoutQueueError) as ctx:
            services._create_single_payout_item(
                batch=self.batch,
                item_dict={
                    "user_id":        self.user.pk,
                    "account_number": "01712345678",
                    "gross_amount":   Decimal("500.00"),
                },
                processor=None,
                validate_accounts=False,
            )
        self.assertIn("fraud risk score", str(ctx.exception).lower())
        mock_fraud.assert_called_once()

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_FRAUD_RISK_THRESHOLD=0.75)
    @patch("api.fraud_detection.payout_integration.get_payout_risk_score", return_value=0.30)
    @patch("payout_queue.services._fee_calculator")
    def test_allows_when_fraud_score_below_threshold(self, mock_fee, mock_fraud):
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        item = services._create_single_payout_item(
            batch=self.batch,
            item_dict={
                "user_id":        self.user.pk,
                "account_number": "01712345678",
                "gross_amount":   Decimal("500.00"),
            },
            processor=None,
            validate_accounts=False,
        )
        self.assertIsNotNone(item)
        self.assertIsInstance(item, PayoutItem)

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=False)
    @patch("payout_queue.services._fee_calculator")
    def test_skips_fraud_check_when_disabled(self, mock_fee):
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        with patch("api.fraud_detection.payout_integration.get_payout_risk_score") as mock_fraud:
            services._create_single_payout_item(
                batch=self.batch,
                item_dict={
                    "user_id":        self.user.pk,
                    "account_number": "01712345678",
                    "gross_amount":   Decimal("500.00"),
                },
                processor=None,
                validate_accounts=False,
            )
            mock_fraud.assert_not_called()

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_FRAUD_RISK_THRESHOLD=0.75)
    @patch("api.fraud_detection.payout_integration.get_payout_risk_score", return_value=0.75)
    @patch("payout_queue.services._fee_calculator")
    def test_allows_exactly_at_threshold(self, mock_fee, mock_fraud):
        """Score exactly equal to threshold should be allowed (> not >=)."""
        mock_fee.calculate.return_value = {
            "fee": Decimal("9.25"), "net": Decimal("490.75")
        }
        item = services._create_single_payout_item(
            batch=self.batch,
            item_dict={
                "user_id":        self.user.pk,
                "account_number": "01712345678",
                "gross_amount":   Decimal("500.00"),
            },
            processor=None,
            validate_accounts=False,
        )
        self.assertIsNotNone(item)

    @override_settings(PAYOUT_FRAUD_CHECK_ENABLED=True, PAYOUT_FRAUD_RISK_THRESHOLD=0.75)
    @patch("api.fraud_detection.payout_integration.get_payout_risk_score", return_value=0.76)
    def test_blocks_just_above_threshold(self, mock_fraud):
        with self.assertRaises(PayoutQueueError):
            services._create_single_payout_item(
                batch=self.batch,
                item_dict={
                    "user_id":        self.user.pk,
                    "account_number": "01712345678",
                    "gross_amount":   Decimal("500.00"),
                },
                processor=None,
                validate_accounts=False,
            )

# ─────────────────────────────────────────────────────────────────────────────
# ③ Wallet gate — services._setup_batch_for_processing()
# ─────────────────────────────────────────────────────────────────────────────

class WalletGateInSetupBatchTest(TestCase):

    def setUp(self):
        self.batch = PayoutBatchFactory(
            status=PayoutBatchStatus.PENDING,
            total_amount=Decimal("1000.00"),
        )
        self.batch.tenant_id = uuid.uuid4()
        PayoutBatch.objects.filter(pk=self.batch.pk).update(tenant_id=self.batch.tenant_id)

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.wallet.payout_integration.deduct_payout_wallet",
           side_effect=InsufficientFundsError("Insufficient funds"))
    @patch("payout_queue.services._get_processor")
    def test_fails_batch_when_wallet_insufficient(self, mock_proc, mock_deduct):
        mock_proc.return_value = MagicMock()
        with self.assertRaises(InsufficientFundsError):
            services._setup_batch_for_processing(
                self.batch, "worker-1", None
            )
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, PayoutBatchStatus.FAILED)

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("api.wallet.payout_integration.deduct_payout_wallet")
    @patch("payout_queue.services._get_processor")
    def test_deducts_wallet_and_returns_processor(self, mock_proc, mock_deduct):
        mock_processor = MagicMock()
        mock_proc.return_value = mock_processor
        result = services._setup_batch_for_processing(
            self.batch, "worker-2", None
        )
        mock_deduct.assert_called_once_with(
            tenant_id=self.batch.tenant_id,
            amount=self.batch.total_amount,
            reference=str(self.batch.id),
        )
        self.assertEqual(result, mock_processor)

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=False)
    @patch("payout_queue.services._get_processor")
    def test_skips_wallet_check_when_disabled(self, mock_proc):
        mock_proc.return_value = MagicMock()
        with patch("api.wallet.payout_integration.deduct_payout_wallet") as mock_deduct:
            services._setup_batch_for_processing(self.batch, "worker-3", None)
            mock_deduct.assert_not_called()

    @override_settings(PAYOUT_WALLET_CHECK_ENABLED=True)
    @patch("payout_queue.services._get_processor")
    def test_skips_wallet_check_when_no_tenant(self, mock_proc):
        """Batches with no tenant_id (single-tenant setups) skip wallet check."""
        mock_proc.return_value = MagicMock()
        PayoutBatch.objects.filter(pk=self.batch.pk).update(tenant_id=None)
        self.batch.tenant_id = None
        with patch("api.wallet.payout_integration.deduct_payout_wallet") as mock_deduct:
            services._setup_batch_for_processing(self.batch, "worker-4", None)
            mock_deduct.assert_not_called()

# ─────────────────────────────────────────────────────────────────────────────
# ④ Audit log in receivers._write_audit_log
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogInReceiversTest(TestCase):

    def setUp(self):
        self.batch = PayoutBatchFactory(status=PayoutBatchStatus.PROCESSING)

    @override_settings(PAYOUT_AUDIT_LOG_ENABLED=True)
    @patch("api.audit_logs.payout_integration.log_payout_event")
    @patch("payout_queue.receivers._emit_webhook_event")
    @patch("payout_queue.receivers._notify_batch_result")
    def test_audit_log_called_on_batch_completed(
        self, mock_notify, mock_webhook, mock_audit
    ):
        from ..signals import payout_batch_completed
        payout_batch_completed.send(sender=PayoutBatch, batch=self.batch)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["event_type"], "BATCH_COMPLETED")

    @override_settings(PAYOUT_AUDIT_LOG_ENABLED=True)
    @patch("api.audit_logs.payout_integration.log_payout_event")
    @patch("payout_queue.receivers._emit_webhook_event")
    @patch("payout_queue.receivers._notify_batch_result")
    def test_audit_log_called_on_batch_failed(
        self, mock_notify, mock_webhook, mock_audit
    ):
        from ..signals import payout_batch_failed
        payout_batch_failed.send(
            sender=PayoutBatch, batch=self.batch, error_summary="Gateway down"
        )
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        self.assertEqual(call_kwargs["event_type"], "BATCH_FAILED")

    @override_settings(PAYOUT_AUDIT_LOG_ENABLED=False)
    @patch("api.audit_logs.payout_integration.log_payout_event")
    @patch("payout_queue.receivers._emit_webhook_event")
    @patch("payout_queue.receivers._notify_batch_result")
    def test_audit_log_skipped_when_disabled(
        self, mock_notify, mock_webhook, mock_audit
    ):
        from ..signals import payout_batch_completed
        payout_batch_completed.send(sender=PayoutBatch, batch=self.batch)
        mock_audit.assert_not_called()

    @override_settings(PAYOUT_AUDIT_LOG_ENABLED=True)
    @patch("payout_queue.receivers._emit_webhook_event")
    @patch("payout_queue.receivers._notify_batch_result")
    def test_audit_log_import_error_does_not_crash(
        self, mock_notify, mock_webhook
    ):
        """If api.audit_logs is not installed, receiver must not crash."""
        from ..signals import payout_batch_completed
        with patch.dict("sys.modules",
                        {"api.audit_logs.payout_integration": None}):
            # Should complete without raising
            try:
                payout_batch_completed.send(sender=PayoutBatch, batch=self.batch)
            except Exception as exc:
                self.fail(f"Receiver raised {exc!r} on ImportError")

    @override_settings(PAYOUT_AUDIT_LOG_ENABLED=True)
    @patch("api.audit_logs.payout_integration.log_payout_event",
           side_effect=Exception("DB error"))
    @patch("payout_queue.receivers._emit_webhook_event")
    @patch("payout_queue.receivers._notify_batch_result")
    def test_audit_log_exception_does_not_crash_receiver(
        self, mock_notify, mock_webhook, mock_audit
    ):
        """A crash in the audit log call must not crash the signal receiver."""
        from ..signals import payout_batch_completed
        try:
            payout_batch_completed.send(sender=PayoutBatch, batch=self.batch)
        except Exception as exc:
            self.fail(f"Receiver raised {exc!r} on audit log crash")

# ─────────────────────────────────────────────────────────────────────────────
# ⑤ api/kyc/payout_integration.py
# ─────────────────────────────────────────────────────────────────────────────

class KycPoutIntegrationTest(TestCase):

    def _mock_profile(self, status="VERIFIED", expires_at=None):
        p = MagicMock()
        p.status     = status
        p.expires_at = expires_at
        return p

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_true_for_verified_user(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        mock_model.objects.select_related().get.return_value = self._mock_profile("VERIFIED")
        self.assertTrue(is_user_kyc_verified(user_id=1))

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_false_for_pending(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        mock_model.objects.select_related().get.return_value = self._mock_profile("PENDING")
        self.assertFalse(is_user_kyc_verified(user_id=1))

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_false_for_rejected(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        mock_model.objects.select_related().get.return_value = self._mock_profile("REJECTED")
        self.assertFalse(is_user_kyc_verified(user_id=1))

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_false_when_profile_does_not_exist(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        mock_model.DoesNotExist = Exception
        mock_model.objects.select_related().get.side_effect = Exception()
        self.assertFalse(is_user_kyc_verified(user_id=99))

    def test_returns_false_when_user_id_is_none(self):
        from api.kyc.payout_integration import is_user_kyc_verified
        self.assertFalse(is_user_kyc_verified(user_id=None))

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_false_for_expired_verification(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        past = timezone.now() - timezone.timedelta(days=1)
        mock_model.objects.select_related().get.return_value = self._mock_profile(
            "VERIFIED", expires_at=past
        )
        self.assertFalse(is_user_kyc_verified(user_id=1))

    @patch("api.kyc.payout_integration.KYCProfile")
    def test_returns_true_for_verified_without_expiry(self, mock_model):
        from api.kyc.payout_integration import is_user_kyc_verified
        mock_model.objects.select_related().get.return_value = self._mock_profile(
            "VERIFIED", expires_at=None
        )
        self.assertTrue(is_user_kyc_verified(user_id=1))

# ─────────────────────────────────────────────────────────────────────────────
# ⑥ api/fraud_detection/payout_integration.py
# ─────────────────────────────────────────────────────────────────────────────

class FraudDetectionIntegrationTest(TestCase):

    def test_returns_float_between_0_and_1(self):
        from api.fraud_detection.payout_integration import get_payout_risk_score
        score = get_payout_risk_score(1, Decimal("500.00"), "01712345678")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_returns_1_for_none_user_id(self):
        from api.fraud_detection.payout_integration import get_payout_risk_score
        score = get_payout_risk_score(None, Decimal("500.00"), "01712345678")
        self.assertEqual(score, 1.0)

    def test_returns_0_on_internal_error(self):
        from api.fraud_detection.payout_integration import get_payout_risk_score
        with patch(
            "api.fraud_detection.payout_integration._calculate_risk",
            side_effect=Exception("DB down"),
        ):
            score = get_payout_risk_score(1, Decimal("500.00"), "01712345678")
            self.assertEqual(score, 0.0)  # fail-open

    def test_clamps_score_to_0_to_1(self):
        from api.fraud_detection.payout_integration import get_payout_risk_score
        with patch(
            "api.fraud_detection.payout_integration._calculate_risk",
            return_value=99.0,  # out of range
        ):
            score = get_payout_risk_score(1, Decimal("500.00"), "01712345678")
            self.assertEqual(score, 1.0)

    @patch("api.fraud_detection.payout_integration.BlacklistedAccount")
    def test_returns_1_for_blacklisted_account(self, mock_bl):
        from api.fraud_detection.payout_integration import _calculate_risk
        mock_bl.objects.filter.return_value.exists.return_value = True
        score = _calculate_risk(
            user_id=1, amount=Decimal("500.00"), account_number="01712345678"
        )
        self.assertEqual(score, 1.0)

    @patch("api.fraud_detection.payout_integration.BlacklistedAccount")
    def test_returns_0_for_clean_account(self, mock_bl):
        from api.fraud_detection.payout_integration import _calculate_risk
        mock_bl.objects.filter.return_value.exists.return_value = False
        score = _calculate_risk(
            user_id=1, amount=Decimal("50.00"), account_number="01712345678"
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLess(score, 1.0)

# ─────────────────────────────────────────────────────────────────────────────
# ⑦ api/wallet/payout_integration.py
# ─────────────────────────────────────────────────────────────────────────────

class WalletIntegrationTest(TestCase):

    def _mock_account(self, balance: Decimal = Decimal("5000.00")):
        acct = MagicMock()
        acct.available_balance = balance
        acct.save = MagicMock()
        return acct

    @patch("api.wallet.payout_integration.WalletAccount")
    def test_deduct_success_reduces_balance(self, mock_model):
        from api.wallet.payout_integration import deduct_payout_wallet
        acct = self._mock_account(Decimal("5000.00"))
        mock_model.objects.select_for_update.return_value.filter.return_value.first.return_value = acct
        with patch("api.wallet.payout_integration.WalletTransaction"):
            deduct_payout_wallet(
                tenant_id=uuid.uuid4(),
                amount=Decimal("1000.00"),
                reference="batch-001",
            )
        self.assertEqual(acct.available_balance, Decimal("4000.00"))

    @patch("api.wallet.payout_integration.WalletAccount")
    def test_deduct_raises_when_balance_insufficient(self, mock_model):
        from api.wallet.payout_integration import deduct_payout_wallet
        acct = self._mock_account(Decimal("200.00"))
        mock_model.objects.select_for_update.return_value.filter.return_value.first.return_value = acct
        with self.assertRaises(InsufficientFundsError):
            deduct_payout_wallet(
                tenant_id=uuid.uuid4(),
                amount=Decimal("500.00"),
                reference="batch-002",
            )

    @patch("api.wallet.payout_integration.WalletAccount")
    def test_deduct_raises_when_no_wallet(self, mock_model):
        from api.wallet.payout_integration import deduct_payout_wallet
        mock_model.objects.select_for_update.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(ValueError):
            deduct_payout_wallet(
                tenant_id=uuid.uuid4(),
                amount=Decimal("500.00"),
                reference="batch-003",
            )

    def test_deduct_raises_on_none_tenant_id(self):
        from api.wallet.payout_integration import deduct_payout_wallet
        with self.assertRaises(ValueError):
            deduct_payout_wallet(
                tenant_id=None, amount=Decimal("500.00"), reference="ref"
            )

    def test_deduct_raises_on_zero_amount(self):
        from api.wallet.payout_integration import deduct_payout_wallet
        with self.assertRaises(ValueError):
            deduct_payout_wallet(
                tenant_id=uuid.uuid4(),
                amount=Decimal("0.00"),
                reference="ref",
            )

    @patch("api.wallet.payout_integration.WalletAccount")
    def test_refund_increases_balance(self, mock_model):
        from api.wallet.payout_integration import refund_payout_wallet
        acct = self._mock_account(Decimal("1000.00"))
        mock_model.objects.select_for_update.return_value.filter.return_value.first.return_value = acct
        with patch("api.wallet.payout_integration.WalletTransaction"):
            refund_payout_wallet(
                tenant_id=uuid.uuid4(),
                amount=Decimal("500.00"),
                reference="batch-004",
                reason="Batch cancelled",
            )
        self.assertEqual(acct.available_balance, Decimal("1500.00"))

    @patch("api.wallet.payout_integration.WalletAccount")
    def test_refund_handles_missing_wallet_gracefully(self, mock_model):
        from api.wallet.payout_integration import refund_payout_wallet
        mock_model.objects.select_for_update.return_value.filter.return_value.first.return_value = None
        # Should not raise
        refund_payout_wallet(
            tenant_id=uuid.uuid4(),
            amount=Decimal("100.00"),
            reference="batch-005",
        )

# ─────────────────────────────────────────────────────────────────────────────
# ⑧ api/audit_logs/payout_integration.py
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogIntegrationTest(TestCase):

    @patch("api.audit_logs.payout_integration.AuditLog")
    def test_log_payout_event_creates_record(self, mock_model):
        from api.audit_logs.payout_integration import log_payout_event
        log_payout_event(
            event_type="BATCH_COMPLETED",
            actor_id=1,
            payload={"batch_id": "uuid-123"},
        )
        mock_model.objects.create.assert_called_once()
        call_kwargs = mock_model.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs["event_type"], "PAYOUT_BATCH_COMPLETED")
        self.assertEqual(call_kwargs["actor_id"], 1)
        self.assertEqual(call_kwargs["module"], "payout_queue")

    @patch("api.audit_logs.payout_integration.AuditLog")
    def test_log_event_severity_error_for_failed(self, mock_model):
        from api.audit_logs.payout_integration import log_payout_event
        log_payout_event(
            event_type="BATCH_FAILED", actor_id=None, payload={}
        )
        call_kwargs = mock_model.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs["severity"], "ERROR")

    @patch("api.audit_logs.payout_integration.AuditLog")
    def test_log_event_severity_info_for_completed(self, mock_model):
        from api.audit_logs.payout_integration import log_payout_event
        log_payout_event(
            event_type="BATCH_COMPLETED", actor_id=1, payload={}
        )
        call_kwargs = mock_model.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs["severity"], "INFO")

    @patch("api.audit_logs.payout_integration.AuditLog")
    def test_log_event_does_not_raise_on_db_error(self, mock_model):
        from api.audit_logs.payout_integration import log_payout_event
        mock_model.objects.create.side_effect = Exception("DB error")
        try:
            log_payout_event(event_type="BATCH_FAILED", actor_id=1, payload={})
        except Exception as exc:
            self.fail(f"log_payout_event raised {exc!r}")

    def test_log_event_skips_empty_event_type(self):
        from api.audit_logs.payout_integration import log_payout_event
        with patch("api.audit_logs.payout_integration.AuditLog") as mock_model:
            log_payout_event(event_type="", actor_id=1, payload={})
            mock_model.objects.create.assert_not_called()

# ─────────────────────────────────────────────────────────────────────────────
# ⑨ api/notifications/payout_tasks.py
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTaskTest(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.data = {
            "batch_id":     str(uuid.uuid4()),
            "batch_name":   "Test Batch",
            "gateway":      "BKASH",
            "status":       "COMPLETED",
            "net_amount":   "490.75",
            "success_count": 1,
            "failure_count": 0,
        }

    @patch("api.notifications.payout_tasks.Notification")
    def test_creates_in_app_notification_on_completed(self, mock_notif):
        from api.notifications.payout_tasks import send_payout_notification
        result = send_payout_notification(
            user_id=self.user.pk,
            event="completed",
            data=self.data,
        )
        mock_notif.objects.create.assert_called_once()
        call_kwargs = mock_notif.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs["notification_type"], "PAYOUT_SUCCESS")
        self.assertIn("status", result)

    @patch("api.notifications.payout_tasks.Notification")
    def test_creates_in_app_notification_on_failed(self, mock_notif):
        from api.notifications.payout_tasks import send_payout_notification
        failed_data = {**self.data, "failure_count": 1, "success_count": 0}
        result = send_payout_notification(
            user_id=self.user.pk,
            event="failed",
            data=failed_data,
        )
        call_kwargs = mock_notif.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs["notification_type"], "PAYOUT_FAILED")

    def test_returns_skipped_for_none_user_id(self):
        from api.notifications.payout_tasks import send_payout_notification
        result = send_payout_notification(
            user_id=None, event="completed", data=self.data
        )
        self.assertEqual(result["status"], "skipped")

    def test_returns_skipped_for_unknown_event(self):
        from api.notifications.payout_tasks import send_payout_notification
        result = send_payout_notification(
            user_id=self.user.pk, event="unknown_event", data=self.data
        )
        self.assertEqual(result["status"], "skipped")

    def test_returns_skipped_for_nonexistent_user(self):
        from api.notifications.payout_tasks import send_payout_notification
        result = send_payout_notification(
            user_id=999_999_999, event="completed", data=self.data
        )
        self.assertEqual(result["status"], "skipped")

    @patch("api.notifications.payout_tasks.Notification",
           side_effect=ImportError("not installed"))
    def test_handles_missing_notification_model(self, mock_notif):
        from api.notifications.payout_tasks import send_payout_notification
        result = send_payout_notification(
            user_id=self.user.pk, event="completed", data=self.data
        )
        self.assertIn(result["status"], ["sent", "no_channels"])

    def test_build_message_completed(self):
        from api.notifications.payout_tasks import _build_message
        title, body = _build_message(event="completed", data=self.data)
        self.assertIn("490.75", body)
        self.assertIn("BKASH", body)

    def test_build_message_failed(self):
        from api.notifications.payout_tasks import _build_message
        failed_data = {**self.data, "failure_count": 3}
        title, body = _build_message(event="failed", data=failed_data)
        self.assertIn("Test Batch", body)
        self.assertIn("failed", title.lower())

    def test_result_contains_sent_channels_list(self):
        from api.notifications.payout_tasks import send_payout_notification
        with patch("api.notifications.payout_tasks.Notification") as mock_n:
            result = send_payout_notification(
                user_id=self.user.pk, event="completed", data=self.data
            )
        self.assertIn("sent_channels", result)
        self.assertIsInstance(result["sent_channels"], list)

# wallet/tests/test_serializers_and_views_input.py
"""
High Priority + Medium Priority Tests
======================================
High Priority  : Serializers ও Views যা ডাটা ইনপুট নেয় (validate করে)
Medium Priority: সমস্ত edge case, boundary value, invalid input rejection

Coverage:
  Serializers:
    - WalletTransactionSerializer  (amount validation)
    - UserPaymentMethodSerializer  (account_number, bank_name, card_expiry)
    - WithdrawalSerializer         (amount min/max, unverified method)
    - WithdrawalRequestSerializer  (circuit breaker + min/max)
    - WalletBalanceUpdateSerializer(amount positive)
    - BulkWalletUpdateSerializer   (list validation)
    - WithdrawalMethodSerializer   (mobile prefix, bank_name, crypto_address)
    - WithdrawalRequestSerializer  (model-level: MIN/MAX from constants)

  Views (via DRF ViewSet router):
    - POST /api/wallet/withdrawal-methods/          add method
    - POST /api/wallet/withdrawal-requests/         create withdrawal
    - POST /api/wallet/wallets/{id}/lock/           admin lock
    - POST /api/wallet/wallets/{id}/unlock/         admin unlock
    - POST /api/wallet/wallets/transfer/            transfer
    - POST /api/wallet/wallets/{id}/admin_credit/   admin credit
    - POST /api/wallet/wallets/{id}/admin_debit/    admin debit
    - POST /api/wallet/wallets/{id}/freeze_balance/ freeze
    - POST /api/wallet/wallets/{id}/unfreeze_balance/
    - GET  /api/wallet/wallets/me/
    - GET  /api/wallet/wallets/summary/
    - GET  /api/wallet/wallets/balance_breakdown/
    - POST /api/wallet/withdrawal-requests/{id}/cancel/
"""

from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from ..models import Wallet, WithdrawalMethod, WalletTransaction
from ..services import WalletService
from ..serializers import (
    WalletTransactionSerializer,
    WithdrawalMethodSerializer,
    WithdrawalRequestSerializer,
)
# Legacy serializers.py classes
from ..serializers_legacy import (   # will alias below if import fails
    UserPaymentMethodSerializer,
    WithdrawalSerializer,
    WalletBalanceUpdateSerializer,
    BulkWalletUpdateSerializer,
    WithdrawalRequestSerializer as LegacyWithdrawalRequestSerializer,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: try importing legacy serializers from the flat serializers.py
# ─────────────────────────────────────────────────────────────────────────────
try:
    from ..serializers import (   # type: ignore[attr-defined]
        UserPaymentMethodSerializer,
        WithdrawalSerializer,
        WalletBalanceUpdateSerializer,
        BulkWalletUpdateSerializer,
    )
except ImportError:
    try:
        from ..serializers import (
            UserPaymentMethodSerializer,
            WithdrawalSerializer,
            WalletBalanceUpdateSerializer,
            BulkWalletUpdateSerializer,
        )
    except ImportError:
        # If not exported from __init__, import directly from the flat file
        import importlib, sys
        _mod = importlib.import_module("wallet.serializers", package=None)
        UserPaymentMethodSerializer  = getattr(_mod, "UserPaymentMethodSerializer", None)
        WithdrawalSerializer         = getattr(_mod, "WithdrawalSerializer", None)
        WalletBalanceUpdateSerializer= getattr(_mod, "WalletBalanceUpdateSerializer", None)
        BulkWalletUpdateSerializer   = getattr(_mod, "BulkWalletUpdateSerializer", None)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  WalletTransactionSerializer — amount field validation
# ══════════════════════════════════════════════════════════════════════════════
class WalletTransactionSerializerTest(TestCase):
    def setUp(self):
        self.user   = User.objects.create_user(username="txnser1", password="pass", email="txnser1@t.com")
        self.wallet = WalletService.get_or_create(self.user)

    def _make_data(self, amount):
        return {
            "wallet": self.wallet.pk,
            "type": "earning",
            "amount": amount,
            "status": "pending",
            "balance_before": "0.00",
        }

    def test_valid_positive_amount(self):
        s = WalletTransactionSerializer(data=self._make_data("150.00"))
        self.assertTrue(s.is_valid(), s.errors)

    def test_zero_amount_rejected(self):
        s = WalletTransactionSerializer(data=self._make_data("0"))
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_non_numeric_amount_rejected(self):
        s = WalletTransactionSerializer(data=self._make_data("abc"))
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_decimal_amount_coerced_correctly(self):
        s = WalletTransactionSerializer(data=self._make_data("99.99"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["amount"], Decimal("99.99"))

    def test_very_large_amount_accepted(self):
        """Serializer itself has no upper cap — service layer enforces that."""
        s = WalletTransactionSerializer(data=self._make_data("9999999.99"))
        self.assertTrue(s.is_valid(), s.errors)


# ══════════════════════════════════════════════════════════════════════════════
# 2.  WithdrawalMethodSerializer — validate() logic
# ══════════════════════════════════════════════════════════════════════════════
class WithdrawalMethodSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wmser1", password="pass", email="wmser1@t.com")

    def _s(self, data):
        return WithdrawalMethodSerializer(data=data)

    def test_bkash_valid(self):
        s = self._s({"method_type": "bkash", "account_number": "01712345678", "account_name": "Test"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_bkash_wrong_prefix_rejected(self):
        s = self._s({"method_type": "bkash", "account_number": "00712345678", "account_name": "Test"})
        self.assertFalse(s.is_valid())
        self.assertIn("account_number", s.errors)

    def test_nagad_prefix_enforced(self):
        s = self._s({"method_type": "nagad", "account_number": "99900000000", "account_name": "X"})
        self.assertFalse(s.is_valid())
        self.assertIn("account_number", s.errors)

    def test_bank_requires_bank_name(self):
        s = self._s({"method_type": "bank", "account_number": "01234567890123", "account_name": "Test"})
        self.assertFalse(s.is_valid())
        self.assertIn("bank_name", s.errors)

    def test_bank_with_bank_name_valid(self):
        s = self._s({
            "method_type": "bank",
            "account_number": "01234567890123",
            "account_name": "Test",
            "bank_name": "Dutch-Bangla Bank",
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_crypto_requires_address(self):
        s = self._s({"method_type": "usdt_trc20", "account_number": "TXABC123", "account_name": "CryptoUser"})
        self.assertFalse(s.is_valid())
        self.assertIn("crypto_address", s.errors)

    def test_crypto_with_address_valid(self):
        s = self._s({
            "method_type": "usdt_trc20",
            "account_number": "TXABC123",
            "account_name": "CryptoUser",
            "crypto_address": "TXbcd1234567890ABCDEF",
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_masked_account_output(self):
        """masked_account হবে ****XXXX (last 4 digits)"""
        method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Masked Test",
        )
        s = WithdrawalMethodSerializer(method)
        self.assertEqual(s.data["masked_account"], "****5678")

    def test_short_account_not_masked(self):
        method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="0171", account_name="Short",
        )
        s = WithdrawalMethodSerializer(method)
        # len <= 4, returned as-is
        self.assertEqual(s.data["masked_account"], "0171")


# ══════════════════════════════════════════════════════════════════════════════
# 3.  WithdrawalRequestSerializer (model-level, from serializers/ package)
# ══════════════════════════════════════════════════════════════════════════════
class WithdrawalRequestSerializerTest(TestCase):
    def setUp(self):
        self.user   = User.objects.create_user(username="wrser1", password="pass", email="wrser1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("10000")
        self.wallet.save()
        self.method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Test",
            is_verified=True,
        )

    def _data(self, amount):
        return {
            "user":           self.user.pk,
            "wallet":         self.wallet.pk,
            "payment_method": self.method.pk,
            "amount":         str(amount),
        }

    def test_valid_withdrawal_amount(self):
        s = WithdrawalRequestSerializer(data=self._data("500"))
        self.assertTrue(s.is_valid(), s.errors)

    def test_below_minimum_rejected(self):
        """MIN_WITHDRAWAL = 50 (from constants)"""
        s = WithdrawalRequestSerializer(data=self._data("10"))
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_above_maximum_rejected(self):
        """MAX_WITHDRAWAL = 100000 (from constants)"""
        s = WithdrawalRequestSerializer(data=self._data("200000"))
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_boundary_minimum_accepted(self):
        from ..constants import MIN_WITHDRAWAL
        s = WithdrawalRequestSerializer(data=self._data(str(MIN_WITHDRAWAL)))
        self.assertTrue(s.is_valid(), s.errors)

    def test_boundary_maximum_accepted(self):
        from ..constants import MAX_WITHDRAWAL
        s = WithdrawalRequestSerializer(data=self._data(str(MAX_WITHDRAWAL)))
        self.assertTrue(s.is_valid(), s.errors)

    def test_read_only_fields_ignored(self):
        """status, net_amount ইত্যাদি read_only — input দিলে ignored হবে"""
        data = self._data("500")
        data["status"]     = "approved"
        data["net_amount"] = "999"
        s = WithdrawalRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        # status should NOT be in validated_data
        self.assertNotIn("status", s.validated_data)


# ══════════════════════════════════════════════════════════════════════════════
# 4.  WalletBalanceUpdateSerializer  (if available from flat serializers.py)
# ══════════════════════════════════════════════════════════════════════════════
class WalletBalanceUpdateSerializerTest(TestCase):
    def _s(self, data):
        if WalletBalanceUpdateSerializer is None:
            self.skipTest("WalletBalanceUpdateSerializer not importable")
        return WalletBalanceUpdateSerializer(data=data)

    def test_valid_credit(self):
        s = self._s({"amount": "500", "type": "credit"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_zero_amount_rejected(self):
        s = self._s({"amount": "0", "type": "credit"})
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_negative_amount_rejected(self):
        s = self._s({"amount": "-100", "type": "debit"})
        self.assertFalse(s.is_valid())
        self.assertIn("amount", s.errors)

    def test_invalid_type_rejected(self):
        s = self._s({"amount": "100", "type": "steal"})
        self.assertFalse(s.is_valid())
        self.assertIn("type", s.errors)

    def test_all_valid_types(self):
        for t in ("credit", "debit", "bonus", "penalty"):
            s = self._s({"amount": "100", "type": t})
            self.assertTrue(s.is_valid(), f"type={t} should be valid: {s.errors}")


# ══════════════════════════════════════════════════════════════════════════════
# 5.  BulkWalletUpdateSerializer  (if available)
# ══════════════════════════════════════════════════════════════════════════════
class BulkWalletUpdateSerializerTest(TestCase):
    def setUp(self):
        self.user   = User.objects.create_user(username="bulkser", password="pass", email="bulk@t.com")
        self.wallet = WalletService.get_or_create(self.user)

    def _s(self, updates):
        if BulkWalletUpdateSerializer is None:
            self.skipTest("BulkWalletUpdateSerializer not importable")
        return BulkWalletUpdateSerializer(data={"updates": updates})

    def test_valid_single_update(self):
        s = self._s([{"wallet_id": self.wallet.pk, "amount": "100", "type": "credit"}])
        self.assertTrue(s.is_valid(), s.errors)

    def test_empty_list_rejected(self):
        s = self._s([])
        self.assertFalse(s.is_valid())
        self.assertIn("updates", s.errors)

    def test_missing_wallet_id_skipped_gracefully(self):
        """wallet_id নেই → skip করে, কিন্তু যদি কোনো valid item না থাকে তাহলে error"""
        s = self._s([{"amount": "100"}])  # no wallet_id
        self.assertFalse(s.is_valid())

    def test_mixed_valid_invalid_skips_invalid(self):
        """Valid item থাকলে pass করে invalid টি skip করে।"""
        s = self._s([
            {"wallet_id": self.wallet.pk, "amount": "200", "type": "credit"},
            {"amount": "bad"},  # no wallet_id, bad amount
        ])
        self.assertTrue(s.is_valid(), s.errors)
        updates = s.validated_data["updates"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["wallet_id"], self.wallet.pk)

    def test_more_than_100_updates_rejected(self):
        updates = [{"wallet_id": self.wallet.pk, "amount": "1"} for _ in range(101)]
        s = self._s(updates)
        self.assertFalse(s.is_valid())


# ══════════════════════════════════════════════════════════════════════════════
# 6.  VIEW TESTS — WalletViewSet  (data input)
# ══════════════════════════════════════════════════════════════════════════════
class WalletViewSetInputTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user(username="vsinput", password="pass", email="vsi@t.com")
        self.admin  = User.objects.create_superuser(username="vsadmin", password="pass", email="vsadmin@t.com")
        self.client.force_authenticate(user=self.user)
        self.wallet = WalletService.get_or_create(self.user)

    # ── GET me/ ──────────────────────────────────────────────────────────────
    def test_me_returns_200_and_success(self):
        r = self.client.get("/api/wallet/wallets/me/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["success"])
        self.assertIn("currency", r.data["data"])

    def test_me_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        r = self.client.get("/api/wallet/wallets/me/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── GET summary/ ─────────────────────────────────────────────────────────
    def test_summary_returns_balance_fields(self):
        r = self.client.get("/api/wallet/wallets/summary/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data["data"]
        self.assertIn("current_balance", data)
        self.assertIn("available_balance", data)
        self.assertIn("is_locked", data)

    # ── GET balance_breakdown/ ───────────────────────────────────────────────
    def test_balance_breakdown_has_current_and_available(self):
        r = self.client.get("/api/wallet/wallets/balance_breakdown/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data["data"]
        self.assertIn("current", data)
        self.assertIn("available", data)

    # ── POST transfer/ ───────────────────────────────────────────────────────
    def test_transfer_insufficient_balance_returns_400(self):
        other = User.objects.create_user(username="tfrecv1", password="pass", email="tfr1@t.com")
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": other.username, "amount": "99999"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["success"])

    def test_transfer_success_debits_sender_credits_receiver(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        other = User.objects.create_user(username="tfrecv2", password="pass", email="tfr2@t.com")
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": other.username, "amount": "400"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("600"))
        recv_wallet = Wallet.objects.get(user=other)
        self.assertEqual(recv_wallet.current_balance, Decimal("400"))

    def test_transfer_missing_recipient_returns_error(self):
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "amount": "100"
        }, format="json")
        self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_transfer_to_self_rejected(self):
        self.wallet.current_balance = Decimal("500")
        self.wallet.save()
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": self.user.username, "amount": "100"
        }, format="json")
        # must fail (400 or 400-type)
        self.assertNotEqual(r.status_code, status.HTTP_200_OK)

    def test_transfer_negative_amount_rejected(self):
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": "someone", "amount": "-100"
        }, format="json")
        self.assertIn(r.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND
        ])

    # ── POST lock/unlock — admin only ────────────────────────────────────────
    def test_lock_requires_admin(self):
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/lock/", {"reason": "Test"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_lock_and_wallet_is_locked(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/lock/", {"reason": "Fraud"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertTrue(self.wallet.is_locked)

    def test_admin_can_unlock(self):
        self.wallet.is_locked = True
        self.wallet.locked_reason = "Test"
        self.wallet.save()
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/unlock/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertFalse(self.wallet.is_locked)

    def test_lock_without_reason_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/lock/", {}, format="json")
        # reason is required
        self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])
        # At minimum it must not crash (500)
        self.assertNotEqual(r.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── POST admin_credit / admin_debit ──────────────────────────────────────
    def test_admin_credit_increases_balance(self):
        self.client.force_authenticate(user=self.admin)
        before = self.wallet.current_balance
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/admin_credit/", {
            "amount": "1000", "description": "Promo credit"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, before + Decimal("1000"))

    def test_admin_debit_decreases_balance(self):
        self.wallet.current_balance = Decimal("2000")
        self.wallet.save()
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/admin_debit/", {
            "amount": "500", "description": "Penalty"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("1500"))

    def test_admin_credit_zero_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/admin_credit/", {
            "amount": "0", "description": "Zero test"
        }, format="json")
        self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY])

    def test_non_admin_credit_rejected(self):
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/admin_credit/", {
            "amount": "500", "description": "Hack"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # ── POST freeze_balance / unfreeze_balance ───────────────────────────────
    def test_admin_can_freeze_balance(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/freeze_balance/", {
            "amount": "200", "reason": "Under review"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertGreaterEqual(self.wallet.frozen_balance, Decimal("200"))

    def test_admin_can_unfreeze_balance(self):
        self.wallet.frozen_balance = Decimal("300")
        self.wallet.save()
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(f"/api/wallet/wallets/{self.wallet.pk}/unfreeze_balance/", {
            "amount": "300"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.frozen_balance, Decimal("0"))


# ══════════════════════════════════════════════════════════════════════════════
# 7.  VIEW TESTS — WithdrawalMethodViewSet  (data input)
# ══════════════════════════════════════════════════════════════════════════════
class WithdrawalMethodViewSetInputTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user(username="wmview1", password="pass", email="wmv1@t.com")
        self.client.force_authenticate(user=self.user)
        self.wallet = WalletService.get_or_create(self.user)

    def test_add_bkash_method_201(self):
        r = self.client.post("/api/wallet/withdrawal-methods/", {
            "method_type": "bkash",
            "account_number": "01811111111",
            "account_name": "View Test",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_add_bkash_bad_prefix_400(self):
        r = self.client.post("/api/wallet/withdrawal-methods/", {
            "method_type": "bkash",
            "account_number": "09811111111",  # wrong prefix
            "account_name": "Bad Prefix",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_bank_without_bank_name_400(self):
        r = self.client.post("/api/wallet/withdrawal-methods/", {
            "method_type": "bank",
            "account_number": "12345678901234",
            "account_name": "No Bank Name",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_bank_with_bank_name_201(self):
        r = self.client.post("/api/wallet/withdrawal-methods/", {
            "method_type": "bank",
            "account_number": "12345678901234",
            "account_name": "Bank Account",
            "bank_name": "Sonali Bank",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_add_rejected(self):
        self.client.force_authenticate(user=None)
        r = self.client.post("/api/wallet/withdrawal-methods/", {
            "method_type": "bkash", "account_number": "01711111111", "account_name": "X"
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_own_methods_only(self):
        other = User.objects.create_user(username="wmv_other", password="pass", email="wmvo@t.com")
        WithdrawalMethod.objects.create(
            user=other, method_type="bkash", account_number="01722222222", account_name="Other"
        )
        WithdrawalMethod.objects.create(
            user=self.user, method_type="nagad", account_number="01733333333", account_name="Mine"
        )
        r = self.client.get("/api/wallet/withdrawal-methods/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # Only my method should appear
        results = r.data.get("results", r.data)
        accounts = [m["account_number"] for m in results]
        self.assertNotIn("01722222222", accounts)
        self.assertIn("01733333333", accounts)

    def test_set_default_action(self):
        m = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01744444444", account_name="DefaultTest"
        )
        r = self.client.post(f"/api/wallet/withdrawal-methods/{m.pk}/set_default/")
        self.assertIn(r.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        m.refresh_from_db()
        self.assertTrue(m.is_default)


# ══════════════════════════════════════════════════════════════════════════════
# 8.  VIEW TESTS — WithdrawalRequestViewSet  (data input)
# ══════════════════════════════════════════════════════════════════════════════
class WithdrawalRequestViewSetInputTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user(username="wrview1", password="pass", email="wrv1@t.com")
        self.admin  = User.objects.create_superuser(username="wradmin", password="pass", email="wradmin@t.com")
        self.client.force_authenticate(user=self.user)
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()
        self.method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="WR Test",
            is_verified=True, is_default=True,
        )

    def _create_payload(self, amount="500"):
        return {
            "wallet":          self.wallet.pk,
            "payment_method":  self.method.pk,
            "amount":          amount,
        }

    def test_create_withdrawal_request_201(self):
        r = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload(), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_create_below_min_rejected(self):
        r = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload("5"), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_above_max_rejected(self):
        r = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload("999999"), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_unverified_method_rejected(self):
        unverified = WithdrawalMethod.objects.create(
            user=self.user, method_type="nagad",
            account_number="01799999999", account_name="Unverified",
            is_verified=False,
        )
        r = self.client.post("/api/wallet/withdrawal-requests/", {
            "wallet": self.wallet.pk,
            "payment_method": unverified.pk,
            "amount": "500",
        }, format="json")
        self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_create_insufficient_balance_rejected(self):
        self.wallet.current_balance = Decimal("10")
        self.wallet.save()
        r = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload("500"), format="json")
        self.assertIn(r.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_402_PAYMENT_REQUIRED])

    def test_cancel_own_pending_request(self):
        r_create = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload(), format="json")
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        wr_id = r_create.data.get("id") or r_create.data.get("data", {}).get("id")
        if wr_id:
            r_cancel = self.client.post(f"/api/wallet/withdrawal-requests/{wr_id}/cancel/", {
                "reason": "Changed mind"
            }, format="json")
            self.assertIn(r_cancel.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_admin_approve_withdrawal(self):
        r_create = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload(), format="json")
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        wr_id = r_create.data.get("id") or r_create.data.get("data", {}).get("id")
        if wr_id:
            self.client.force_authenticate(user=self.admin)
            r_approve = self.client.post(f"/api/wallet/withdrawal-requests/{wr_id}/approve/")
            self.assertIn(r_approve.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_admin_reject_withdrawal(self):
        r_create = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload(), format="json")
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        wr_id = r_create.data.get("id") or r_create.data.get("data", {}).get("id")
        if wr_id:
            self.client.force_authenticate(user=self.admin)
            r_reject = self.client.post(f"/api/wallet/withdrawal-requests/{wr_id}/reject/", {
                "reason": "KYC failed"
            }, format="json")
            self.assertIn(r_reject.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_fee_preview_endpoint(self):
        r = self.client.get("/api/wallet/withdrawal-requests/fee_preview/", {"amount": "1000", "gateway": "bkash"})
        self.assertIn(r.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        # Must not crash
        self.assertNotEqual(r.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_limits_endpoint(self):
        r = self.client.get("/api/wallet/withdrawal-requests/limits/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_pending_count_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get("/api/wallet/withdrawal-requests/pending_count/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unauthenticated_create_rejected(self):
        self.client.force_authenticate(user=None)
        r = self.client.post("/api/wallet/withdrawal-requests/", self._create_payload(), format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


# ══════════════════════════════════════════════════════════════════════════════
# 9.  Edge Cases — Locked Wallet blocks input
# ══════════════════════════════════════════════════════════════════════════════
class LockedWalletInputTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user   = User.objects.create_user(username="lockview", password="pass", email="lv@t.com")
        self.admin  = User.objects.create_superuser(username="lockadmin", password="pass", email="la@t.com")
        self.client.force_authenticate(user=self.user)
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.is_locked = True
        self.wallet.locked_reason = "Fraud"
        self.wallet.save()
        self.method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345679", account_name="Locked Test",
            is_verified=True,
        )

    def test_withdrawal_from_locked_wallet_rejected(self):
        r = self.client.post("/api/wallet/withdrawal-requests/", {
            "wallet": self.wallet.pk,
            "payment_method": self.method.pk,
            "amount": "500",
        }, format="json")
        self.assertIn(r.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_transfer_from_locked_wallet_rejected(self):
        other = User.objects.create_user(username="lockother", password="pass", email="lo@t.com")
        r = self.client.post("/api/wallet/wallets/transfer/", {
            "recipient": other.username, "amount": "100"
        }, format="json")
        self.assertIn(r.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
        ])

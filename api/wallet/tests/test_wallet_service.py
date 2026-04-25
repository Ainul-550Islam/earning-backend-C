# api/wallet/tests/test_wallet_service.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet
from ..services import WalletService
from ..exceptions import WalletLockedError, InsufficientBalanceError, InvalidAmountError

User = get_user_model()


class WalletServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wstest", password="pass", email="ws@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_get_or_create_creates_wallet(self):
        self.assertIsNotNone(self.wallet)
        self.assertEqual(self.wallet.user, self.user)

    def test_credit_increases_balance(self):
        WalletService.credit(self.wallet, Decimal("500"), txn_type="earning")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("500"))

    def test_credit_updates_total_earned(self):
        WalletService.credit(self.wallet, Decimal("300"), txn_type="earning")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_earned, Decimal("300"))

    def test_credit_records_balance_snapshot(self):
        WalletService.credit(self.wallet, Decimal("200"), txn_type="earning")
        from ..models import WalletTransaction
        txn = WalletTransaction.objects.filter(wallet=self.wallet).last()
        self.assertEqual(txn.balance_before, Decimal("0"))
        self.assertEqual(txn.balance_after, Decimal("200"))

    def test_credit_locked_wallet_raises(self):
        self.wallet.lock("Test")
        with self.assertRaises(WalletLockedError):
            WalletService.credit(self.wallet, Decimal("100"), txn_type="earning")

    def test_credit_zero_raises(self):
        with self.assertRaises(InvalidAmountError):
            WalletService.credit(self.wallet, Decimal("0"), txn_type="earning")

    def test_credit_negative_raises(self):
        with self.assertRaises(InvalidAmountError):
            WalletService.credit(self.wallet, Decimal("-50"), txn_type="earning")

    def test_credit_increments_version(self):
        v0 = self.wallet.version
        WalletService.credit(self.wallet, Decimal("100"), txn_type="earning")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.version, v0 + 1)

    def test_credit_idempotency_no_double_credit(self):
        WalletService.credit(self.wallet, Decimal("500"), idempotency_key="idem-001")
        WalletService.credit(self.wallet, Decimal("500"), idempotency_key="idem-001")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("500"))

    def test_debit_moves_to_pending(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        WalletService.debit(self.wallet, Decimal("400"))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("600"))
        self.assertEqual(self.wallet.pending_balance, Decimal("400"))

    def test_debit_insufficient_raises(self):
        self.wallet.current_balance = Decimal("100")
        self.wallet.save()
        with self.assertRaises(InsufficientBalanceError):
            WalletService.debit(self.wallet, Decimal("500"))

    def test_debit_locked_raises(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        self.wallet.lock("Fraud")
        with self.assertRaises(WalletLockedError):
            WalletService.debit(self.wallet, Decimal("100"))

    def test_transfer_success(self):
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()
        other = User.objects.create_user(username="recv", password="pass", email="recv@test.com")
        result = WalletService.transfer(self.user, other, Decimal("300"))
        self.wallet.refresh_from_db()
        other_wallet = Wallet.objects.get(user=other)
        self.assertEqual(self.wallet.current_balance, Decimal("700"))
        self.assertEqual(other_wallet.current_balance, Decimal("300"))
        self.assertIn("debit_txn", result)

    def test_transfer_insufficient_raises(self):
        other = User.objects.create_user(username="recv2", password="pass", email="recv2@test.com")
        with self.assertRaises(InsufficientBalanceError):
            WalletService.transfer(self.user, other, Decimal("9999"))

    def test_get_summary_returns_all_fields(self):
        self.wallet.current_balance = Decimal("500")
        self.wallet.save()
        summary = WalletService.get_summary(self.user)
        self.assertIn("current_balance", summary)
        self.assertIn("available_balance", summary)
        self.assertIn("total_earned", summary)
        self.assertFalse(summary["is_locked"])

    def test_admin_credit(self):
        admin = User.objects.create_superuser(username="admin1", password="pass", email="admin1@test.com")
        WalletService.admin_credit(self.wallet, Decimal("1000"), "Test credit", admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("1000"))

    def test_admin_debit(self):
        self.wallet.current_balance = Decimal("500")
        self.wallet.save()
        admin = User.objects.create_superuser(username="admin2", password="pass", email="admin2@test.com")
        WalletService.admin_debit(self.wallet, Decimal("200"), "Test debit", admin)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("300"))

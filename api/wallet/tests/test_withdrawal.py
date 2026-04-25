# api/wallet/tests/test_withdrawal.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WithdrawalRequest, WithdrawalMethod
from ..services import WalletService, WithdrawalService
from ..exceptions import WalletLockedError, InsufficientBalanceError

User = get_user_model()


class WithdrawalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wdtest", password="pass", email="wd@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()
        self.method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Test",
            is_verified=True, is_default=True,
        )

    def test_create_withdrawal(self):
        wr = WithdrawalService.create(self.wallet, Decimal("500"), self.method, created_by=self.user)
        self.assertEqual(wr.status, "pending")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.pending_balance, Decimal("500"))
        self.assertGreater(wr.fee, Decimal("0"))

    def test_create_deducts_from_current(self):
        WithdrawalService.create(self.wallet, Decimal("1000"), self.method)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("4000"))

    def test_approve_withdrawal(self):
        wr = WithdrawalService.create(self.wallet, Decimal("500"), self.method)
        admin = User.objects.create_superuser(username="wadmin", password="pass", email="wa@test.com")
        WithdrawalService.approve(wr, by=admin)
        wr.refresh_from_db()
        self.assertEqual(wr.status, "approved")

    def test_complete_updates_totals(self):
        wr = WithdrawalService.create(self.wallet, Decimal("500"), self.method)
        WithdrawalService.approve(wr)
        WithdrawalService.complete(wr, "GW-12345")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.total_withdrawn, Decimal("500"))
        self.assertEqual(self.wallet.pending_balance, Decimal("0"))

    def test_reject_refunds_balance(self):
        wr = WithdrawalService.create(self.wallet, Decimal("500"), self.method)
        bal_before = self.wallet.current_balance
        self.wallet.refresh_from_db()
        WithdrawalService.reject(wr, "KYC fail")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("5000"))
        self.assertEqual(self.wallet.pending_balance, Decimal("0"))

    def test_cancel_refunds(self):
        wr = WithdrawalService.create(self.wallet, Decimal("500"), self.method)
        WithdrawalService.cancel(wr, "Changed mind")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("5000"))

    def test_locked_wallet_raises(self):
        self.wallet.lock("Fraud")
        with self.assertRaises(WalletLockedError):
            WithdrawalService.create(self.wallet, Decimal("100"), self.method)

    def test_insufficient_raises(self):
        with self.assertRaises(Exception):
            WithdrawalService.create(self.wallet, Decimal("99999"), self.method)

# api/wallet/tests/test_ledger.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WalletLedger, LedgerEntry
from ..services import WalletService, LedgerService

User = get_user_model()


class LedgerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ledger", password="pass", email="lg@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_credit_creates_ledger(self):
        WalletService.credit(self.wallet, Decimal("500"), txn_type="earning")
        ledgers = WalletLedger.objects.filter(wallet=self.wallet)
        self.assertTrue(ledgers.exists())

    def test_ledger_has_two_entries(self):
        WalletService.credit(self.wallet, Decimal("300"), txn_type="earning")
        ledger = WalletLedger.objects.filter(wallet=self.wallet).first()
        self.assertEqual(ledger.entries.count(), 2)

    def test_ledger_is_balanced(self):
        WalletService.credit(self.wallet, Decimal("750"), txn_type="earning")
        ledger = WalletLedger.objects.filter(wallet=self.wallet).first()
        self.assertTrue(ledger.is_balanced)

    def test_debit_credit_equal(self):
        WalletService.credit(self.wallet, Decimal("400"), txn_type="earning")
        ledger = WalletLedger.objects.filter(wallet=self.wallet).first()
        debits  = sum(e.amount for e in ledger.entries.filter(entry_type="debit"))
        credits = sum(e.amount for e in ledger.entries.filter(entry_type="credit"))
        self.assertEqual(debits, credits)

    def test_ledger_entry_immutable(self):
        WalletService.credit(self.wallet, Decimal("100"), txn_type="earning")
        entry = LedgerEntry.objects.filter(ledger__wallet=self.wallet).first()
        with self.assertRaises(ValueError):
            entry.save()

    def test_reconcile_ok(self):
        WalletService.credit(self.wallet, Decimal("500"), txn_type="earning")
        result = LedgerService.reconcile(self.wallet)
        self.assertIn("status", result)
        self.assertIn("discrepancy", result)

    def test_account_balance(self):
        WalletService.credit(self.wallet, Decimal("300"), txn_type="earning")
        bal = LedgerService.get_account_balance(self.wallet, "user_balance")
        self.assertGreaterEqual(bal, Decimal("0"))

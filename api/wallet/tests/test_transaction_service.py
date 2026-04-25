# api/wallet/tests/test_transaction_service.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WalletTransaction
from ..services import WalletService, TransactionService

User = get_user_model()


class TransactionServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="txntest", password="pass", email="txn@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("1000")
        self.wallet.save()

    def test_approve_pending_transaction(self):
        txn = WalletTransaction.objects.create(
            wallet=self.wallet, type="earning", amount=Decimal("100"),
            status="pending", balance_before=Decimal("1000"),
        )
        approved = TransactionService.approve(txn.id)
        self.assertEqual(approved.status, "approved")
        self.assertIsNotNone(approved.approved_at)

    def test_reject_pending_transaction(self):
        txn = WalletTransaction.objects.create(
            wallet=self.wallet, type="withdrawal", amount=-Decimal("200"),
            status="pending", balance_before=Decimal("1000"),
        )
        rejected = TransactionService.reject(txn.id, "Insufficient docs")
        self.assertEqual(rejected.status, "rejected")
        self.assertIn("Insufficient docs", rejected.description)

    def test_reverse_approved_transaction(self):
        WalletService.credit(self.wallet, Decimal("300"), txn_type="earning")
        txn = WalletTransaction.objects.filter(wallet=self.wallet, type="earning").last()
        reversal = TransactionService.reverse(txn.id, "Error in earning")
        self.assertTrue(txn.__class__.objects.get(pk=txn.pk).is_reversed)
        self.assertEqual(reversal.type, "reversal")
        self.assertEqual(reversal.amount, -Decimal("300"))

    def test_get_history_filters(self):
        WalletService.credit(self.wallet, Decimal("100"), txn_type="earning")
        WalletService.credit(self.wallet, Decimal("50"), txn_type="bonus")
        history = TransactionService.get_history(self.wallet, type="earning")
        self.assertTrue(all(t.type == "earning" for t in history))

    def test_idempotency_prevents_duplicate(self):
        TransactionService.create(
            self.wallet, "earning", Decimal("200"), idempotency_key="txn-idem-001"
        )
        TransactionService.create(
            self.wallet, "earning", Decimal("200"), idempotency_key="txn-idem-001"
        )
        self.wallet.refresh_from_db()
        total = WalletTransaction.objects.filter(
            wallet=self.wallet, idempotency_key="txn-idem-001"
        ).count()
        self.assertEqual(total, 1)

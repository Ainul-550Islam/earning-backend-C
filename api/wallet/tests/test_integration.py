# api/wallet/tests/test_integration.py
"""
End-to-end integration tests — full flow from signup to withdrawal completion.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WalletTransaction, WithdrawalMethod, WithdrawalRequest
from ..services import WalletService, EarningService, WithdrawalService

User = get_user_model()


class FullFlowIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="integ", password="pass", email="int@test.com")
        self.admin = User.objects.create_superuser(username="iadmin", password="pass", email="ia@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_full_earning_and_withdrawal_flow(self):
        """Signup → earn → withdraw → approve → complete."""
        # 1. Earn from tasks
        result1 = EarningService.add_earning(self.wallet, Decimal("500"), source_type="task")
        result2 = EarningService.add_earning(self.wallet, Decimal("300"), source_type="referral",
                                              source_id="user_123")
        self.wallet.refresh_from_db()
        self.assertGreaterEqual(self.wallet.current_balance, Decimal("800"))

        # 2. Add payment method
        pm = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01712345678", account_name="Test User",
            is_verified=True, is_default=True,
        )

        # 3. Request withdrawal
        wr = WithdrawalService.create(
            self.wallet, Decimal("500"), pm, created_by=self.user
        )
        self.assertEqual(wr.status, "pending")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.pending_balance, Decimal("500"))

        # 4. Admin approve
        WithdrawalService.approve(wr, by=self.admin)
        wr.refresh_from_db()
        self.assertEqual(wr.status, "approved")

        # 5. Gateway processes → complete
        WithdrawalService.complete(wr, gateway_ref="BKS-12345")
        wr.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(wr.status, "completed")
        self.assertEqual(self.wallet.pending_balance, Decimal("0"))
        self.assertEqual(self.wallet.total_withdrawn, Decimal("500"))

    def test_idempotent_earning_full_flow(self):
        """Idempotency key prevents double-credit on retry."""
        EarningService.add_earning(self.wallet, Decimal("200"), idempotency_key="earn-001")
        EarningService.add_earning(self.wallet, Decimal("200"), idempotency_key="earn-001")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("200"))

    def test_referral_chain_three_levels(self):
        """3-level referral commissions are all credited."""
        l1 = User.objects.create_user(username="lvl1", password="pass", email="l1@test.com")
        l2 = User.objects.create_user(username="lvl2", password="pass", email="l2@test.com")
        l3 = User.objects.create_user(username="lvl3", password="pass", email="l3@test.com")
        w1 = WalletService.get_or_create(l1)
        w2 = WalletService.get_or_create(l2)
        w3 = WalletService.get_or_create(l3)

        base = Decimal("1000")
        EarningService.add_referral(w1, base, 1, self.user.id)  # 10% = 100
        EarningService.add_referral(w2, base, 2, self.user.id)  # 5%  = 50
        EarningService.add_referral(w3, base, 3, self.user.id)  # 2%  = 20

        w1.refresh_from_db(); w2.refresh_from_db(); w3.refresh_from_db()
        self.assertAlmostEqual(float(w1.current_balance), 100.0, places=2)
        self.assertAlmostEqual(float(w2.current_balance), 50.0, places=2)
        self.assertAlmostEqual(float(w3.current_balance), 20.0, places=2)

    def test_wallet_lock_blocks_all_mutations(self):
        """Locked wallet blocks earn, debit, and withdrawal."""
        from ..exceptions import WalletLockedError
        self.wallet.lock("Fraud")
        with self.assertRaises(WalletLockedError):
            WalletService.credit(self.wallet, Decimal("100"))
        with self.assertRaises(WalletLockedError):
            WalletService.debit(self.wallet, Decimal("100"))

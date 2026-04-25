# api/wallet/tests/test_performance.py
"""
Performance tests — ensure critical queries stay within acceptable thresholds.
Uses assertNumQueries to detect N+1 regressions.
"""
import time
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WalletTransaction
from ..services import WalletService

User = get_user_model()


class PerformanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="perf", password="pass", email="p@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        # Pre-create transactions
        for i in range(50):
            WalletTransaction.objects.create(
                wallet=self.wallet, type="earning",
                amount=Decimal("10"), status="approved",
                balance_before=Decimal("0"), balance_after=Decimal("10"),
            )

    def test_transaction_list_query_count(self):
        """Transaction listing must not produce N+1 queries."""
        with self.assertNumQueries(2):  # 1 auth + 1 query
            list(WalletTransaction.objects.filter(
                wallet=self.wallet
            ).select_related("wallet", "wallet__user", "created_by", "approved_by")[:20])

    def test_wallet_summary_query_count(self):
        """Wallet summary must be fast — single wallet lookup."""
        with self.assertNumQueries(2):  # 1 auth + 1 wallet get
            WalletService.get_summary(self.user)

    def test_bulk_credit_performance(self):
        """100 sequential credits must complete within 10 seconds."""
        start = time.monotonic()
        for i in range(100):
            WalletService.credit(self.wallet, Decimal("1"), txn_type="earning")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 10.0, f"100 credits took {elapsed:.2f}s — too slow")

    def test_wallet_balance_optimistic_lock(self):
        """Verify version increments on each mutation."""
        v0 = self.wallet.version
        for _ in range(5):
            WalletService.credit(self.wallet, Decimal("1"))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.version, v0 + 5)

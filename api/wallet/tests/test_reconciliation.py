# api/wallet/tests/test_reconciliation.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, LedgerReconciliation
from ..services import WalletService, ReconciliationService

User = get_user_model()


class ReconciliationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="recon", password="pass", email="rc@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_run_one_creates_reconciliation_record(self):
        WalletService.credit(self.wallet, Decimal("500"))
        result = ReconciliationService.run_one(self.wallet)
        self.assertIn("status", result)
        self.assertTrue(LedgerReconciliation.objects.filter(wallet=self.wallet).exists())

    def test_run_all_returns_summary(self):
        result = ReconciliationService.run_all()
        self.assertIn("ok", result)
        self.assertIn("total", result)
        self.assertIn("errors", result)

    def test_resolve_discrepancy(self):
        WalletService.credit(self.wallet, Decimal("100"))
        ReconciliationService.run_one(self.wallet)
        recon = LedgerReconciliation.objects.filter(wallet=self.wallet).last()
        admin = User.objects.create_superuser(username="radmin", password="pass", email="ra@test.com")
        ReconciliationService.resolve(recon.id, "Fixed by admin", resolved_by=admin)
        recon.refresh_from_db()
        self.assertEqual(recon.status, "fixed")
        self.assertIsNotNone(recon.resolved_at)

    def test_get_unresolved_returns_discrepancies(self):
        qs = ReconciliationService.get_unresolved()
        self.assertIsNotNone(qs)

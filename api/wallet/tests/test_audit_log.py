# api/wallet/tests/test_audit_log.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..audit_log import AuditLogger

User = get_user_model()


class AuditLogTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="audadmin", email="aa@t.com", password="pass")

    def test_log_action_no_crash(self):
        # Should not raise even if model fails
        AuditLogger.log(action="wallet_locked", user_id=self.admin.id, target_id=1, detail="Test")

    def test_log_balance_change(self):
        from ..models.core import Wallet
        user = User.objects.create_user(username="atest", email="at@t.com", password="pass")
        from ..services.core.WalletService import WalletService
        wallet = WalletService.get_or_create(user)
        # Should not raise
        AuditLogger.log_balance_change(
            wallet, Decimal("0"), Decimal("500"), "admin_credit", self.admin.id, "Test credit"
        )

    def test_get_wallet_history_returns_list(self):
        result = AuditLogger.get_wallet_history(99999)  # Non-existent wallet
        self.assertIsNotNone(result)

    def test_log_admin_action(self):
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post("/admin/")
        request.user = self.admin
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        AuditLogger.log_admin_action(request, "wallet_locked", target_id=1, detail="Test")

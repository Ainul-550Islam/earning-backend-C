# api/wallet/tests/test_tasks.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WithdrawalRequest, WithdrawalMethod, BalanceBonus
from ..services import WalletService

User = get_user_model()


class TaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tasktest", password="pass", email="task@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_expire_bonus_balances_task(self):
        from django.utils import timezone
        from datetime import timedelta
        from ..tasks.bonus_expiry_tasks import expire_bonus_balances
        BalanceBonus.objects.create(
            wallet=self.wallet, amount=Decimal("100"),
            status="active", expires_at=timezone.now() - timedelta(hours=1)
        )
        self.wallet.bonus_balance = Decimal("100")
        self.wallet.save()
        result = expire_bonus_balances.apply().get()
        self.assertIn("expired_bonuses", result)

    def test_reset_daily_earning_caps_task(self):
        from ..tasks.earning_cap_reset_tasks import reset_daily_earning_caps
        result = reset_daily_earning_caps.apply().get()
        self.assertIn("status", result)
        self.assertEqual(result["status"], "ok")

    def test_cleanup_idempotency_keys_task(self):
        from ..tasks.cleanup_tasks import cleanup_idempotency_keys
        from ..models import IdempotencyKey
        from django.utils import timezone
        from datetime import timedelta
        IdempotencyKey.objects.create(
            key="old-idem-1", wallet=self.wallet,
            expires_at=timezone.now() - timedelta(hours=2)
        )
        result = cleanup_idempotency_keys.apply().get()
        self.assertIn("deleted", result)
        self.assertGreaterEqual(result["deleted"], 1)

    def test_compute_daily_liability_task(self):
        from ..tasks.liability_report_tasks import compute_daily_liability
        result = compute_daily_liability.apply().get()
        self.assertIn("total_liability", result)

    def test_auto_reject_stale_task(self):
        from ..tasks.withdrawal_processing_tasks import auto_reject_stale_withdrawals
        result = auto_reject_stale_withdrawals.apply(kwargs={"hours": 0}).get()
        self.assertIn("rejected", result)

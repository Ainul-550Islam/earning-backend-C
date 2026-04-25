# api/wallet/tests/test_earning_caps.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, EarningCap
from ..services import WalletService, EarningService, EarningCapService
from ..exceptions import InvalidAmountError

User = get_user_model()


class EarningCapTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="captest", password="pass", email="cap@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_earning_without_cap_succeeds(self):
        result = EarningService.add_earning(self.wallet, Decimal("100"), source_type="task")
        self.assertIsNotNone(result["txn"])

    def test_cap_blocks_excess_earning(self):
        EarningCap.objects.create(
            cap_type="global", cap_amount=Decimal("50"),
            is_active=True,
        )
        EarningService.add_earning(self.wallet, Decimal("50"), source_type="task")
        with self.assertRaises(InvalidAmountError):
            EarningService.add_earning(self.wallet, Decimal("50"), source_type="task")

    def test_get_cap_status_returns_dict(self):
        data = EarningCapService.get_cap_status(self.wallet, "task")
        self.assertIn("task", data)
        self.assertIn("cap", data["task"])
        self.assertIn("earned_today", data["task"])

    def test_check_returns_allowed_false_when_capped(self):
        EarningCap.objects.create(cap_type="global", cap_amount=Decimal("10"), is_active=True)
        # Manually create an earning record for today
        from ..models import EarningRecord
        from django.utils import timezone
        EarningRecord(
            wallet=self.wallet, source_type="task",
            amount=Decimal("10"), original_amount=Decimal("10"),
        ).save()
        allowed, remaining = EarningCapService.check(self.wallet, Decimal("1"), "task")
        self.assertFalse(allowed)
        self.assertEqual(remaining, Decimal("0"))

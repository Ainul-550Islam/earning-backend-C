# api/wallet/tests/test_withdrawal_fees.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import WithdrawalFee
from ..services import WithdrawalFeeService

User = get_user_model()


class WithdrawalFeeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feetest", password="pass", email="fee@test.com")
        WithdrawalFee.objects.create(
            gateway="bkash", tier="ALL",
            fee_type="percent", fee_percent=Decimal("2.00"),
            flat_fee=Decimal("0"), min_fee=Decimal("5"),
            max_fee=Decimal("100"), is_active=True,
        )

    def test_percent_fee_calculation(self):
        fee = WithdrawalFeeService.calculate(Decimal("1000"), "bkash", self.user)
        self.assertEqual(fee, Decimal("20.00"))

    def test_min_fee_applied(self):
        fee = WithdrawalFeeService.calculate(Decimal("100"), "bkash", self.user)
        self.assertGreaterEqual(fee, Decimal("5"))

    def test_max_fee_cap(self):
        fee = WithdrawalFeeService.calculate(Decimal("100000"), "bkash", self.user)
        self.assertLessEqual(fee, Decimal("100"))

    def test_diamond_tier_zero_fee(self):
        self.user.tier = "DIAMOND"
        fee = WithdrawalFeeService.calculate(Decimal("5000"), "bkash", self.user)
        self.assertEqual(fee, Decimal("0"))

    def test_fee_breakdown_dict(self):
        data = WithdrawalFeeService.get_fee_breakdown(Decimal("1000"), "bkash", self.user)
        self.assertIn("amount", data)
        self.assertIn("fee", data)
        self.assertIn("net_amount", data)
        self.assertEqual(data["amount"], 1000.0)

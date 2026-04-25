# api/wallet/tests/test_withdrawal_limits.py
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from ..models import Wallet, WithdrawalLimit
from ..services import WalletService, WithdrawalLimitService
from ..exceptions import InvalidAmountError, WithdrawalLimitError

User = get_user_model()


class WithdrawalLimitsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="limtest", password="pass", email="lim@test.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("100000")
        self.wallet.save()

    def test_below_minimum_raises(self):
        with self.assertRaises(InvalidAmountError):
            WithdrawalLimitService.validate(self.wallet, Decimal("10"))

    def test_above_maximum_raises(self):
        with self.assertRaises(InvalidAmountError):
            WithdrawalLimitService.validate(self.wallet, Decimal("200000"))

    def test_valid_amount_passes(self):
        WithdrawalLimitService.validate(self.wallet, Decimal("500"))

    def test_daily_limit_enforced(self):
        WithdrawalLimit.objects.create(
            tier="ALL", gateway="ALL", period="daily",
            limit_amount=Decimal("1000"), min_amount=Decimal("50"),
            max_single=Decimal("10000"), max_count=10, is_active=True,
        )
        with self.assertRaises(WithdrawalLimitError):
            WithdrawalLimitService.validate(self.wallet, Decimal("2000"))

    def test_get_remaining_returns_dict(self):
        result = WithdrawalLimitService.get_remaining(self.user, self.wallet)
        self.assertIsInstance(result, dict)

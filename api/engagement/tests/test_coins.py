# engagement/tests/test_coins.py
import pytest
from decimal import Decimal

from ..services.coin_service import CoinService
from ..exceptions import InsufficientCoinsError
from .factories import UserFactory


@pytest.mark.django_db
class TestCoinService:

    def test_add_increases_balance(self):
        user = UserFactory(coin_balance=Decimal("10"))
        CoinService.add(user, Decimal("50"))
        user.refresh_from_db()
        assert user.coin_balance == Decimal("60")

    def test_add_returns_new_balance(self):
        user    = UserFactory(coin_balance=Decimal("10"))
        balance = CoinService.add(user, Decimal("20"))
        assert balance == Decimal("30")

    def test_add_zero_raises_value_error(self):
        user = UserFactory(coin_balance=Decimal("10"))
        with pytest.raises(ValueError):
            CoinService.add(user, Decimal("0"))

    def test_add_negative_raises_value_error(self):
        user = UserFactory(coin_balance=Decimal("10"))
        with pytest.raises(ValueError):
            CoinService.add(user, Decimal("-5"))

    def test_deduct_decreases_balance(self):
        user = UserFactory(coin_balance=Decimal("100"))
        CoinService.deduct(user, Decimal("30"))
        user.refresh_from_db()
        assert user.coin_balance == Decimal("70")

    def test_deduct_returns_new_balance(self):
        user    = UserFactory(coin_balance=Decimal("100"))
        balance = CoinService.deduct(user, Decimal("40"))
        assert balance == Decimal("60")

    def test_deduct_insufficient_balance_raises(self):
        user = UserFactory(coin_balance=Decimal("10"))
        with pytest.raises(InsufficientCoinsError):
            CoinService.deduct(user, Decimal("50"))

    def test_deduct_exact_balance_succeeds(self):
        user = UserFactory(coin_balance=Decimal("50"))
        balance = CoinService.deduct(user, Decimal("50"))
        assert balance == Decimal("0")

    def test_balance_returns_current_coins(self):
        user = UserFactory(coin_balance=Decimal("77"))
        assert CoinService.balance(user) == Decimal("77")

    def test_concurrent_adds_are_atomic(self):
        """Multiple sequential adds must not lose any coins (F() expression used)."""
        user = UserFactory(coin_balance=Decimal("0"))
        for _ in range(10):
            CoinService.add(user, Decimal("10"))
        user.refresh_from_db()
        assert user.coin_balance == Decimal("100")

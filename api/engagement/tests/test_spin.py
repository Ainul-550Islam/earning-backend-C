# engagement/tests/test_spin.py
import pytest
from decimal import Decimal

from ..services.spin_service import SpinService
from ..models.spinwheel import SpinWheel
from ..exceptions import MaxSpinsReachedError
from ..constants import SPIN_MAX_PER_DAY
from .factories import UserFactory, SpinWheelFactory


@pytest.mark.django_db
class TestSpinService:

    def test_spin_creates_record(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        result = SpinService.spin(user)
        assert SpinWheel.objects.filter(user=user).count() == 1
        assert result["coins_won"] > 0

    def test_spin_adds_coins_to_balance(self):
        user    = UserFactory(coin_balance=Decimal("0"))
        result  = SpinService.spin(user)
        user.refresh_from_db()
        assert float(user.coin_balance) == result["new_balance"]

    def test_spin_remaining_decrements(self):
        user = UserFactory(coin_balance=Decimal("0"))
        SpinService.spin(user)
        assert SpinWheel.remaining_today(user) == SPIN_MAX_PER_DAY - 1

    def test_max_spins_raises_error(self):
        user = UserFactory(coin_balance=Decimal("0"))
        for _ in range(SPIN_MAX_PER_DAY):
            SpinService.spin(user)
        with pytest.raises(MaxSpinsReachedError):
            SpinService.spin(user)

    def test_can_spin_false_after_limit(self):
        user = UserFactory(coin_balance=Decimal("0"))
        for _ in range(SPIN_MAX_PER_DAY):
            SpinService.spin(user)
        assert SpinWheel.can_spin(user) is False

    def test_spin_outcome_within_valid_range(self):
        from ..constants import SPIN_OUTCOMES
        valid_coins = {c for c, _ in SPIN_OUTCOMES}
        user = UserFactory(coin_balance=Decimal("0"))
        for _ in range(20):
            SpinWheel.objects.all().delete()
            result = SpinService.spin(user)
            assert result["coins_won"] in valid_coins

    def test_spin_history_returns_list(self):
        user = UserFactory(coin_balance=Decimal("0"))
        SpinService.spin(user)
        history = SpinService.history(user, limit=10)
        assert isinstance(history, list)
        assert len(history) == 1
        assert "coins_won" in history[0]
        assert "spun_at" in history[0]

    def test_roll_boosted_doubles_coins(self):
        """_roll with boosted=True returns 2× the base outcome."""
        from ..services.spin_service import SpinService
        import random
        random.seed(42)
        coins_normal, idx = SpinService._roll(boosted=False)
        random.seed(42)
        coins_boosted, _ = SpinService._roll(boosted=True)
        assert coins_boosted == coins_normal * 2

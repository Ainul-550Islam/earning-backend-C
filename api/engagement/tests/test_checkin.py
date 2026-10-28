# engagement/tests/test_checkin.py
import pytest
from datetime import date, timedelta
from decimal import Decimal

from ..services.checkin_service import CheckInService
from ..models.checkin import DailyCheckIn
from ..exceptions import AlreadyCheckedInError
from .factories import UserFactory, DailyCheckInFactory


@pytest.mark.django_db
class TestCheckInService:

    def test_first_checkin_creates_record(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        result = CheckInService.process(user)
        assert result["consecutive_days"] == 1
        assert DailyCheckIn.objects.filter(user=user, date=date.today()).exists()

    def test_first_checkin_gives_base_coins(self):
        user   = UserFactory(coin_balance=Decimal("0"))
        result = CheckInService.process(user)
        assert result["coins_earned"] == 5.0   # day 1 = 5 * 1

    def test_second_day_streak_multiplied(self):
        user = UserFactory(coin_balance=Decimal("100"))
        # yesterday's check-in
        DailyCheckInFactory(user=user, date=date.today() - timedelta(days=1), consecutive_days=1)
        result = CheckInService.process(user)
        assert result["consecutive_days"] == 2
        assert result["coins_earned"] == 10.0  # 5 * 2

    def test_day_7_streak_caps_at_35(self):
        user = UserFactory(coin_balance=Decimal("100"))
        DailyCheckInFactory(user=user, date=date.today() - timedelta(days=1), consecutive_days=6)
        result = CheckInService.process(user)
        assert result["consecutive_days"] == 7
        assert result["coins_earned"] == 35.0  # 5 * 7

    def test_day_8_still_35_coins(self):
        """Streak bonus caps at day 7."""
        user = UserFactory(coin_balance=Decimal("100"))
        DailyCheckInFactory(user=user, date=date.today() - timedelta(days=1), consecutive_days=7)
        result = CheckInService.process(user)
        assert result["consecutive_days"] == 8
        assert result["coins_earned"] == 35.0  # still 5 * 7 (cap)

    def test_double_checkin_raises_error(self):
        user = UserFactory(coin_balance=Decimal("0"))
        CheckInService.process(user)
        with pytest.raises(AlreadyCheckedInError):
            CheckInService.process(user)

    def test_broken_streak_resets_to_1(self):
        user = UserFactory(coin_balance=Decimal("100"))
        # last check-in was 3 days ago (no yesterday)
        DailyCheckInFactory(user=user, date=date.today() - timedelta(days=3), consecutive_days=5)
        result = CheckInService.process(user)
        assert result["consecutive_days"] == 1
        assert result["coins_earned"] == 5.0

    def test_checkin_xp_earned_grows_with_streak(self):
        user = UserFactory(coin_balance=Decimal("100"))
        DailyCheckInFactory(user=user, date=date.today() - timedelta(days=1), consecutive_days=3)
        result = CheckInService.process(user)
        # xp = 10 + 5*(multiplier-1), multiplier = min(4,7) = 4 → 10+15 = 25
        assert result["xp_earned"] == 25

    def test_stats_returns_correct_streak(self):
        user = UserFactory(coin_balance=Decimal("0"))
        DailyCheckInFactory(user=user, date=date.today(), consecutive_days=5)
        stats = CheckInService.stats(user)
        assert stats["current_streak"] == 5
        assert stats["checked_in_today"] is True

    def test_stats_no_checkins(self):
        user  = UserFactory(coin_balance=Decimal("0"))
        stats = CheckInService.stats(user)
        assert stats["current_streak"] == 0
        assert stats["checked_in_today"] is False
        assert stats["total_checkins"] == 0

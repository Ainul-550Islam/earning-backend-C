# engagement/tests/test_leaderboard.py
import pytest
from datetime import date
from decimal import Decimal

from ..services.leaderboard_service import LeaderboardService
from ..models.leaderboard import Leaderboard, LeaderboardReward
from .factories import UserFactory, LeaderboardFactory, LeaderboardRewardFactory, SpinWheelFactory, DailyCheckInFactory


@pytest.mark.django_db
class TestLeaderboardService:

    def test_get_leaderboard_returns_ordered_list(self):
        today = date.today()
        u1 = UserFactory(coin_balance=Decimal("0"))
        u2 = UserFactory(coin_balance=Decimal("0"))
        LeaderboardFactory(user=u1, date=today, rank=1, total_coins_earned=Decimal("200"))
        LeaderboardFactory(user=u2, date=today, rank=2, total_coins_earned=Decimal("100"))
        entries = LeaderboardService.get_leaderboard(today)
        assert entries[0].rank == 1
        assert entries[1].rank == 2

    def test_get_user_rank_returns_correct_rank(self):
        today = date.today()
        user  = UserFactory(coin_balance=Decimal("0"))
        LeaderboardFactory(user=user, date=today, rank=3)
        rank = LeaderboardService.get_user_rank(user, today)
        assert rank == 3

    def test_get_user_rank_returns_none_if_not_ranked(self):
        user = UserFactory(coin_balance=Decimal("0"))
        rank = LeaderboardService.get_user_rank(user, date.today())
        assert rank is None

    def test_distribute_rewards_grants_coins(self):
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        user      = UserFactory(coin_balance=Decimal("0"))
        LeaderboardFactory(user=user, date=yesterday, rank=1, reward_distributed=False)
        LeaderboardRewardFactory(rank=1, season_type="daily", reward_coins=Decimal("100"))
        rewarded  = LeaderboardService.distribute_rewards(yesterday)
        assert rewarded == 1
        user.refresh_from_db()
        assert user.coin_balance == Decimal("100")

    def test_distribute_rewards_marks_distributed(self):
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        user      = UserFactory(coin_balance=Decimal("0"))
        entry     = LeaderboardFactory(user=user, date=yesterday, rank=1, reward_distributed=False)
        LeaderboardRewardFactory(rank=1, season_type="daily", reward_coins=Decimal("50"))
        LeaderboardService.distribute_rewards(yesterday)
        entry.refresh_from_db()
        assert entry.reward_distributed is True

    def test_distribute_rewards_skips_already_distributed(self):
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        user      = UserFactory(coin_balance=Decimal("0"))
        LeaderboardFactory(user=user, date=yesterday, rank=1, reward_distributed=True)
        LeaderboardRewardFactory(rank=1, season_type="daily", reward_coins=Decimal("100"))
        rewarded  = LeaderboardService.distribute_rewards(yesterday)
        assert rewarded == 0

    def test_leaderboard_limited_to_100(self):
        today = date.today()
        for i in range(120):
            u = UserFactory(coin_balance=Decimal("0"))
            LeaderboardFactory(user=u, date=today, rank=i + 1)
        entries = LeaderboardService.get_leaderboard(today, limit=50)
        assert len(entries) <= 50

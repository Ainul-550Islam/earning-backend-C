# engagement/tests/test_achievements.py
import pytest
from decimal import Decimal

from ..services.achievement_service import AchievementService
from ..models.achievement import Achievement, UserAchievement, AchievementProgress
from .factories import UserFactory, AchievementFactory, UserAchievementFactory


@pytest.mark.django_db
class TestAchievementService:

    def test_check_and_unlock_unlocks_matching(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="streak", threshold=7)
        unlocked = AchievementService.check_and_unlock(user, "streak", current_value=7)
        assert len(unlocked) == 1
        assert unlocked[0].pk == a.pk
        assert UserAchievement.objects.filter(user=user, achievement=a).exists()

    def test_check_and_unlock_skips_already_unlocked(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="streak", threshold=7)
        UserAchievementFactory(user=user, achievement=a)
        unlocked = AchievementService.check_and_unlock(user, "streak", current_value=10)
        assert len(unlocked) == 0

    def test_check_and_unlock_skips_above_threshold(self):
        user = UserFactory(coin_balance=Decimal("0"))
        AchievementFactory(type="streak", threshold=10)
        unlocked = AchievementService.check_and_unlock(user, "streak", current_value=5)
        assert len(unlocked) == 0

    def test_unlock_grants_coin_reward(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="streak", threshold=1, coin_reward=Decimal("50"))
        AchievementService.check_and_unlock(user, "streak", current_value=1)
        user.refresh_from_db()
        assert user.coin_balance == Decimal("50")

    def test_unlock_grants_xp_reward(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="streak", threshold=1, xp_reward=100, coin_reward=Decimal("0"))
        AchievementService.check_and_unlock(user, "streak", current_value=1)
        from ..models.xp import UserXP
        xp_obj = UserXP.objects.filter(user=user).first()
        assert xp_obj is not None
        assert xp_obj.total_xp == 100

    def test_update_progress_increments(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="spins", threshold=10)
        AchievementService.update_progress(user, "spins", increment=3)
        prog = AchievementProgress.objects.get(user=user, achievement=a)
        assert prog.current == 3

    def test_update_progress_auto_unlocks_on_threshold(self):
        user = UserFactory(coin_balance=Decimal("0"))
        a    = AchievementFactory(type="spins", threshold=5)
        AchievementService.update_progress(user, "spins", increment=5)
        assert UserAchievement.objects.filter(user=user, achievement=a).exists()

    def test_get_all_with_status_includes_locked(self):
        user = UserFactory(coin_balance=Decimal("0"))
        AchievementFactory(type="streak", threshold=7, is_secret=False)
        data = AchievementService.get_all_with_status(user)
        assert any(not item["is_unlocked"] for item in data)

    def test_get_all_with_status_hides_secret_locked(self):
        user = UserFactory(coin_balance=Decimal("0"))
        AchievementFactory(type="streak", threshold=100, is_secret=True)
        data = AchievementService.get_all_with_status(user)
        # Secret achievement should not appear if locked
        assert all(not item.get("is_secret", False) or item["is_unlocked"] for item in data)

    def test_multiple_achievements_same_type(self):
        user = UserFactory(coin_balance=Decimal("0"))
        AchievementFactory(type="streak", threshold=3)
        AchievementFactory(type="streak", threshold=7)
        AchievementFactory(type="streak", threshold=14)
        unlocked = AchievementService.check_and_unlock(user, "streak", current_value=7)
        assert len(unlocked) == 2  # threshold 3 and 7 both met

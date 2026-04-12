"""USER_MONETIZATION/achievement_rewards.py — Achievement reward management."""
from decimal import Decimal


class AchievementRewards:
    @classmethod
    def award(cls, user, achievement_key: str, title: str,
               category: str = "earning", xp: int = 0,
               coins: Decimal = Decimal("0"), tenant=None):
        from ..models import Achievement
        if Achievement.objects.filter(user=user, achievement_key=achievement_key).exists():
            return None, False
        ach = Achievement.objects.create(
            user=user, achievement_key=achievement_key, title=title,
            category=category, xp_reward=xp, coin_reward=coins, tenant=tenant,
        )
        if coins > 0:
            from ..services import RewardService
            RewardService.credit(user, coins, transaction_type="achievement",
                                 description=f"Achievement: {title}")
        return ach, True

    @classmethod
    def user_achievements(cls, user) -> list:
        from ..models import Achievement
        return list(Achievement.objects.filter(user=user).order_by("-earned_at").values(
            "achievement_key", "title", "category", "xp_reward", "coin_reward", "earned_at"
        ))

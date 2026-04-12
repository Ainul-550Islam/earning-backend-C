"""GAMIFICATION/achievement_system.py — Achievement management."""
from ..USER_MONETIZATION.achievement_rewards import AchievementRewards


class AchievementSystem:
    @classmethod
    def award(cls, user, key: str, title: str, category: str = "earning",
               xp: int = 0, coins=None, tenant=None):
        from decimal import Decimal
        return AchievementRewards.award(
            user, key, title, category, xp,
            Decimal(str(coins)) if coins else Decimal("0"), tenant
        )

    @classmethod
    def all_for_user(cls, user) -> list:
        return AchievementRewards.user_achievements(user)

    @classmethod
    def check_milestones(cls, user, total_earned, tenant=None):
        milestones = [
            (100,   "earned_100",    "First 100 Coins!",   10,  10),
            (1000,  "earned_1k",     "1K Coins Club",      50,  50),
            (10000, "earned_10k",    "10K Coins Legend",   200, 200),
            (100000,"earned_100k",   "100K Whale!",        1000,1000),
        ]
        from decimal import Decimal
        for threshold, key, title, xp, coins in milestones:
            if total_earned >= Decimal(str(threshold)):
                cls.award(user, key, title, "earning", xp, coins, tenant)

"""GAMIFICATION/quest_system.py — Daily/weekly quest system."""
from decimal import Decimal
from django.core.cache import cache

QUESTS = {
    "daily_complete_3_offers": {
        "title": "Complete 3 Offers Today", "type": "daily",
        "target": 3, "reward_coins": Decimal("30"), "reward_xp": 15,
    },
    "daily_spin_wheel": {
        "title": "Spin the Wheel", "type": "daily",
        "target": 1, "reward_coins": Decimal("10"), "reward_xp": 5,
    },
    "weekly_earn_1000": {
        "title": "Earn 1000 Coins This Week", "type": "weekly",
        "target": 1000, "reward_coins": Decimal("100"), "reward_xp": 50,
    },
    "weekly_referral": {
        "title": "Refer a Friend", "type": "weekly",
        "target": 1, "reward_coins": Decimal("200"), "reward_xp": 100,
    },
}


class QuestSystem:
    @classmethod
    def active_quests(cls) -> list:
        return [{"key": k, **v} for k, v in QUESTS.items()]

    @classmethod
    def progress(cls, user, quest_key: str) -> dict:
        key    = f"mt:quest:{user.id}:{quest_key}"
        prog   = int(cache.get(key, 0))
        quest  = QUESTS.get(quest_key, {})
        target = quest.get("target", 1)
        return {
            "quest_key": quest_key, "progress": prog, "target": target,
            "completed": prog >= target, "pct": min(100, prog / target * 100),
        }

    @classmethod
    def increment(cls, user, quest_key: str, amount: int = 1) -> dict:
        ttl  = 86400 if QUESTS.get(quest_key, {}).get("type") == "daily" else 604800
        key  = f"mt:quest:{user.id}:{quest_key}"
        prog = int(cache.get(key, 0)) + amount
        cache.set(key, prog, ttl)
        quest  = QUESTS.get(quest_key, {})
        target = quest.get("target", 1)
        if prog >= target:
            return {"completed": True, "coins": quest.get("reward_coins", Decimal("0"))}
        return {"completed": False, "progress": prog}

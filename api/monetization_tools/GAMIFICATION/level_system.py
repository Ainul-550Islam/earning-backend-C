"""GAMIFICATION/level_system.py — User level progression."""
from ..models import UserLevel


class LevelSystem:
    XP_TABLE = [0, 100, 250, 500, 1000, 2000, 4000, 8000, 15000, 30000]

    @classmethod
    def get_or_create(cls, user, tenant=None):
        obj, _ = UserLevel.objects.get_or_create(
            user=user, defaults={"tenant": tenant}
        )
        return obj

    @classmethod
    def add_xp(cls, user, xp: int) -> dict:
        lvl   = cls.get_or_create(user)
        levup = lvl.add_xp(xp)
        lvl.save(update_fields=["current_xp", "current_level", "xp_to_next_level", "level_title"])
        return {"level_up": levup, "current_level": lvl.current_level, "current_xp": lvl.current_xp}

    @classmethod
    def xp_for_level(cls, level: int) -> int:
        if level <= 0:
            return 0
        idx = min(level - 1, len(cls.XP_TABLE) - 1)
        base = cls.XP_TABLE[idx]
        extra = (level - len(cls.XP_TABLE)) * 50000 if level > len(cls.XP_TABLE) else 0
        return base + extra

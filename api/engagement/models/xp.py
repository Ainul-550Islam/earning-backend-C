# engagement/models/xp.py
import math
from django.db import models
from .base import UserEngagementModel
from ..constants import LEVEL_XP_BASE, LEVEL_XP_GROWTH


def xp_for_level(level: int) -> int:
    """Total XP needed to reach `level` from level 1."""
    return int(LEVEL_XP_BASE * (LEVEL_XP_GROWTH ** (level - 1)))


def level_from_total_xp(total_xp: int) -> int:
    """Given cumulative XP, what level is the user?"""
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


class UserXP(UserEngagementModel):
    """Single row per user – cumulative XP & derived level."""

    total_xp  = models.IntegerField(default=0)
    level     = models.IntegerField(default=1)
    level_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = []  # one row per user via get_or_create
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"{self.user} – Level {self.level} ({self.total_xp} XP)"

    # ── Computed helpers ─────────────────────────────────────────────────────

    @property
    def xp_for_current_level(self) -> int:
        return xp_for_level(self.level)

    @property
    def xp_for_next_level(self) -> int:
        return xp_for_level(self.level + 1)

    @property
    def xp_progress_in_level(self) -> int:
        return max(0, self.total_xp - self.xp_for_current_level)

    @property
    def xp_needed_for_next(self) -> int:
        return self.xp_for_next_level - self.xp_for_current_level

    @property
    def level_pct(self) -> int:
        needed = self.xp_needed_for_next
        if needed == 0:
            return 100
        return min(100, int(self.xp_progress_in_level / needed * 100))


class XPTransaction(UserEngagementModel):
    """Audit log of every XP change."""

    SOURCE_CHOICES = [
        ("checkin",     "Daily Check-in"),
        ("spin",        "Spin Wheel"),
        ("quest",       "Quest Completed"),
        ("achievement", "Achievement"),
        ("challenge",   "Challenge"),
        ("referral",    "Referral"),
        ("admin",       "Admin Grant"),
    ]
    source   = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    amount   = models.IntegerField()
    note     = models.CharField(max_length=200, blank=True)
    ref_id   = models.CharField(max_length=100, blank=True)  # FK id of source object

    class Meta:
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["user", "created_at"])]

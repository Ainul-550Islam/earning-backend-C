# engagement/models/achievement.py
from django.db import models
from .base import TenantModel, UserEngagementModel
from ..constants import ACHIEVEMENT_TYPES


class Achievement(TenantModel):
    """Definition of an achievement / badge."""

    slug        = models.SlugField(max_length=80, unique=True)
    name        = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=200, blank=True)   # emoji or URL
    badge_color = models.CharField(max_length=20, default="#FFD700")
    type        = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    threshold   = models.IntegerField(default=1)   # e.g. reach 7-day streak
    xp_reward   = models.IntegerField(default=50)
    coin_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_secret   = models.BooleanField(default=False)  # hidden until unlocked
    is_active   = models.BooleanField(default=True)
    order       = models.IntegerField(default=0)

    class Meta:
        ordering = ["type", "order", "threshold"]

    def __str__(self):
        return f"[{self.type}] {self.name} (×{self.threshold})"


class UserAchievement(UserEngagementModel):
    """When a user unlocks an achievement."""

    achievement   = models.ForeignKey(Achievement, on_delete=models.CASCADE,
                                      related_name="user_achievements")
    unlocked_at   = models.DateTimeField(auto_now_add=True)
    notified      = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "achievement"]
        ordering        = ["-unlocked_at"]

    def __str__(self):
        return f"{self.user} unlocked '{self.achievement.name}'"


class AchievementProgress(UserEngagementModel):
    """Track partial progress toward an achievement."""

    achievement  = models.ForeignKey(Achievement, on_delete=models.CASCADE,
                                     related_name="progress_records")
    current      = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "achievement"]

    @property
    def pct(self):
        if self.achievement.threshold == 0:
            return 100
        return min(100, int(self.current / self.achievement.threshold * 100))

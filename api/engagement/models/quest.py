# engagement/models/quest.py
from django.db import models
from django.utils import timezone
from .base import TenantModel, UserEngagementModel
from ..constants import QUEST_TYPES, QUEST_STATUSES


class Quest(TenantModel):
    """Blueprint for a daily / weekly / special quest."""

    slug        = models.SlugField(max_length=100, unique=True)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type        = models.CharField(max_length=10, choices=QUEST_TYPES)
    icon        = models.CharField(max_length=200, blank=True)
    target      = models.IntegerField(default=1)       # e.g. spin 3 times
    action      = models.CharField(max_length=50)      # "spin", "checkin", "buy_item"
    coin_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_reward   = models.IntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    order       = models.IntegerField(default=0)

    class Meta:
        ordering = ["type", "order"]

    def __str__(self):
        return f"[{self.type}] {self.title}"


class UserQuest(UserEngagementModel):
    """User's current progress on a quest for a given period."""

    quest       = models.ForeignKey(Quest, on_delete=models.CASCADE, related_name="user_quests")
    period_date = models.DateField(default=timezone.now)  # Mon for weekly, today for daily
    status      = models.CharField(max_length=12, choices=QUEST_STATUSES, default="active")
    progress    = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "quest", "period_date"]
        ordering        = ["-period_date"]
        indexes         = [models.Index(fields=["user", "status", "period_date"])]

    def __str__(self):
        return f"{self.user} – {self.quest.title} ({self.status})"

    @property
    def pct(self):
        if self.quest.target == 0:
            return 100
        return min(100, int(self.progress / self.quest.target * 100))

# engagement/models/challenge.py
from django.db import models
from django.utils import timezone
from .base import TenantModel, UserEngagementModel
from ..constants import CHALLENGE_STATUSES


class Challenge(TenantModel):
    """A PvP or solo timed challenge."""

    TYPE_CHOICES = [("pvp", "PvP"), ("solo", "Solo"), ("group", "Group")]

    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type        = models.CharField(max_length=10, choices=TYPE_CHOICES, default="solo")
    metric      = models.CharField(max_length=50)      # "total_coins", "spins", "streak"
    target      = models.IntegerField(default=100)
    starts_at   = models.DateTimeField()
    ends_at     = models.DateTimeField()
    coin_reward = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_reward   = models.IntegerField(default=0)
    max_participants = models.IntegerField(default=0)  # 0 = unlimited
    is_public   = models.BooleanField(default=True)

    class Meta:
        ordering = ["-starts_at"]

    @property
    def is_active(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    def __str__(self):
        return f"[{self.type}] {self.title}"


class ChallengeParticipant(UserEngagementModel):
    challenge   = models.ForeignKey(Challenge, on_delete=models.CASCADE,
                                    related_name="participants")
    status      = models.CharField(max_length=12, choices=CHALLENGE_STATUSES, default="active")
    score       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rank        = models.IntegerField(default=0)
    joined_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_distributed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "challenge"]
        ordering        = ["rank", "-score"]

    def __str__(self):
        return f"{self.user} in '{self.challenge.title}' – {self.score}"

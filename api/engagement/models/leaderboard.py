# engagement/models/leaderboard.py
from django.db import models
from datetime import date
from .base import TenantModel, UserEngagementModel


class LeaderboardSeason(TenantModel):
    """Weekly / Monthly leaderboard seasons."""

    PERIOD_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")]
    period     = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="daily")
    start_date = models.DateField()
    end_date   = models.DateField()
    is_active  = models.BooleanField(default=True)
    prize_pool = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.period} season {self.start_date} → {self.end_date}"


class Leaderboard(UserEngagementModel):
    """Cached rank snapshot — rebuilt by Celery task."""

    season             = models.ForeignKey(LeaderboardSeason, on_delete=models.CASCADE,
                                           null=True, blank=True, related_name="entries")
    date               = models.DateField(default=date.today, db_index=True)
    total_coins_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_xp_earned    = models.IntegerField(default=0)
    rank               = models.IntegerField(default=0, db_index=True)
    reward_distributed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "date", "season"]
        ordering        = ["rank"]
        indexes         = [
            models.Index(fields=["date", "rank"]),
            models.Index(fields=["tenant", "date"]),
        ]

    def __str__(self):
        return f"#{self.rank} {self.user} on {self.date}"


class LeaderboardReward(TenantModel):
    rank         = models.IntegerField()
    season_type  = models.CharField(max_length=10, default="daily")  # daily/weekly/monthly
    reward_coins = models.DecimalField(max_digits=10, decimal_places=2)
    reward_xp    = models.IntegerField(default=0)
    reward_badge = models.CharField(max_length=100, blank=True)  # achievement slug

    class Meta:
        unique_together = ["tenant", "rank", "season_type"]
        ordering        = ["season_type", "rank"]

    def __str__(self):
        return f"Rank {self.rank} ({self.season_type}): {self.reward_coins} coins"

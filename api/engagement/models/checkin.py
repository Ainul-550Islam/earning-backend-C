# engagement/models/checkin.py
from django.db import models
from django.utils import timezone
from datetime import date
from .base import UserEngagementModel
from ..constants import CHECKIN_BASE_COINS, CHECKIN_MAX_STREAK_BONUS


class DailyCheckIn(UserEngagementModel):
    date              = models.DateField(default=date.today, db_index=True)
    coins_earned      = models.DecimalField(max_digits=10, decimal_places=2, default=CHECKIN_BASE_COINS)
    xp_earned         = models.IntegerField(default=10)
    consecutive_days  = models.IntegerField(default=1)
    bonus_claimed     = models.BooleanField(default=False)
    reward_claimed    = models.BooleanField(default=False)
    streak_shield_used = models.BooleanField(default=False)  # broke chain but used shield
    note              = models.CharField(max_length=255, blank=True)  # e.g. "Day 7 Bonus!"

    class Meta:
        unique_together = ["user", "date"]
        ordering        = ["-date"]
        indexes         = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["tenant", "date"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.date} (streak: {self.consecutive_days})"

    @classmethod
    def today_for(cls, user):
        return cls.objects.filter(user=user, date=date.today()).first()

    @classmethod
    def streak_for(cls, user):
        record = cls.objects.filter(user=user).order_by("-date").first()
        return record.consecutive_days if record else 0

    @property
    def expected_coins(self):
        multiplier = min(self.consecutive_days, CHECKIN_MAX_STREAK_BONUS)
        return CHECKIN_BASE_COINS * multiplier

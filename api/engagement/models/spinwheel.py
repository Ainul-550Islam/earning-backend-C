# engagement/models/spinwheel.py
from django.db import models
from django.utils import timezone
from .base import UserEngagementModel
from ..constants import SPIN_MAX_PER_DAY


class SpinWheel(UserEngagementModel):
    coins_won   = models.DecimalField(max_digits=10, decimal_places=2)
    xp_earned   = models.IntegerField(default=5)
    spun_at     = models.DateTimeField(auto_now_add=True, db_index=True)
    outcome_idx = models.IntegerField(default=0)  # index in SPIN_OUTCOMES list
    is_boosted  = models.BooleanField(default=False)  # spin boost item active?

    class Meta:
        ordering = ["-spun_at"]
        indexes  = [
            models.Index(fields=["user", "spun_at"]),
            models.Index(fields=["tenant", "spun_at"]),
        ]

    def __str__(self):
        return f"{self.user} won {self.coins_won} @ {self.spun_at:%Y-%m-%d %H:%M}"

    @classmethod
    def spins_today(cls, user):
        return cls.objects.filter(user=user, spun_at__date=timezone.now().date()).count()

    @classmethod
    def can_spin(cls, user):
        return cls.spins_today(user) < SPIN_MAX_PER_DAY

    @classmethod
    def remaining_today(cls, user):
        return max(0, SPIN_MAX_PER_DAY - cls.spins_today(user))

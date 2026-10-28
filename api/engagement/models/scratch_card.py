# engagement/models/scratch_card.py
"""
Scratch Card System — Alternative randomised reward mechanic.
Daily Login Calendar — Visual calendar with reward milestones.
"""
from django.db import models
from datetime import date
from .base import TenantModel, UserEngagementModel


# ── Scratch Card ──────────────────────────────────────────────────────────────

class ScratchCardTemplate(TenantModel):
    """A scratch card design with its drop table."""
    slug         = models.SlugField(max_length=80, unique=True)
    name         = models.CharField(max_length=100)
    icon         = models.CharField(max_length=200, blank=True)
    max_per_day  = models.IntegerField(default=1)
    price_coins  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active    = models.BooleanField(default=True)


class ScratchCardPrize(TenantModel):
    """One possible prize on a scratch card template."""
    template    = models.ForeignKey(ScratchCardTemplate, on_delete=models.CASCADE, related_name="prizes")
    label       = models.CharField(max_length=50)    # shown to user e.g. "💰 50 Coins"
    coins       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp          = models.IntegerField(default=0)
    item_slug   = models.CharField(max_length=100, blank=True)
    weight      = models.IntegerField(default=10)    # relative probability

    class Meta:
        ordering = ["-weight"]


class ScratchCardResult(UserEngagementModel):
    """A user's scratch card play result."""
    template    = models.ForeignKey(ScratchCardTemplate, on_delete=models.PROTECT)
    prize       = models.ForeignKey(ScratchCardPrize, on_delete=models.PROTECT)
    coins_won   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_won      = models.IntegerField(default=0)
    scratched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scratched_at"]

    def __str__(self):
        return f"{self.user} scratched {self.template.name} → {self.prize.label}"


# ── Daily Login Calendar ──────────────────────────────────────────────────────

class LoginCalendar(TenantModel):
    """A monthly login reward calendar configuration."""
    month       = models.IntegerField()    # 1–12
    year        = models.IntegerField()
    is_active   = models.BooleanField(default=True)

    class Meta:
        unique_together = ["tenant", "month", "year"]

    def __str__(self):
        return f"Calendar {self.year}-{self.month:02d}"


class LoginCalendarDay(TenantModel):
    """Reward for checking in on a specific day of the month."""
    calendar      = models.ForeignKey(LoginCalendar, on_delete=models.CASCADE, related_name="days")
    day_number    = models.IntegerField()    # 1–31
    coins         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp            = models.IntegerField(default=0)
    item_slug     = models.CharField(max_length=100, blank=True)
    chest_slug    = models.CharField(max_length=100, blank=True)
    is_milestone  = models.BooleanField(default=False)   # day 7, 14, 21, 28 highlight
    icon          = models.CharField(max_length=10, blank=True)

    class Meta:
        unique_together = ["calendar", "day_number"]
        ordering        = ["day_number"]


class UserLoginCalendarProgress(UserEngagementModel):
    """Tracks which calendar days a user has claimed."""
    calendar      = models.ForeignKey(LoginCalendar, on_delete=models.CASCADE)
    claimed_days  = models.JSONField(default=list)    # list of day_numbers claimed
    last_claimed_day = models.IntegerField(default=0)
    last_claimed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "calendar"]

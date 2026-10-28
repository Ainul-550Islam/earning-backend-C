# engagement/models/seasonal_event.py
"""
Seasonal & Limited-Time Event System
Holiday events, special campaigns, time-limited missions
with event-specific currency and exclusive rewards.
"""
from django.db import models
from django.utils import timezone
from .base import TenantModel, UserEngagementModel


class SeasonalEvent(TenantModel):
    """A limited-time event (e.g. Eid Special, Black Friday, New Year)."""
    slug         = models.SlugField(max_length=100, unique=True)
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    theme_color  = models.CharField(max_length=20, default="#FF6B35")
    banner_image = models.CharField(max_length=500, blank=True)
    icon         = models.CharField(max_length=200, blank=True)
    starts_at    = models.DateTimeField()
    ends_at      = models.DateTimeField()
    is_active    = models.BooleanField(default=True)
    event_currency_name  = models.CharField(max_length=50, default="Event Token")
    event_currency_icon  = models.CharField(max_length=10, default="🎟️")
    coin_multiplier      = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    xp_multiplier        = models.DecimalField(max_digits=4, decimal_places=2, default=1)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"[Event] {self.name}"

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    @property
    def time_remaining_seconds(self):
        if not self.is_live:
            return 0
        return int((self.ends_at - timezone.now()).total_seconds())


class EventMission(TenantModel):
    """A mission available only during a seasonal event."""
    event       = models.ForeignKey(SeasonalEvent, on_delete=models.CASCADE, related_name="missions")
    slug        = models.SlugField(max_length=100)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=200, blank=True)
    target      = models.IntegerField(default=1)
    action      = models.CharField(max_length=50)
    coin_reward         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_reward           = models.IntegerField(default=0)
    event_currency_reward = models.IntegerField(default=0)
    chest_reward_slug   = models.CharField(max_length=100, blank=True)
    order       = models.IntegerField(default=0)
    repeatable  = models.BooleanField(default=False)    # can complete multiple times

    class Meta:
        unique_together = ["event", "slug"]
        ordering        = ["order"]


class UserEventProgress(UserEngagementModel):
    """A user's progress on event missions."""
    event            = models.ForeignKey(SeasonalEvent, on_delete=models.CASCADE)
    mission          = models.ForeignKey(EventMission, on_delete=models.CASCADE)
    progress         = models.IntegerField(default=0)
    times_completed  = models.IntegerField(default=0)
    reward_claimed   = models.BooleanField(default=False)
    last_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "event", "mission"]

    @property
    def pct(self):
        if self.mission.target == 0:
            return 100
        return min(100, int(self.progress / self.mission.target * 100))


class UserEventCurrency(UserEngagementModel):
    """Per-event special currency balance for a user."""
    event   = models.ForeignKey(SeasonalEvent, on_delete=models.CASCADE)
    balance = models.IntegerField(default=0)

    class Meta:
        unique_together = ["user", "event"]

    def __str__(self):
        return f"{self.user} – {self.event.event_currency_name}: {self.balance}"


class EventShopItem(TenantModel):
    """Items purchasable with event currency during an event."""
    event        = models.ForeignKey(SeasonalEvent, on_delete=models.CASCADE, related_name="shop_items")
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    icon         = models.CharField(max_length=200, blank=True)
    price_event_currency = models.IntegerField(default=10)
    stock        = models.IntegerField(default=-1)
    reward_coins = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reward_xp    = models.IntegerField(default=0)
    reward_item_slug = models.CharField(max_length=100, blank=True)
    reward_chest_slug = models.CharField(max_length=100, blank=True)
    order        = models.IntegerField(default=0)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]

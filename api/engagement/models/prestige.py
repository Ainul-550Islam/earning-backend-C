# engagement/models/prestige.py
"""
Prestige / Rebirth System
When a user reaches max level, they can "prestige" — resetting XP/level
but gaining permanent prestige bonuses (coin multiplier, special badge, etc.)

Milestone System
Long-term platform milestones that go beyond regular achievements
(e.g., "100,000 total coins earned", "365-day check-in streak").
"""
from django.db import models
from .base import TenantModel, UserEngagementModel


# ── Prestige System ────────────────────────────────────────────────────────────

class PrestigeLevel(TenantModel):
    """Definition of each prestige level and its permanent perks."""
    level             = models.IntegerField(unique=True)
    name              = models.CharField(max_length=100)
    icon              = models.CharField(max_length=200, blank=True)
    badge_color       = models.CharField(max_length=20, default="#FFD700")
    required_level    = models.IntegerField(default=50)     # XP level needed to prestige
    coin_multiplier   = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    xp_multiplier     = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    spin_bonus        = models.IntegerField(default=0)      # extra spins per day
    exclusive_item_slug = models.CharField(max_length=100, blank=True)
    description       = models.TextField(blank=True)

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return f"Prestige {self.level}: {self.name}"


class UserPrestige(UserEngagementModel):
    """A user's prestige history."""
    prestige_level  = models.IntegerField(default=0)
    level_at_prestige = models.IntegerField(default=0)    # XP level when they prestiged
    xp_at_prestige  = models.IntegerField(default=0)
    prestiged_at    = models.DateTimeField(auto_now_add=True)
    coin_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    xp_multiplier   = models.DecimalField(max_digits=4, decimal_places=2, default=1)

    class Meta:
        ordering = ["-prestiged_at"]

    def __str__(self):
        return f"{self.user} Prestige {self.prestige_level}"


# ── Milestone System ───────────────────────────────────────────────────────────

class Milestone(TenantModel):
    """A long-term milestone definition."""
    METRIC_CHOICES = [
        ("total_coins_earned",   "Total Coins Earned"),
        ("total_xp",             "Total XP"),
        ("checkin_streak",       "Check-in Streak"),
        ("total_checkins",       "Total Check-ins"),
        ("total_spins",          "Total Spins"),
        ("total_purchases",      "Total Purchases"),
        ("total_referrals",      "Total Referrals"),
        ("guild_contribution",   "Guild XP Contributed"),
        ("battle_pass_tiers",    "Battle Pass Tiers Reached"),
        ("prestige_level",       "Prestige Level"),
        ("friends_count",        "Friends Count"),
    ]
    slug         = models.SlugField(max_length=100, unique=True)
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    icon         = models.CharField(max_length=200, blank=True)
    metric       = models.CharField(max_length=30, choices=METRIC_CHOICES)
    threshold    = models.BigIntegerField()
    coin_reward  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    xp_reward    = models.IntegerField(default=0)
    title_reward = models.CharField(max_length=100, blank=True)    # unlocks a user title
    is_active    = models.BooleanField(default=True)
    order        = models.IntegerField(default=0)

    class Meta:
        ordering = ["metric", "order", "threshold"]

    def __str__(self):
        return f"[Milestone] {self.name} ({self.metric} ≥ {self.threshold})"


class UserMilestone(UserEngagementModel):
    """A user's unlocked milestone."""
    milestone     = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="user_milestones")
    unlocked_at   = models.DateTimeField(auto_now_add=True)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "milestone"]
        ordering        = ["-unlocked_at"]


class UserTitle(TenantModel):
    """Unlockable display titles for users."""
    slug        = models.SlugField(max_length=100, unique=True)
    name        = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    rarity      = models.CharField(max_length=12, default="common",
                                   choices=[("common","Common"),("rare","Rare"),("epic","Epic"),("legendary","Legendary")])
    color       = models.CharField(max_length=20, default="#888888")
    source      = models.CharField(max_length=50, blank=True)   # "milestone", "prestige", "event"

    class Meta:
        ordering = ["rarity", "name"]


class UserEquippedTitle(UserEngagementModel):
    """Which title a user currently has equipped."""
    title       = models.ForeignKey(UserTitle, on_delete=models.SET_NULL, null=True, blank=True)
    unlocked_titles = models.ManyToManyField(UserTitle, related_name="owners", blank=True)

    class Meta:
        unique_together = []   # one row per user

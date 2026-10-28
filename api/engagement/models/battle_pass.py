# engagement/models/battle_pass.py
"""
Battle Pass (Season Pass) System
Users earn BP XP through actions and unlock tiered rewards.
Free track (all users) + Premium track (paid/coin-unlocked).
"""
from django.db import models
from django.utils import timezone
from .base import TenantModel, UserEngagementModel


class BattlePass(TenantModel):
    """A season's Battle Pass definition."""
    name        = models.CharField(max_length=200)
    season_num  = models.IntegerField(default=1)
    starts_at   = models.DateTimeField()
    ends_at     = models.DateTimeField()
    is_active   = models.BooleanField(default=True)
    premium_price_coins = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    total_tiers = models.IntegerField(default=50)
    cover_image = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-season_num"]

    def __str__(self):
        return f"Season {self.season_num}: {self.name}"

    @property
    def is_live(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at


class BattlePassTier(TenantModel):
    """One tier (level) inside a battle pass."""
    battle_pass = models.ForeignKey(BattlePass, on_delete=models.CASCADE, related_name="tiers")
    tier_number = models.IntegerField()
    xp_required = models.IntegerField(default=100)   # XP needed to reach this tier

    # Free rewards (all users)
    free_coins      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_xp         = models.IntegerField(default=0)
    free_item_slug  = models.CharField(max_length=100, blank=True)  # ShopItem slug
    free_badge_slug = models.CharField(max_length=100, blank=True)

    # Premium rewards (premium holders only)
    premium_coins      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    premium_xp         = models.IntegerField(default=0)
    premium_item_slug  = models.CharField(max_length=100, blank=True)
    premium_badge_slug = models.CharField(max_length=100, blank=True)
    is_milestone       = models.BooleanField(default=False)   # special highlight tier

    class Meta:
        unique_together = ["battle_pass", "tier_number"]
        ordering        = ["tier_number"]

    def __str__(self):
        return f"Season {self.battle_pass.season_num} Tier {self.tier_number}"


class UserBattlePass(UserEngagementModel):
    """A user's progress inside a battle pass."""
    battle_pass   = models.ForeignKey(BattlePass, on_delete=models.CASCADE, related_name="user_passes")
    is_premium    = models.BooleanField(default=False)
    current_xp    = models.IntegerField(default=0)
    current_tier  = models.IntegerField(default=0)
    last_claimed_tier = models.IntegerField(default=0)
    premium_unlocked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "battle_pass"]

    def __str__(self):
        return f"{self.user} – S{self.battle_pass.season_num} T{self.current_tier} {'PRO' if self.is_premium else 'FREE'}"

    @property
    def unclaimed_tiers(self):
        return list(range(self.last_claimed_tier + 1, self.current_tier + 1))


class BattlePassXPSource(TenantModel):
    """How much BP XP each action gives."""
    battle_pass = models.ForeignKey(BattlePass, on_delete=models.CASCADE, related_name="xp_sources")
    action      = models.CharField(max_length=50)      # "checkin", "spin", "quest_complete"
    xp_amount   = models.IntegerField(default=10)
    daily_cap   = models.IntegerField(default=0)        # 0 = no cap

    class Meta:
        unique_together = ["battle_pass", "action"]

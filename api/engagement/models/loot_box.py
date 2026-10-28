# engagement/models/loot_box.py
"""
Reward Chest / Loot Box System
Users earn, buy, or win chests. Opening gives randomised rewards.
Drop tables are configurable per chest type.
"""
from django.db import models
from .base import TenantModel, UserEngagementModel


class ChestType(TenantModel):
    """Definition of a chest type (e.g. Bronze, Silver, Gold, Legendary)."""
    RARITY_CHOICES = [
        ("common",    "Common"),
        ("rare",      "Rare"),
        ("epic",      "Epic"),
        ("legendary", "Legendary"),
    ]
    slug         = models.SlugField(max_length=80, unique=True)
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    icon         = models.CharField(max_length=200, blank=True)
    rarity       = models.CharField(max_length=12, choices=RARITY_CHOICES, default="common")
    price_coins  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active    = models.BooleanField(default=True)
    open_animation = models.CharField(max_length=100, blank=True)   # frontend animation key
    order        = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "price_coins"]

    def __str__(self):
        return f"[{self.rarity}] {self.name}"


class ChestDropTable(TenantModel):
    """
    One row = one possible reward from a chest.
    Weight determines probability (higher = more likely).
    """
    REWARD_TYPE_CHOICES = [
        ("coins",       "Coins"),
        ("xp",          "XP"),
        ("shop_item",   "Shop Item"),
        ("achievement", "Achievement Badge"),
        ("spin",        "Extra Spin"),
        ("chest",       "Another Chest"),
    ]
    chest_type  = models.ForeignKey(ChestType, on_delete=models.CASCADE, related_name="drop_table")
    reward_type = models.CharField(max_length=15, choices=REWARD_TYPE_CHOICES)
    reward_slug = models.CharField(max_length=100, blank=True)   # e.g. ShopItem slug, achievement slug
    coins_min   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coins_max   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_min      = models.IntegerField(default=0)
    xp_max      = models.IntegerField(default=0)
    quantity    = models.IntegerField(default=1)
    weight      = models.IntegerField(default=10)   # relative probability weight
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ["-weight"]


class UserChest(UserEngagementModel):
    """A chest in a user's possession (not yet opened)."""
    chest_type    = models.ForeignKey(ChestType, on_delete=models.PROTECT, related_name="user_chests")
    quantity      = models.IntegerField(default=1)
    source        = models.CharField(max_length=50, blank=True)    # "quest", "login", "purchase"
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "chest_type"]


class ChestOpening(UserEngagementModel):
    """Record of each chest opening event and what was received."""
    chest_type      = models.ForeignKey(ChestType, on_delete=models.PROTECT)
    drop_table_entry = models.ForeignKey(ChestDropTable, on_delete=models.SET_NULL,
                                         null=True, related_name="openings")
    reward_type     = models.CharField(max_length=15)
    reward_slug     = models.CharField(max_length=100, blank=True)
    coins_won       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    xp_won          = models.IntegerField(default=0)
    quantity        = models.IntegerField(default=1)
    opened_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"{self.user} opened {self.chest_type.name} → {self.reward_type}"

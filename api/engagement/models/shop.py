# engagement/models/shop.py
from django.db import models
from .base import TenantModel, UserEngagementModel
from ..constants import SHOP_ITEM_TYPES


class ShopItem(TenantModel):
    """An item available for purchase in the coin shop."""

    slug         = models.SlugField(max_length=100, unique=True)
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    type         = models.CharField(max_length=30, choices=SHOP_ITEM_TYPES)
    icon         = models.CharField(max_length=200, blank=True)
    price_coins  = models.DecimalField(max_digits=10, decimal_places=2)
    stock        = models.IntegerField(default=-1)    # -1 = unlimited
    max_per_user = models.IntegerField(default=-1)    # -1 = unlimited
    effect_days  = models.IntegerField(default=1)     # how long item lasts
    is_active    = models.BooleanField(default=True)
    order        = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "price_coins"]

    def __str__(self):
        return f"{self.name} ({self.price_coins} coins)"


class ShopPurchase(UserEngagementModel):
    """A completed purchase record."""

    item         = models.ForeignKey(ShopItem, on_delete=models.PROTECT,
                                     related_name="purchases")
    quantity     = models.IntegerField(default=1)
    coins_spent  = models.DecimalField(max_digits=10, decimal_places=2)
    expires_at   = models.DateTimeField(null=True, blank=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bought {self.item.name} × {self.quantity}"


class UserInventory(UserEngagementModel):
    """Active items in a user's inventory (derived from purchases)."""

    item        = models.ForeignKey(ShopItem, on_delete=models.CASCADE,
                                    related_name="inventory_entries")
    quantity    = models.IntegerField(default=0)
    expires_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "item"]

    def __str__(self):
        return f"{self.user}: {self.item.name} ×{self.quantity}"

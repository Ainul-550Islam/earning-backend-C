# engagement/serializers/shop_serializer.py
from rest_framework import serializers
from ..models.shop import ShopItem, ShopPurchase, UserInventory


class ShopItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShopItem
        fields = [
            "id", "slug", "name", "description", "type", "icon",
            "price_coins", "stock", "max_per_user", "effect_days", "order",
        ]


class ShopPurchaseSerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)

    class Meta:
        model  = ShopPurchase
        fields = [
            "id", "item", "quantity", "coins_spent",
            "expires_at", "is_active", "created_at",
        ]
        read_only_fields = fields


class UserInventorySerializer(serializers.ModelSerializer):
    item = ShopItemSerializer(read_only=True)

    class Meta:
        model  = UserInventory
        fields = ["id", "item", "quantity", "expires_at"]

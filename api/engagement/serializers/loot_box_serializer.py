# engagement/serializers/loot_box_serializer.py
from rest_framework import serializers
from ..models.loot_box import ChestType, ChestDropTable, UserChest, ChestOpening


class ChestDropTableSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChestDropTable
        fields = [
            "id", "reward_type", "reward_slug",
            "coins_min", "coins_max", "xp_min", "xp_max",
            "quantity", "weight",
        ]


class ChestTypeSerializer(serializers.ModelSerializer):
    drop_table = ChestDropTableSerializer(many=True, read_only=True)

    class Meta:
        model  = ChestType
        fields = [
            "id", "slug", "name", "description", "icon", "rarity",
            "price_coins", "is_active", "order", "drop_table",
        ]


class UserChestSerializer(serializers.ModelSerializer):
    chest_name   = serializers.CharField(source="chest_type.name",   read_only=True)
    chest_icon   = serializers.CharField(source="chest_type.icon",   read_only=True)
    chest_rarity = serializers.CharField(source="chest_type.rarity", read_only=True)
    chest_slug   = serializers.CharField(source="chest_type.slug",   read_only=True)

    class Meta:
        model  = UserChest
        fields = [
            "id", "chest_slug", "chest_name", "chest_icon", "chest_rarity",
            "quantity", "source", "expires_at",
        ]
        read_only_fields = fields


class ChestOpeningSerializer(serializers.ModelSerializer):
    chest_name = serializers.CharField(source="chest_type.name", read_only=True)
    username   = serializers.CharField(source="user.username",   read_only=True)

    class Meta:
        model  = ChestOpening
        fields = [
            "id", "username", "chest_name", "reward_type", "reward_slug",
            "coins_won", "xp_won", "quantity", "opened_at",
        ]
        read_only_fields = fields

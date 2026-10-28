# engagement/serializers/battle_pass_serializer.py
from rest_framework import serializers
from ..models.battle_pass import BattlePass, BattlePassTier, UserBattlePass, BattlePassXPSource


class BattlePassTierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BattlePassTier
        fields = [
            "tier_number", "xp_required",
            "free_coins", "free_xp", "free_item_slug", "free_badge_slug",
            "premium_coins", "premium_xp", "premium_item_slug", "premium_badge_slug",
            "is_milestone",
        ]


class BattlePassSerializer(serializers.ModelSerializer):
    is_live      = serializers.BooleanField(read_only=True)
    tiers        = BattlePassTierSerializer(many=True, read_only=True)

    class Meta:
        model  = BattlePass
        fields = [
            "id", "name", "season_num", "starts_at", "ends_at",
            "is_active", "is_live", "premium_price_coins", "total_tiers",
            "cover_image", "description", "tiers",
        ]


class UserBattlePassSerializer(serializers.ModelSerializer):
    season_num      = serializers.IntegerField(source="battle_pass.season_num", read_only=True)
    season_name     = serializers.CharField(source="battle_pass.name",         read_only=True)
    total_tiers     = serializers.IntegerField(source="battle_pass.total_tiers", read_only=True)
    premium_price   = serializers.DecimalField(
        source="battle_pass.premium_price_coins", max_digits=10, decimal_places=2, read_only=True
    )
    unclaimed_tiers = serializers.ListField(read_only=True)

    class Meta:
        model  = UserBattlePass
        fields = [
            "id", "season_num", "season_name", "total_tiers", "premium_price",
            "is_premium", "current_xp", "current_tier", "last_claimed_tier",
            "unclaimed_tiers", "premium_unlocked_at",
        ]
        read_only_fields = fields


class BattlePassXPSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BattlePassXPSource
        fields = ["action", "xp_amount", "daily_cap"]

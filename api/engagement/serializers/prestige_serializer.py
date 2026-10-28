# engagement/serializers/prestige_serializer.py
from rest_framework import serializers
from ..models.prestige import PrestigeLevel, UserPrestige, Milestone, UserMilestone, UserTitle, UserEquippedTitle


class PrestigeLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PrestigeLevel
        fields = [
            "level", "name", "icon", "badge_color", "required_level",
            "coin_multiplier", "xp_multiplier", "spin_bonus",
            "exclusive_item_slug", "description",
        ]


class UserPrestigeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserPrestige
        fields = [
            "id", "prestige_level", "level_at_prestige", "xp_at_prestige",
            "coin_multiplier", "xp_multiplier", "prestiged_at",
        ]
        read_only_fields = fields


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Milestone
        fields = [
            "id", "slug", "name", "description", "icon",
            "metric", "threshold", "coin_reward", "xp_reward", "title_reward",
            "is_active", "order",
        ]


class UserMilestoneSerializer(serializers.ModelSerializer):
    milestone = MilestoneSerializer(read_only=True)

    class Meta:
        model  = UserMilestone
        fields = ["id", "milestone", "unlocked_at", "reward_claimed"]
        read_only_fields = ["id", "unlocked_at"]


class UserTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserTitle
        fields = ["id", "slug", "name", "description", "rarity", "color", "source"]

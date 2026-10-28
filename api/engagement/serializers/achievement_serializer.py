# engagement/serializers/achievement_serializer.py
from rest_framework import serializers
from ..models.achievement import Achievement, UserAchievement, AchievementProgress


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Achievement
        fields = [
            "id", "slug", "name", "description", "icon", "badge_color",
            "type", "threshold", "xp_reward", "coin_reward", "is_secret", "order",
        ]


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)

    class Meta:
        model  = UserAchievement
        fields = ["id", "achievement", "unlocked_at", "notified", "reward_claimed"]
        read_only_fields = ["id", "unlocked_at"]


class AchievementProgressSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)
    pct         = serializers.IntegerField(read_only=True)

    class Meta:
        model  = AchievementProgress
        fields = ["id", "achievement", "current", "pct", "last_updated"]


class AchievementStatusSerializer(serializers.Serializer):
    """Flat representation used in get_all_with_status()."""
    id          = serializers.IntegerField()
    slug        = serializers.CharField()
    name        = serializers.CharField()
    description = serializers.CharField()
    icon        = serializers.CharField()
    badge_color = serializers.CharField()
    type        = serializers.CharField()
    threshold   = serializers.IntegerField()
    is_unlocked = serializers.BooleanField()
    progress    = serializers.IntegerField()
    pct         = serializers.IntegerField()

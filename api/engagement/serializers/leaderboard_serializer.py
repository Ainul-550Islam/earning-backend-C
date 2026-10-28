# engagement/serializers/leaderboard_serializer.py
from rest_framework import serializers
from ..models.leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason


class LeaderboardSerializer(serializers.ModelSerializer):
    username       = serializers.CharField(source="user.username", read_only=True)
    avatar         = serializers.SerializerMethodField()
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model  = Leaderboard
        fields = [
            "id", "username", "avatar", "date",
            "total_coins_earned", "total_xp_earned",
            "rank", "is_current_user", "reward_distributed",
        ]
        read_only_fields = ["id", "date", "rank"]

    def get_avatar(self, obj):
        try:
            return obj.user.avatar_url
        except AttributeError:
            return None

    def get_is_current_user(self, obj):
        req = self.context.get("request")
        return bool(req and req.user.is_authenticated and obj.user == req.user)


class LeaderboardRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaderboardReward
        fields = ["rank", "season_type", "reward_coins", "reward_xp", "reward_badge"]


class LeaderboardSeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaderboardSeason
        fields = ["id", "period", "start_date", "end_date", "is_active", "prize_pool"]

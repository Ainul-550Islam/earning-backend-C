# api/engagement/serializers.py
from rest_framework import serializers
from .models import DailyCheckIn, SpinWheel, Leaderboard, LeaderboardReward


# ✅ try/except ছাড়া — সরাসরি import
class DailyCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCheckIn
        fields = [
            'id', 'user', 'date', 'coins_earned',
            'consecutive_days', 'bonus_claimed', 'reward_claimed'
        ]
        read_only_fields = ['id', 'date']


class SpinWheelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpinWheel
        fields = [
            'id', 'user', 'coins_won', 'spun_at',
            'total_spins', 'total_won', 'last_spin'
        ]
        read_only_fields = ['id', 'spun_at', 'last_spin']


class LeaderboardSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = Leaderboard
        fields = ['id', 'username', 'date', 'total_coins_earned', 'rank', 'is_current_user']
        read_only_fields = ['id', 'date', 'rank']

    def get_is_current_user(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False


class LeaderboardRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardReward
        fields = ['rank', 'reward_coins']
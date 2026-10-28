# engagement/serializers/checkin_serializer.py
from rest_framework import serializers
from ..models.checkin import DailyCheckIn


class DailyCheckInSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model  = DailyCheckIn
        fields = [
            "id", "user", "username", "date", "coins_earned", "xp_earned",
            "consecutive_days", "bonus_claimed", "reward_claimed",
            "streak_shield_used", "note", "created_at",
        ]
        read_only_fields = ["id", "date", "created_at"]


class CheckInStatsSerializer(serializers.Serializer):
    total_checkins    = serializers.IntegerField()
    current_streak    = serializers.IntegerField()
    last_checkin      = serializers.DateField(allow_null=True)
    checked_in_today  = serializers.BooleanField()

# api/djoyalty/serializers/StreakSerializer.py
from rest_framework import serializers
from ..models.engagement import DailyStreak, StreakReward


class StreakRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreakReward
        fields = ['id', 'milestone_days', 'points_awarded', 'multiplier_hours', 'awarded_at', 'created_at']
        read_only_fields = ['id', 'created_at']


class DailyStreakSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    rewards = StreakRewardSerializer(many=True, read_only=True)
    next_milestone = serializers.SerializerMethodField()

    class Meta:
        model = DailyStreak
        fields = [
            'id', 'customer', 'customer_code',
            'current_streak', 'longest_streak',
            'last_activity_date', 'freeze_count',
            'is_active', 'started_at',
            'next_milestone', 'rewards',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_code', 'next_milestone', 'created_at', 'updated_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_next_milestone(self, obj) -> dict | None:
        from ..constants import STREAK_MILESTONES
        current = obj.current_streak
        for days in sorted(STREAK_MILESTONES.keys()):
            if days > current:
                return {
                    'days': days,
                    'bonus_points': str(STREAK_MILESTONES[days]),
                    'days_remaining': days - current,
                }
        return None

    def validate_current_streak(self, value):
        if value < 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Streak cannot be negative.')
        return value

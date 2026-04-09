# api/djoyalty/serializers/StreakSerializer.py
"""Daily streak and streak reward serializers।"""
from rest_framework import serializers
from ..models.engagement import DailyStreak, StreakReward


class DailyStreakSerializer(serializers.ModelSerializer):
    """Daily streak serializer with full streak info।"""
    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()
    streak_status = serializers.SerializerMethodField()
    next_milestone = serializers.SerializerMethodField()

    class Meta:
        model = DailyStreak
        fields = [
            'id', 'customer', 'customer_code', 'customer_name',
            'current_streak', 'longest_streak', 'last_activity_date',
            'is_active', 'started_at', 'streak_status', 'next_milestone',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else ''

    def get_customer_code(self, obj):
        return obj.customer.code if obj.customer else ''

    def get_streak_status(self, obj):
        """Streak এর current status।"""
        if not obj.is_active:
            return 'broken'
        if obj.current_streak >= 30:
            return 'legendary'
        if obj.current_streak >= 7:
            return 'on_fire'
        if obj.current_streak >= 3:
            return 'building'
        return 'starting'

    def get_next_milestone(self, obj):
        """Next streak milestone কতটা দূরে।"""
        from ..constants import STREAK_MILESTONES
        for milestone_days in sorted(STREAK_MILESTONES.keys()):
            if obj.current_streak < milestone_days:
                return {
                    'days': milestone_days,
                    'days_remaining': milestone_days - obj.current_streak,
                    'bonus_points': str(STREAK_MILESTONES[milestone_days]),
                }
        return None


class StreakRewardSerializer(serializers.ModelSerializer):
    """Streak reward log serializer।"""
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = StreakReward
        fields = [
            'id', 'customer', 'customer_code', 'streak',
            'milestone_days', 'points_awarded', 'awarded_at',
        ]
        read_only_fields = ['awarded_at']

    def get_customer_code(self, obj):
        return obj.customer.code if obj.customer else ''

# api/cms/serializers_new/LeaderboardSerializer.py
"""
Serializers for Leaderboard, EarningStreak, and StreakMilestone Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry, EarningStreak, StreakMilestone

User = get_user_model()


class LeaderboardPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardPeriod
        fields = ['id', 'period_type', 'start_date', 'end_date', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] >= data['end_date']:
                raise serializers.ValidationError("end_date must be after start_date.")
        return data


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = LeaderboardEntry
        fields = [
            'uuid', 'period', 'user', 'user_display', 'category',
            'rank', 'score', 'score_usd', 'score_coins',
        ]
        read_only_fields = ['uuid', 'rank']


class EarningStreakSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = EarningStreak
        fields = [
            'id', 'user', 'user_display', 'current_streak', 'longest_streak',
            'last_earn_date', 'streak_bonus_multiplier', 'total_streak_days', 'updated_at',
        ]
        read_only_fields = ['id', 'longest_streak', 'total_streak_days', 'updated_at']


class StreakMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreakMilestone
        fields = [
            'id', 'streak_days', 'bonus_coins', 'bonus_usd',
            'title', 'description', 'is_active',
        ]
        read_only_fields = ['id']

    def validate_streak_days(self, value):
        if value <= 0:
            raise serializers.ValidationError("streak_days must be a positive integer.")
        return value

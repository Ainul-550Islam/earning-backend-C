# engagement/serializers/stats_serializer.py
from rest_framework import serializers


class DailyStatsSerializer(serializers.Serializer):
    check_in = serializers.DictField()
    spin_wheel = serializers.DictField()
    todays_earnings = serializers.FloatField()
    coin_balance = serializers.FloatField()
    xp = serializers.DictField()
    active_quests = serializers.DictField()


class EngagementScoreSerializer(serializers.Serializer):
    engagement_score  = serializers.FloatField()
    streak            = serializers.IntegerField()
    has_checked_in    = serializers.BooleanField()
    spins_today       = serializers.IntegerField()
    spins_remaining   = serializers.IntegerField()
    total_checkins    = serializers.IntegerField()
    total_spins       = serializers.IntegerField()
    coin_balance      = serializers.FloatField()
    level             = serializers.IntegerField()
    total_xp          = serializers.IntegerField()
    level_pct         = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    rank_today        = serializers.IntegerField(allow_null=True)

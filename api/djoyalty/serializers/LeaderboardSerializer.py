# api/djoyalty/serializers/LeaderboardSerializer.py
from rest_framework import serializers


class LeaderboardEntrySerializer(serializers.Serializer):
    """Leaderboard entry -- read-only aggregated data।"""
    rank = serializers.IntegerField(read_only=True)
    customer__id = serializers.IntegerField(read_only=True)
    customer__code = serializers.CharField(read_only=True)
    customer__firstname = serializers.CharField(read_only=True, allow_null=True)
    customer__lastname = serializers.CharField(read_only=True, allow_null=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    lifetime_earned = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

# api/djoyalty/serializers/LeaderboardSerializer.py
from rest_framework import serializers

class LeaderboardSerializer(serializers.Serializer):
    rank = serializers.IntegerField(read_only=True)
    customer__id = serializers.IntegerField(read_only=True)
    customer__code = serializers.CharField(read_only=True)
    customer__firstname = serializers.CharField(read_only=True)
    customer__lastname = serializers.CharField(read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    lifetime_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

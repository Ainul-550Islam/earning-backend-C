# api/djoyalty/serializers/BadgeSerializer.py
from rest_framework import serializers
from ..models.engagement import Badge, UserBadge

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'name', 'description', 'icon', 'trigger', 'threshold', 'points_reward', 'is_active', 'is_unique', 'created_at']

class UserBadgeSerializer(serializers.ModelSerializer):
    badge_name = serializers.SerializerMethodField()
    badge_icon = serializers.SerializerMethodField()
    class Meta:
        model = UserBadge
        fields = ['id', 'customer', 'badge', 'badge_name', 'badge_icon', 'points_awarded', 'awarded_at']
    def get_badge_name(self, obj): return obj.badge.name if obj.badge else ''
    def get_badge_icon(self, obj): return obj.badge.icon if obj.badge else ''

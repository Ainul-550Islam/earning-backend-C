# api/djoyalty/serializers/BadgeSerializer.py
from rest_framework import serializers
from ..models.engagement import Badge, UserBadge


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = [
            'id', 'name', 'description', 'icon', 'rarity',
            'trigger', 'threshold', 'points_reward',
            'is_active', 'is_unique', 'sort_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserBadgeSerializer(serializers.ModelSerializer):
    badge_name = serializers.SerializerMethodField()
    badge_icon = serializers.SerializerMethodField()
    badge_rarity = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = UserBadge
        fields = [
            'id', 'customer', 'customer_code',
            'badge', 'badge_name', 'badge_icon', 'badge_rarity',
            'points_awarded', 'earned_at',
            'is_pinned', 'display_order',
            'created_at',
        ]
        read_only_fields = ['id', 'badge_name', 'badge_icon', 'badge_rarity', 'customer_code', 'created_at']

    def get_badge_name(self, obj) -> str:
        return obj.badge.name if obj.badge else ''

    def get_badge_icon(self, obj) -> str:
        return obj.badge.icon if obj.badge else '🏅'

    def get_badge_rarity(self, obj) -> str:
        return obj.badge.rarity if obj.badge else 'common'

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


# ── Validator mixin added ─────────────────────────────────────────────────────
from rest_framework import serializers as _s

class _BadgeMixin:
    def validate_name(self, value):
        if not value or not value.strip():
            from rest_framework import serializers
            raise serializers.ValidationError('Badge name cannot be empty.')
        return value.strip()

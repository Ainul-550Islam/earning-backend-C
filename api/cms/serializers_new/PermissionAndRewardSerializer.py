# api/cms/serializers_new/PermissionAndRewardSerializer.py
"""
Serializers for BannerReward, ContentPermission, PermissionAuditLog, PermissionStats
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import BannerReward, ContentPermission, PermissionAuditLog, PermissionStats

User = get_user_model()


class BannerRewardSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = BannerReward
        fields = [
            'uuid', 'user', 'user_display', 'banner', 'amount', 'reward_type',
            'is_processed', 'is_active', 'retry_count', 'last_error', 'created_at',
        ]
        read_only_fields = ['uuid', 'is_processed', 'retry_count', 'last_error', 'created_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Reward amount must be greater than 0.")
        return value


class ContentPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentPermission
        fields = [
            'uuid', 'permission_type', 'content', 'target_id', 'permissions',
            'parent_permission', 'is_active', 'is_system', 'priority', 'created_at',
        ]
        read_only_fields = ['uuid', 'is_system', 'created_at']

    def validate_priority(self, value):
        if value < 0:
            raise serializers.ValidationError("Priority must be non-negative.")
        return value


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionAuditLog
        fields = [
            'uuid', 'permission_id', 'action', 'user_id', 'username',
            'content_id', 'ip_address', 'created_at',
        ]
        read_only_fields = ['uuid', 'created_at']
        extra_kwargs = {
            'ip_address': {'write_only': True},
            'user_agent': {'write_only': True},
        }


class PermissionStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionStats
        fields = [
            'id', 'date', 'content_id', 'check_count',
            'cache_hits', 'cache_misses', 'avg_response_time',
        ]
        read_only_fields = ['id']

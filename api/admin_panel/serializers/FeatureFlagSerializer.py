# api/admin_panel/serializers/FeatureFlagSerializer.py
"""FeatureFlag serializer."""
from rest_framework import serializers
from ..models.config import FeatureFlag


class FeatureFlagSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, default='')
    is_active_globally = serializers.SerializerMethodField()

    class Meta:
        model = FeatureFlag
        fields = [
            'id', 'flag_key', 'label', 'description',
            'is_enabled', 'rollout_pct', 'environments',
            'allowed_user_ids', 'metadata',
            'updated_by', 'updated_by_username',
            'is_active_globally',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_by', 'created_at', 'updated_at']

    def get_is_active_globally(self, obj) -> bool:
        return obj.is_enabled and obj.rollout_pct > 0

    def validate_flag_key(self, value):
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                'flag_key must be snake_case (lowercase letters, digits, underscores).'
            )
        return value

    def validate_rollout_pct(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError('rollout_pct must be between 0 and 100.')
        return value

    def validate_allowed_user_ids(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('allowed_user_ids must be a list.')
        for item in value:
            if not isinstance(item, int):
                raise serializers.ValidationError('All user IDs must be integers.')
        return value
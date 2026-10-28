# api/cms/serializers_new/ABTestingSerializer.py
"""
Serializers for A/B Testing Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.ab_testing import ABTest, ABTestVariant, ABTestParticipant, ABTestResult

User = get_user_model()


class ABTestVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ABTestVariant
        fields = [
            'uuid', 'test', 'name', 'description', 'is_control',
            'traffic_split', 'is_active', 'configuration',
        ]
        read_only_fields = ['uuid']

    def validate_traffic_split(self, value):
        if not (0 < value <= 100):
            raise serializers.ValidationError("traffic_split must be between 1 and 100.")
        return value


class ABTestSerializer(serializers.ModelSerializer):
    variants = ABTestVariantSerializer(many=True, read_only=True)

    class Meta:
        model = ABTest
        fields = [
            'uuid', 'name', 'description', 'test_type', 'status',
            'target_percentage', 'target_countries', 'target_devices',
            'variants', 'created_at', 'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def validate_target_percentage(self, value):
        if not (0 < value <= 100):
            raise serializers.ValidationError("target_percentage must be between 1 and 100.")
        return value


class ABTestParticipantSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = ABTestParticipant
        fields = [
            'uuid', 'test', 'variant', 'user', 'user_display',
            'assigned_at', 'first_seen_at', 'last_seen_at', 'has_converted',
        ]
        read_only_fields = ['uuid', 'assigned_at', 'first_seen_at', 'last_seen_at']


class ABTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ABTestResult
        fields = [
            'uuid', 'test', 'variant', 'total_participants', 'active_participants',
            'conversions', 'conversion_rate', 'total_value',
        ]
        read_only_fields = ['uuid', 'conversion_rate']

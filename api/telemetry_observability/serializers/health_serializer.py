"""
Health Status serializer. DRY: inherits BaseSerializer.
"""
from rest_framework import serializers

from ..models.health_status import HealthStatus
from ..choices import HealthStatusChoices, EnvironmentChoices
from .base_serializer import BaseSerializer


class HealthStatusSerializer(BaseSerializer):
    is_healthy   = serializers.SerializerMethodField()
    is_degraded  = serializers.SerializerMethodField()
    is_unhealthy = serializers.SerializerMethodField()

    class Meta:
        model  = HealthStatus
        fields = [
            'id', 'service_name', 'component_name', 'status',
            'health_score', 'last_check', 'uptime', 'response_time_ms',
            'error_rate', 'metadata', 'environment',
            'is_healthy', 'is_degraded', 'is_unhealthy',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'last_check', 'created_at', 'updated_at']

    def get_is_healthy(self, obj):
        return obj.is_healthy()

    def get_is_degraded(self, obj):
        return obj.is_degraded()

    def get_is_unhealthy(self, obj):
        return obj.is_unhealthy()

    def validate_health_score(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("health_score must be between 0 and 100.")
        return value

    def validate_error_rate(self, value):
        if not (0.0 <= value <= 100.0):
            raise serializers.ValidationError("error_rate must be between 0 and 100.")
        return value

    def validate_status(self, value):
        if value not in HealthStatusChoices.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {HealthStatusChoices.values}."
            )
        return value


class HealthStatusCreateSerializer(BaseSerializer):
    class Meta:
        model  = HealthStatus
        fields = [
            'service_name', 'component_name', 'status',
            'health_score', 'uptime', 'response_time_ms',
            'error_rate', 'metadata', 'environment',
        ]

    def validate_health_score(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("health_score must be between 0 and 100.")
        return value

    def validate_error_rate(self, value):
        if not (0.0 <= value <= 100.0):
            raise serializers.ValidationError("error_rate must be between 0 and 100.")
        return value

    def validate_status(self, value):
        if value not in HealthStatusChoices.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {HealthStatusChoices.values}."
            )
        return value

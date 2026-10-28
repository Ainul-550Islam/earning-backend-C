"""
Alert serializer. DRY: inherits BaseSerializer.
"""
from rest_framework import serializers

from ..models.alert import Alert
from ..choices import AlertTypeChoices, AlertSeverityChoices, AlertStatusChoices
from .base_serializer import BaseSerializer


class AlertSerializer(BaseSerializer):
    class Meta:
        model  = Alert
        fields = [
            'id', 'name', 'alert_type', 'severity', 'status',
            'condition', 'message', 'source', 'service', 'environment',
            'triggered_at', 'resolved_at', 'acknowledged_by',
            'acknowledged_at', 'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'triggered_at', 'resolved_at',
            'acknowledged_at', 'created_at', 'updated_at',
        ]

    def validate_alert_type(self, value):
        if value not in AlertTypeChoices.values:
            raise serializers.ValidationError(
                f"Invalid alert_type. Must be one of: {AlertTypeChoices.values}."
            )
        return value

    def validate_severity(self, value):
        if value not in AlertSeverityChoices.values:
            raise serializers.ValidationError(
                f"Invalid severity. Must be one of: {AlertSeverityChoices.values}."
            )
        return value

    def validate_status(self, value):
        if value not in AlertStatusChoices.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {AlertStatusChoices.values}."
            )
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Alert name cannot be empty.")
        return value


class AlertCreateSerializer(BaseSerializer):
    class Meta:
        model  = Alert
        fields = ['name', 'alert_type', 'severity', 'condition',
                  'message', 'source', 'service', 'environment', 'metadata']

    def validate_severity(self, value):
        if value not in AlertSeverityChoices.values:
            raise serializers.ValidationError(
                f"Invalid severity. Must be one of: {AlertSeverityChoices.values}."
            )
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Alert name cannot be empty.")
        return value


class AlertAcknowledgeSerializer(serializers.Serializer):
    user = serializers.CharField(max_length=255)

    def validate_user(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("User identifier cannot be empty.")
        return value


class AlertStatisticsSerializer(serializers.Serializer):
    period_hours    = serializers.IntegerField()
    total_alerts    = serializers.IntegerField()
    open_alerts     = serializers.IntegerField()
    resolved_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    warning_alerts  = serializers.IntegerField()


class AlertBatchCreateSerializer(serializers.Serializer):
    alerts = AlertCreateSerializer(many=True)

    def validate_alerts(self, value):
        if not value:
            raise serializers.ValidationError("At least one alert must be provided.")
        return value

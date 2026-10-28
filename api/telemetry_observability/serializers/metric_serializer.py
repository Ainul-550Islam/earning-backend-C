"""
Metric Event serializer for Telemetry Observability.
DRY: inherits BaseSerializer for created_at / updated_at.
"""
from rest_framework import serializers

from ..models.metric_event import MetricEvent
from ..choices import MetricTypeChoices, EnvironmentChoices
from .base_serializer import BaseSerializer


class MetricEventSerializer(BaseSerializer):
    """Full read/response serializer for MetricEvent."""

    class Meta:
        model  = MetricEvent
        fields = [
            'id', 'name', 'metric_type', 'value', 'unit',
            'labels', 'source', 'service', 'environment',
            'timestamp', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'timestamp', 'created_at', 'updated_at']

    def validate_metric_type(self, value):
        if value not in MetricTypeChoices.values:
            raise serializers.ValidationError(
                f"Invalid metric_type. Must be one of: {MetricTypeChoices.values}."
            )
        return value

    def validate_value(self, value):
        if value is None:
            raise serializers.ValidationError("Metric value cannot be null.")
        return value


class MetricEventCreateSerializer(BaseSerializer):
    """Write serializer for MetricEvent (POST / PUT / PATCH)."""

    class Meta:
        model  = MetricEvent
        fields = ['name', 'metric_type', 'value', 'unit',
                  'labels', 'source', 'service', 'environment']

    def validate_metric_type(self, value):
        if value not in MetricTypeChoices.values:
            raise serializers.ValidationError(
                f"Invalid metric_type. Must be one of: {MetricTypeChoices.values}."
            )
        return value

    def validate_value(self, value):
        if value is None:
            raise serializers.ValidationError("Metric value cannot be null.")
        return value


class MetricEventListSerializer(BaseSerializer):
    """Compact list serializer for MetricEvent."""

    class Meta:
        model  = MetricEvent
        fields = ['id', 'name', 'metric_type', 'value', 'unit', 'service', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class MetricStatisticsSerializer(serializers.Serializer):
    """Read-only serializer for metric aggregation responses."""
    metric_name  = serializers.CharField()
    period_hours = serializers.IntegerField()
    count        = serializers.IntegerField()
    avg          = serializers.FloatField()
    min          = serializers.FloatField()
    max          = serializers.FloatField()
    sum          = serializers.FloatField()


class MetricBatchCreateSerializer(serializers.Serializer):
    """Serializer for batch-creating multiple MetricEvent records."""
    metrics = MetricEventCreateSerializer(many=True)

    def validate_metrics(self, value):
        if not value:
            raise serializers.ValidationError("At least one metric must be provided.")
        return value

"""
Trace Span serializer. DRY: inherits BaseSerializer.
"""
from rest_framework import serializers

from ..models.trace_span import TraceSpan
from ..choices import TraceStatusChoices
from .base_serializer import BaseSerializer


class TraceSpanSerializer(BaseSerializer):
    class Meta:
        model  = TraceSpan
        fields = [
            'id', 'trace_id', 'span_id', 'parent_span_id',
            'operation_name', 'service', 'start_time', 'end_time',
            'duration_ms', 'status', 'tags', 'logs', 'context',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'span_id', 'start_time', 'created_at', 'updated_at']

    def validate_status(self, value):
        if value not in TraceStatusChoices.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {TraceStatusChoices.values}."
            )
        return value


class TraceSpanCreateSerializer(serializers.Serializer):
    """Write serializer for starting a new span."""
    operation_name = serializers.CharField(max_length=255)
    trace_id       = serializers.CharField(max_length=255, required=False, allow_blank=True)
    parent_span_id = serializers.CharField(max_length=255, required=False, allow_null=True)
    service        = serializers.CharField(max_length=255, required=False, default='default')
    tags           = serializers.DictField(required=False, default=dict)

    def validate_operation_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("operation_name cannot be empty.")
        return value


class TraceSpanFinishSerializer(serializers.Serializer):
    """Write serializer for finishing a span."""
    status  = serializers.ChoiceField(choices=TraceStatusChoices.choices, default='success')
    logs    = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    context = serializers.DictField(required=False, default=dict)


class TraceBatchCreateSerializer(serializers.Serializer):
    spans = TraceSpanCreateSerializer(many=True)

    def validate_spans(self, value):
        if not value:
            raise serializers.ValidationError("At least one span must be provided.")
        return value

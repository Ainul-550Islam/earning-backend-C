"""Webhook Delivery Log Serializer

This module contains the serializer for the WebhookDeliveryLog model.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookDeliveryLog, WebhookEndpoint
from ..constants import DeliveryStatus

User = get_user_model()


class WebhookDeliveryLogSerializer(serializers.ModelSerializer):
    """Serializer for WebhookDeliveryLog model."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.url', read_only=True)
    
    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id',
            'endpoint',
            'endpoint_label',
            'endpoint_url',
            'event_type',
            'payload',
            'request_headers',
            'signature',
            'http_status_code',
            'response_body',
            'duration_ms',
            'error_message',
            'status',
            'attempt_number',
            'max_attempts',
            'next_retry_at',
            'dispatched_at',
            'completed_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'dispatched_at', 
            'completed_at', 'next_retry_at', 'signature'
        ]
    
    def validate_status(self, value):
        """Validate delivery status."""
        valid_statuses = [status.value for status in DeliveryStatus]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value
    
    def validate_attempt_number(self, value):
        """Validate attempt number."""
        if value < 1:
            raise serializers.ValidationError("Attempt number must be at least 1.")
        return value
    
    def validate_max_attempts(self, value):
        """Validate max attempts."""
        if value < 1:
            raise serializers.ValidationError("Max attempts must be at least 1.")
        return value
    
    def validate(self, attrs):
        """Validate attempt number vs max attempts."""
        attempt_number = attrs.get('attempt_number', 1)
        max_attempts = attrs.get('max_attempts', 3)
        
        if attempt_number > max_attempts:
            raise serializers.ValidationError(
                "Attempt number cannot be greater than max attempts."
            )
        
        return attrs


class WebhookDeliveryLogCreateSerializer(WebhookDeliveryLogSerializer):
    """Serializer for creating webhook delivery logs."""
    
    class Meta(WebhookDeliveryLogSerializer.Meta):
        fields = [
            'endpoint',
            'event_type',
            'payload',
            'request_headers',
            'http_status_code',
            'response_body',
            'duration_ms',
            'error_message',
            'status',
            'attempt_number',
            'max_attempts'
        ]
        read_only_fields = []


class WebhookDeliveryLogUpdateSerializer(WebhookDeliveryLogSerializer):
    """Serializer for updating webhook delivery logs."""
    
    class Meta(WebhookDeliveryLogSerializer.Meta):
        fields = [
            'http_status_code',
            'response_body',
            'duration_ms',
            'error_message',
            'status',
            'attempt_number',
            'max_attempts',
            'next_retry_at',
            'dispatched_at',
            'completed_at',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class WebhookDeliveryLogDetailSerializer(WebhookDeliveryLogSerializer):
    """Detailed serializer for webhook delivery logs."""
    
    endpoint = serializers.PrimaryKeyRelatedField(queryset=WebhookEndpoint.objects.all())
    
    class Meta(WebhookDeliveryLogSerializer.Meta):
        fields = WebhookDeliveryLogSerializer.Meta.fields


class WebhookDeliveryLogListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing webhook delivery logs."""
    
    endpoint_label = serializers.CharField(source='endpoint.label', read_only=True)
    endpoint_url = serializers.URLField(source='endpoint.url', read_only=True)
    
    class Meta:
        model = WebhookDeliveryLog
        fields = [
            'id',
            'endpoint_label',
            'endpoint_url',
            'event_type',
            'status',
            'http_status_code',
            'duration_ms',
            'attempt_number',
            'created_at'
        ]


class WebhookDeliveryLogRetrySerializer(serializers.Serializer):
    """Serializer for webhook delivery log retry operations."""
    
    force_retry = serializers.BooleanField(default=False, write_only=True)
    
    def validate_force_retry(self, value):
        """Validate force retry option."""
        return value


class WebhookDeliveryLogStatsSerializer(serializers.Serializer):
    """Serializer for webhook delivery log statistics."""
    
    total_count = serializers.IntegerField(read_only=True)
    success_count = serializers.IntegerField(read_only=True)
    failed_count = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    min_response_time = serializers.FloatField(read_only=True)
    max_response_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'total_count',
            'success_count',
            'failed_count',
            'success_rate',
            'avg_response_time',
            'min_response_time',
            'max_response_time'
        ]
